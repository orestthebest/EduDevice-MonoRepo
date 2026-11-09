-- ============================================================
-- EduDevice Schulkalender 2026/27 (Daten, gehoert zu Schema V4.8)
-- Quelle: Jahreskalender der Schule 2026/27.
-- Eingetragen sind nur Tage, die vom normalen Wochenplan abweichen.
-- Kontrolle: vom 03.09.2026 bis 25.06.2027 ergeben sich damit genau
-- 181 Unterrichtstage - so wie im Kalender ("181. Unterrichtstag").
--
-- Kann mehrmals ausgefuehrt werden: ein schon vorhandenes Datum wird
-- mit den Werten hier ueberschrieben (nur in school_calendar).
-- VORAUSSETZUNG: migration_v4_8_kalender_minuten.sql ist gelaufen
--                und es gibt das Schuljahr mit label '2026/27'.
-- ============================================================

USE edudevice_db;

SET @sy = (SELECT id FROM school_years WHERE label = '2026/27');

UPDATE school_years
SET first_lesson_day = '2026-09-03', last_lesson_day = '2027-06-25'
WHERE id = @sy;

INSERT INTO school_calendar (date, school_year_id, day_type, has_lessons, timetable_weekday, note) VALUES
    ('2026-09-03', @sy, 'info', TRUE, NULL, '1. Unterrichtstag'),
    ('2026-09-07', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2026-10-29', @sy, 'autonomous_day', FALSE, NULL, 'schulautonomer Tag (SAFT)'),
    ('2026-10-30', @sy, 'autonomous_day', FALSE, NULL, 'schulautonomer Tag (SAFT)'),
    ('2026-11-18', @sy, 'info', TRUE, NULL, 'Sprechtag'),
    ('2026-11-20', @sy, 'info', TRUE, NULL, 'Trimesterende 5. Klassen'),
    ('2026-11-23', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2026-11-24', @sy, 'swapped_timetable', TRUE, 'Mo', 'Montagsstundenplan'),
    ('2026-11-25', @sy, 'swapped_timetable', TRUE, 'Di', 'Dienstagsstundenplan'),
    ('2026-11-30', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2026-12-01', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2026-12-02', @sy, 'swapped_timetable', TRUE, 'Mo', 'Montagsstundenplan'),
    ('2026-12-03', @sy, 'swapped_timetable', TRUE, 'Di', 'Dienstagsstundenplan'),
    ('2026-12-04', @sy, 'swapped_timetable', TRUE, 'Mi', 'Mittwochsstundenplan'),
    ('2026-12-08', @sy, 'holiday', FALSE, NULL, 'Feiertag'),
    ('2026-12-16', @sy, 'info', TRUE, NULL, 'Beurteilungskonferenz'),
    ('2026-12-21', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-22', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-23', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-24', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-25', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-28', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-29', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-30', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2026-12-31', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2027-01-01', @sy, 'break', FALSE, NULL, 'Weihnachtsferien'),
    ('2027-01-04', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2027-01-05', @sy, 'swapped_timetable', TRUE, 'Mo', 'Montagsstundenplan'),
    ('2027-01-13', @sy, 'info', TRUE, NULL, 'paed. Konferenz / Q-Day'),
    ('2027-02-11', @sy, 'autonomous_day', FALSE, NULL, 'schulautonomer Tag (SAFT)'),
    ('2027-02-12', @sy, 'autonomous_day', FALSE, NULL, 'schulautonomer Tag (SAFT)'),
    ('2027-02-17', @sy, 'info', TRUE, NULL, 'Sprechtag'),
    ('2027-02-19', @sy, 'info', TRUE, NULL, 'Trimesterende 5. Klassen'),
    ('2027-03-10', @sy, 'holiday', FALSE, NULL, 'Feiertag'),
    ('2027-03-15', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2027-03-22', @sy, 'holiday', FALSE, NULL, 'Feiertag'),
    ('2027-03-23', @sy, 'swapped_timetable', TRUE, 'Mo', 'Montagsstundenplan'),
    ('2027-03-24', @sy, 'info', TRUE, NULL, 'Beurteilungskonferenz'),
    ('2027-03-29', @sy, 'holiday', FALSE, NULL, 'Feiertag (Ostermontag)'),
    ('2027-03-30', @sy, 'break', FALSE, NULL, 'Osterferien'),
    ('2027-03-31', @sy, 'break', FALSE, NULL, 'Osterferien'),
    ('2027-04-01', @sy, 'break', FALSE, NULL, 'Osterferien'),
    ('2027-04-02', @sy, 'break', FALSE, NULL, 'Osterferien'),
    ('2027-04-14', @sy, 'info', TRUE, NULL, 'paed. Konferenz / Q-Day'),
    ('2027-04-21', @sy, 'info', TRUE, NULL, 'Sprechtag'),
    ('2027-04-30', @sy, 'info', TRUE, NULL, 'Trimesterende 5. Klassen'),
    ('2027-05-03', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2027-05-04', @sy, 'holiday', FALSE, NULL, 'Feiertag/Ersatztag'),
    ('2027-05-05', @sy, 'swapped_timetable', TRUE, 'Mo', 'Montagsstundenplan'),
    ('2027-05-06', @sy, 'swapped_timetable', TRUE, 'Di', 'Dienstagsstundenplan, Tag der offenen Tuer'),
    ('2027-05-07', @sy, 'swapped_timetable', TRUE, 'Mi', 'Mittwochsstundenplan'),
    ('2027-05-17', @sy, 'holiday', FALSE, NULL, 'Feiertag'),
    ('2027-06-17', @sy, 'info', TRUE, NULL, 'Beurteilungskonferenz'),
    ('2027-06-18', @sy, 'info', TRUE, NULL, 'Schuljahresende 9. Klassen'),
    ('2027-06-25', @sy, 'info', TRUE, NULL, '181. Unterrichtstag (letzter)')
ON DUPLICATE KEY UPDATE
    school_year_id = VALUES(school_year_id), day_type = VALUES(day_type), has_lessons = VALUES(has_lessons),
    timetable_weekday = VALUES(timetable_weekday), note = VALUES(note);

-- Kontrolle: Anzahl je Art (holiday 13, autonomous_day 4, break 14, swapped_timetable 10, info 14)
SELECT day_type, COUNT(*) AS n FROM school_calendar WHERE school_year_id = @sy GROUP BY day_type;

