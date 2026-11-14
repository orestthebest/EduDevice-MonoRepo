-- ============================================================
-- EduDevice Schema V4.11 (Migration von V4.10)
-- Stundenplan-Verwaltung durch den Admin (Wunsch von Orest, 14.11.2026)
--   timetable.valid_from / valid_to: ab wann / bis wann ein Eintrag gilt.
--   Ein Eintrag gilt an einem Datum, wenn valid_from <= Datum
--   und (valid_to IS NULL oder valid_to >= Datum).
--   Aendern = alten Eintrag beenden (valid_to = gestern) + neuen anlegen,
--   so bleibt die Geschichte (Anwesenheiten vergangener Stunden) erhalten.
-- Bestehende Eintraege gelten ab dem ersten Unterrichtstag ihres Schuljahres.
-- Das Stundenraster (Periode 1 = 07:45-08:30 ...) steht in der API (core/config.py),
-- nicht in der Datenbank. Alte Eintraege, die nicht ins Raster passen, bleiben gueltig.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

ALTER TABLE timetable
    ADD COLUMN valid_from DATE NULL AFTER room,
    ADD COLUMN valid_to   DATE NULL AFTER valid_from;

UPDATE timetable t
    JOIN class_subjects cs ON cs.id = t.class_subject_id
    JOIN classes c         ON c.id = cs.class_id
    JOIN school_years y    ON y.id = c.school_year_id
SET t.valid_from = COALESCE(y.first_lesson_day, y.start_date)
WHERE t.valid_from IS NULL;

ALTER TABLE timetable
    MODIFY COLUMN valid_from DATE NOT NULL,
    ADD INDEX idx_timetable_valid (class_subject_id, weekday, valid_to);

-- Kontrolle: alle Eintraege mit Gueltigkeit
SELECT t.id, c.name AS klasse, s.name AS fach, t.weekday, t.start_time, t.end_time, t.room,
       t.valid_from, t.valid_to
FROM timetable t
    JOIN class_subjects cs ON cs.id = t.class_subject_id
    JOIN classes c         ON c.id = cs.class_id
    JOIN subjects s        ON s.id = cs.subject_id
ORDER BY c.name, FIELD(t.weekday, 'Mo', 'Di', 'Mi', 'Do', 'Fr'), t.start_time;
