-- ============================================================
-- EduDevice Schema V4.10 (Migration von V4.9)
-- Letzter Unterrichtstag pro Klasse (Jorik)
--
-- Neu:
--   classes.last_lesson_day   letzter Unterrichtstag dieser Klasse, wenn er
--                             vor dem des Schuljahres liegt. NULL = wie das
--                             Schuljahr (school_years.last_lesson_day).
--
-- Warum: Die 5. Klassen haben nur bis zum Ende ihres 3. Trimesters
-- (30.04.2027) regulaeren Unterricht. Die Fehlzeiten-Grenzen (20 % / 30 %)
-- werden an den Unterrichtsminuten des ganzen Jahres gemessen - fuer eine
-- 5. Klasse endet dieses Jahr am 30.04.
--
-- Nichts wird geloescht. Falls fuer 5. Klassen schon Stunden nach dem 30.04.
-- angelegt wurden, bleiben sie stehen; die Auswertung zaehlt sie nicht mit.
-- Die Kontrollabfrage am Ende zeigt, ob es solche Stunden gibt.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

ALTER TABLE classes
    ADD COLUMN last_lesson_day DATE NULL AFTER class_teacher_id;

-- 5. Klassen im Schuljahr 2026/27: letzter Unterrichtstag 30.04.2027
UPDATE classes c
    JOIN school_years y ON y.id = c.school_year_id
SET c.last_lesson_day = '2027-04-30'
WHERE y.label = '2026/27' AND c.name LIKE '5%';

-- Kontrolle 1: welche Klassen frueher aufhoeren
SELECT c.name, c.last_lesson_day FROM classes c WHERE c.last_lesson_day IS NOT NULL;

-- Kontrolle 2: schon angelegte Stunden nach dem letzten Unterrichtstag der Klasse
-- (werden nicht geloescht, nur gezaehlt)
SELECT c.name, COUNT(*) AS stunden_danach
FROM lessons l
    JOIN timetable t       ON t.id = l.timetable_id
    JOIN class_subjects cs ON cs.id = t.class_subject_id
    JOIN classes c         ON c.id = cs.class_id
WHERE c.last_lesson_day IS NOT NULL AND l.date > c.last_lesson_day
GROUP BY c.name;
