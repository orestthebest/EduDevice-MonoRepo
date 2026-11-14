-- ===========================================================================
-- sim_cut_grades_after_today.sql - OPTIONAL, DELETES ROWS
--
-- The sim grades (sim_seed_edudevice.sql) cover the whole school year up to
-- July 2027. On the live server that makes the year look finished: nothing is
-- "still open", forecasts have nothing left to forecast, and "recent grades"
-- shows June 2027. This file deletes the sim grades dated after today, so the
-- server shows a year in progress - the way it will look with real data.
--
-- What it deletes: ONLY rows in `grades` that belong to a sim student
-- (username sim_...) AND are dated after today. Real students, real grades and
-- all other tables are not touched.
-- To undo: delete the sim students and run sim_seed_edudevice.sql again.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ===========================================================================

USE edudevice_db;

-- first look: how many rows would go
SELECT COUNT(*) AS sim_grades_after_today
FROM grades g JOIN users u ON u.id = g.student_id
WHERE u.username LIKE 'sim\_%' AND g.date > CURDATE();

DELETE g FROM grades g JOIN users u ON u.id = g.student_id
WHERE u.username LIKE 'sim\_%' AND g.date > CURDATE();
