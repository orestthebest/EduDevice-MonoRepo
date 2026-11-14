-- ===========================================================================
-- sim_timetable.sql - weekly timetable for the sim class_subjects (2026-11-13)
-- Inserts only for a class_subject that has NO timetable entry yet.
-- Run before: python -m scripts.generate_lessons
-- ===========================================================================

USE edudevice_db;

INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)
SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM (SELECT 3 AS cs, 'Mo' AS wd, '07:45' AS st, '08:30' AS en UNION ALL SELECT 3 AS cs, 'Mi' AS wd, '09:35' AS st, '10:20' AS en UNION ALL SELECT 3 AS cs, 'Fr' AS wd, '08:35' AS st, '09:20' AS en) v
WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = 3)
  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = 3);

INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)
SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM (SELECT 4 AS cs, 'Di' AS wd, '07:45' AS st, '08:30' AS en UNION ALL SELECT 4 AS cs, 'Di' AS wd, '08:35' AS st, '09:20' AS en UNION ALL SELECT 4 AS cs, 'Do' AS wd, '09:35' AS st, '10:20' AS en UNION ALL SELECT 4 AS cs, 'Do' AS wd, '10:25' AS st, '11:10' AS en) v
WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = 4)
  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = 4);

INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)
SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM (SELECT 5 AS cs, 'Mo' AS wd, '09:35' AS st, '10:20' AS en UNION ALL SELECT 5 AS cs, 'Mi' AS wd, '07:45' AS st, '08:30' AS en UNION ALL SELECT 5 AS cs, 'Fr' AS wd, '10:25' AS st, '11:10' AS en) v
WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = 5)
  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = 5);

INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)
SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM (SELECT 2 AS cs, 'Mo' AS wd, '08:35' AS st, '09:20' AS en UNION ALL SELECT 2 AS cs, 'Mi' AS wd, '10:25' AS st, '11:10' AS en UNION ALL SELECT 2 AS cs, 'Do' AS wd, '07:45' AS st, '08:30' AS en) v
WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = 2)
  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = 2);

INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)
SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM (SELECT 6 AS cs, 'Di' AS wd, '09:35' AS st, '10:20' AS en UNION ALL SELECT 6 AS cs, 'Di' AS wd, '10:25' AS st, '11:10' AS en UNION ALL SELECT 6 AS cs, 'Fr' AS wd, '07:45' AS st, '08:30' AS en UNION ALL SELECT 6 AS cs, 'Fr' AS wd, '08:35' AS st, '09:20' AS en) v
WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = 6)
  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = 6);

-- Kontrolle: Stunden pro Woche je Fach
SELECT class_subject_id, COUNT(*) AS per_week FROM timetable
WHERE class_subject_id IN (3, 4, 5, 2, 6) GROUP BY class_subject_id;
