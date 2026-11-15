-- ===========================================================================
-- sim_grid_45min.sql - move the sim timetable onto the school's 45-minute grid
--
-- The first version of sim_timetable.sql used 50-minute periods (08:00-08:50,
-- ...). The school's grid is 07:45-08:30, 08:35-09:20, 09:35-10:20,
-- 10:25-11:10. This moves the existing sim entries (room = 'SIM') onto the grid
-- and recomputes the minutes of the sim absences (50 -> 45).
--
-- Deletes nothing. Changes only:
--   timetable  rows with room = 'SIM' (start_time / end_time)
--   attendance rows of status 'abwesend' in lessons of those timetable rows
-- Lessons keep their ids and dates - they point to the timetable row, so they
-- move with it. Late arrivals (3-20 minutes) stay as they are.
-- Only needed on a database where the old 50-minute sim_timetable.sql ran;
-- a second run changes nothing.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ===========================================================================

USE edudevice_db;

-- end_time FIRST: MySQL applies the assignments left to right, so the second
-- CASE would otherwise already see the new start_time and match nothing.
UPDATE timetable
SET end_time   = CASE start_time WHEN '08:00:00' THEN '08:30' WHEN '08:50:00' THEN '09:20'
                                 WHEN '09:55:00' THEN '10:20' WHEN '10:45:00' THEN '11:10' END,
    start_time = CASE start_time WHEN '08:00:00' THEN '07:45' WHEN '08:50:00' THEN '08:35'
                                 WHEN '09:55:00' THEN '09:35' WHEN '10:45:00' THEN '10:25' END
WHERE room = 'SIM' AND start_time IN ('08:00:00', '08:50:00', '09:55:00', '10:45:00');

UPDATE attendance a
    JOIN lessons l   ON l.id = a.lesson_id
    JOIN timetable t ON t.id = l.timetable_id
SET a.minutes_missed = TIME_TO_SEC(TIMEDIFF(t.end_time, t.start_time)) DIV 60
WHERE t.room = 'SIM' AND a.status = 'abwesend';

-- Kontrolle: alle Sim-Stunden 45 Minuten, alle Sim-Abwesenheiten 45 Minuten
SELECT start_time, end_time, COUNT(*) AS entries FROM timetable WHERE room = 'SIM'
GROUP BY start_time, end_time ORDER BY start_time;
SELECT a.minutes_missed, COUNT(*) AS absences
FROM attendance a JOIN lessons l ON l.id = a.lesson_id JOIN timetable t ON t.id = l.timetable_id
WHERE t.room = 'SIM' AND a.status = 'abwesend' GROUP BY a.minutes_missed;
