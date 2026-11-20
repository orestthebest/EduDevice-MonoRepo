-- ===========================================================================
-- sim_whole_marks.sql - Schularbeit and project marks of the sim students
--                       become whole numbers
--
-- Schularbeiten and projects are graded from points (up to 50 % a 4, 56 % 5,
-- 62 % 6, 71 % 7, 81 % 8, 91 % 9, above 10), so a 4.5 cannot exist. The first
-- sim seed gave them half steps; seed_edudevice_real.py is fixed, this fixes
-- the rows already in the database.
--
-- Each .5 goes up or down by a fixed coin (CRC32 of the grade id): about half
-- each way, and the same result every time. Already whole marks are not
-- touched, so a second run changes nothing. Only sim_* students, only the
-- categories schularbeit and project.
--
-- Changes data: take a backup first, e.g.
--   mysqldump edudevice_db grades > backup_vor_whole_marks.sql
-- ===========================================================================

USE edudevice_db;

-- Vorher: wie viele halbe Schularbeit-/Projektnoten gibt es?
SELECT g.category, COUNT(*) AS half_marks
FROM grades g JOIN users u ON u.id = g.student_id
WHERE u.username LIKE 'sim\_%'
  AND g.category IN ('schularbeit', 'project')
  AND g.value <> FLOOR(g.value)
GROUP BY g.category;

UPDATE grades g
    JOIN users u ON u.id = g.student_id
SET g.value = CASE WHEN CRC32(CONCAT('whole-', g.id)) % 2 = 0 THEN FLOOR(g.value)
                   ELSE CEIL(g.value) END
WHERE u.username LIKE 'sim\_%'
  AND g.category IN ('schularbeit', 'project')
  AND g.value <> FLOOR(g.value);

-- Nachher: muss 0 Zeilen liefern
SELECT g.category, COUNT(*) AS half_marks
FROM grades g JOIN users u ON u.id = g.student_id
WHERE u.username LIKE 'sim\_%'
  AND g.category IN ('schularbeit', 'project')
  AND g.value <> FLOOR(g.value);