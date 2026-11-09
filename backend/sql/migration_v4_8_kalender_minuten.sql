-- ============================================================
-- EduDevice Schema V4.8 (Migration von V4.7)
-- Fehlminuten, Schulkalender und Tabellen fuer die Auswertung (Jorik)
--
-- Neu:
--   attendance.minutes_missed        versaeumte Minuten pro Stunde
--                                    (anwesend = 0, abwesend = ganze Stunde,
--                                     verspaetet = tatsaechliche Minuten)
--   school_years.first_lesson_day /  erster und letzter Unterrichtstag
--   school_years.last_lesson_day
--   school_calendar                  Tage, die vom normalen Wochenplan abweichen:
--                                    Feiertage, Ferien, schulautonome Tage und
--                                    Tage mit getauschtem Stundenplan
--   grade_forecasts.predicted_low /  Unsicherheitsbereich der Prognose
--   grade_forecasts.predicted_high
--   student_insights                 die "3 Beobachtungen" fuer die Schuelersicht
--
-- Warum Minuten: Die 20-%/30-%-Grenze wird an den Unterrichtsminuten eines
-- Fachs im ganzen Jahr gemessen. 5 Minuten Verspaetung sind 5 Minuten,
-- nicht eine ganze Stunde. Ob entschuldigt oder nicht, spielt fuer die
-- Grenze keine Rolle.
--
-- Nichts wird geloescht. Bestehende Zeilen bekommen nur Werte in den
-- NEUEN Spalten. Trotzdem:
-- VORAUSSETZUNG: migration_v4_7_pipeline.sql ist schon gelaufen
--                (grade_forecasts und pipeline_runs muessen existieren).
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

-- ------------------------------------------------------------
-- 1. Fehlminuten pro Anwesenheitseintrag
-- ------------------------------------------------------------
ALTER TABLE attendance
    ADD COLUMN minutes_missed SMALLINT UNSIGNED NULL AFTER status;

-- Bestehende Eintraege nachtragen:
--   anwesend -> 0
--   abwesend -> Laenge der Stunde laut Stundenplan
--   verspaetet -> bleibt NULL (die Minuten wurden nie erfasst; die Lehrkraft
--                 kann sie nachtragen, die Auswertung behandelt NULL als "unbekannt")
UPDATE attendance SET minutes_missed = 0 WHERE status = 'anwesend';

UPDATE attendance a
    JOIN lessons   l ON l.id = a.lesson_id
    JOIN timetable t ON t.id = l.timetable_id
SET a.minutes_missed = TIME_TO_SEC(TIMEDIFF(t.end_time, t.start_time)) DIV 60
WHERE a.status = 'abwesend';

ALTER TABLE attendance
    -- COALESCE, weil ein CHECK bei NULL nicht greift (NULL = "unbekannt" = erlaubt)
    ADD CONSTRAINT chk_attendance_minutes CHECK (
        (status = 'anwesend' AND COALESCE(minutes_missed, -1) = 0) OR
        (status <> 'anwesend' AND COALESCE(minutes_missed, 1) > 0)
    );

-- ------------------------------------------------------------
-- 2. Erster und letzter Unterrichtstag des Schuljahres
--    (start_date/end_date bleiben unveraendert - sie beschreiben das
--     Schuljahr, nicht die Unterrichtszeit)
-- ------------------------------------------------------------
ALTER TABLE school_years
    ADD COLUMN first_lesson_day DATE NULL AFTER end_date,
    ADD COLUMN last_lesson_day  DATE NULL AFTER first_lesson_day,
    ADD CONSTRAINT chk_school_years_lesson_days CHECK (
        first_lesson_day IS NULL OR last_lesson_day IS NULL OR last_lesson_day > first_lesson_day
    );

-- ------------------------------------------------------------
-- 3. Schulkalender: nur die Tage, die vom normalen Wochenplan abweichen.
--    Ein Tag, der hier nicht steht, ist ein normaler Unterrichtstag
--    (Mo-Fr, mit dem Stundenplan seines eigenen Wochentags).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS school_calendar (
    date               DATE PRIMARY KEY,
    school_year_id     INT UNSIGNED NOT NULL,
    day_type           ENUM('holiday',           -- Feiertag oder Ersatztag
                            'autonomous_day',    -- schulautonomer Tag (SAFT)
                            'break',             -- Ferien
                            'swapped_timetable', -- Unterricht nach dem Plan eines anderen Wochentags
                            'info'               -- Unterricht normal, nur ein Hinweis (Sprechtag, Konferenz ...)
                           ) NOT NULL,
    has_lessons        BOOLEAN NOT NULL,
    timetable_weekday  ENUM('Mo','Di','Mi','Do','Fr') NULL,  -- nur bei swapped_timetable
    note               VARCHAR(100) NULL,
    CHECK (has_lessons = (day_type IN ('swapped_timetable', 'info'))),
    CHECK ((day_type = 'swapped_timetable') = (timetable_weekday IS NOT NULL)),
    FOREIGN KEY (school_year_id) REFERENCES school_years(id),
    INDEX idx_calendar_year (school_year_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. Unsicherheitsbereich fuer die Prognose (Tabelle aus V4.7)
--    NULL, solange das Modell noch keinen Bereich liefert.
-- ------------------------------------------------------------
ALTER TABLE grade_forecasts
    ADD COLUMN predicted_low  DECIMAL(4,2) NULL AFTER predicted_grade,
    ADD COLUMN predicted_high DECIMAL(4,2) NULL AFTER predicted_low,
    ADD CONSTRAINT chk_forecast_range CHECK (
        (predicted_low IS NULL AND predicted_high IS NULL) OR
        (predicted_low <= predicted_grade AND predicted_grade <= predicted_high
         AND predicted_low >= 4 AND predicted_high <= 10)
    );

-- ------------------------------------------------------------
-- 5. Beobachtungen fuer die Schuelersicht ("3 Dinge, die das Modell bemerkt hat")
--    Der naechtliche Lauf schreibt Kandidaten mit einer Staerke (score);
--    angezeigt werden die drei staerksten der aktuellen Woche.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_insights (
    id                 INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id             INT UNSIGNED NOT NULL,
    student_id         INT UNSIGNED NOT NULL,
    class_subject_id   INT UNSIGNED NULL,               -- NULL = betrifft alle Faecher
    week_start         DATE NOT NULL,                   -- Montag der Berichtswoche
    kind               VARCHAR(40) NOT NULL,            -- z. B. 'trimester_up', 'recovery', 'near_round_up'
    tone               ENUM('positive','neutral','attention') NOT NULL,
    score              DECIMAL(6,3) NOT NULL,           -- Staerke der Beobachtung
    message            VARCHAR(255) NOT NULL,           -- fertiger Satz fuer die Anzeige (Englisch)
    model_version      VARCHAR(50) NOT NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id)           REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)       REFERENCES users(id)             ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id)    ON DELETE CASCADE,
    INDEX idx_insights_student_week (student_id, week_start, score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 6. Jorik darf in die Ergebnistabellen der Auswertung schreiben
--    (pipeline_runs und grade_forecasts sind seit V4.7 freigegeben)
-- ------------------------------------------------------------
GRANT INSERT, UPDATE, DELETE ON edudevice_db.risk_assessments TO 'jorik'@'localhost';
GRANT INSERT, UPDATE, DELETE ON edudevice_db.alerts           TO 'jorik'@'localhost';
GRANT INSERT, UPDATE, DELETE ON edudevice_db.student_insights TO 'jorik'@'localhost';

-- Kontrolle
SELECT status, COUNT(*) AS n, SUM(minutes_missed IS NULL) AS ohne_minuten
FROM attendance GROUP BY status;
