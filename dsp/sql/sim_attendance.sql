-- ===========================================================================
-- sim_attendance.sql - simulated attendance for the sim students (2026-11-13)
--
-- Run AFTER sim_timetable.sql and python -m scripts.generate_lessons.
-- Safe to run again: it only adds rows for lessons that have none yet for
-- that student, so it never changes real entries and a second run adds nothing.
-- Only lessons up to today, never cancelled ones (nobody can miss those).
-- Every row belongs to a sim student and disappears with them
-- (attendance.student_id is ON DELETE CASCADE).
-- ===========================================================================

USE edudevice_db;

DROP TEMPORARY TABLE IF EXISTS sim_tendency;
CREATE TEMPORARY TABLE sim_tendency (
    username  VARCHAR(50) COLLATE utf8mb4_unicode_ci PRIMARY KEY,
    p_ill     DECIMAL(5,4) NOT NULL,   -- share of school days ill (all lessons that day)
    p_skip    DECIMAL(5,4) NOT NULL,   -- share of single lessons missed
    p_late    DECIMAL(5,4) NOT NULL    -- share of lessons arrived late
);
INSERT INTO sim_tendency VALUES
  ('sim_0001', 0.0207, 0.0069, 0.0235),
  ('sim_0002', 0.0212, 0.0071, 0.0297),
  ('sim_0003', 0.0207, 0.0052, 0.0121),
  ('sim_0004', 0.0184, 0.0046, 0.0177),
  ('sim_0005', 0.0262, 0.0131, 0.0335),
  ('sim_0006', 0.0327, 0.0163, 0.0499),
  ('sim_0007', 0.0393, 0.0262, 0.0523),
  ('sim_0008', 0.1225, 0.0816, 0.0385),
  ('sim_0009', 0.0232, 0.0077, 0.0299),
  ('sim_0010', 0.0329, 0.011, 0.0409),
  ('sim_0011', 0.0141, 0.0035, 0.0182),
  ('sim_0012', 0.0264, 0.0066, 0.0169),
  ('sim_0013', 0.1083, 0.0722, 0.0548),
  ('sim_0014', 0.0257, 0.0086, 0.0197),
  ('sim_0015', 0.0371, 0.0186, 0.036),
  ('sim_0016', 0.0216, 0.0072, 0.0171),
  ('sim_0017', 0.032, 0.016, 0.0352),
  ('sim_0018', 0.04, 0.0133, 0.0295),
  ('sim_0019', 0.0179, 0.0045, 0.0174),
  ('sim_0020', 0.0606, 0.0404, 0.0289),
  ('sim_0021', 0.0153, 0.0038, 0.0145),
  ('sim_0022', 0.0196, 0.0049, 0.0158),
  ('sim_0023', 0.0195, 0.0097, 0.0282),
  ('sim_0024', 0.0823, 0.0549, 0.0549),
  ('sim_0025', 0.0415, 0.0138, 0.0308),
  ('sim_0026', 0.0341, 0.0114, 0.0382),
  ('sim_0027', 0.0234, 0.0078, 0.0192),
  ('sim_0028', 0.0281, 0.014, 0.0366),
  ('sim_0029', 0.0329, 0.0165, 0.0588),
  ('sim_0030', 0.0504, 0.0252, 0.0558),
  ('sim_0031', 0.0177, 0.0044, 0.0135),
  ('sim_0032', 0.0484, 0.0322, 0.056),
  ('sim_0033', 0.0167, 0.0042, 0.0235),
  ('sim_0034', 0.0447, 0.0223, 0.0332),
  ('sim_0035', 0.0199, 0.01, 0.0182),
  ('sim_0036', 0.0918, 0.0612, 0.0399),
  ('sim_0037', 0.0163, 0.0041, 0.0261),
  ('sim_0038', 0.0586, 0.0391, 0.0256),
  ('sim_0039', 0.0451, 0.03, 0.0258),
  ('sim_0040', 0.0261, 0.0065, 0.0266),
  ('sim_0041', 0.062, 0.0414, 0.0448),
  ('sim_0042', 0.0278, 0.007, 0.015),
  ('sim_0043', 0.0397, 0.0265, 0.0398),
  ('sim_0044', 0.0309, 0.0155, 0.0478),
  ('sim_0045', 0.0937, 0.0625, 0.0741),
  ('sim_0046', 0.0198, 0.005, 0.019),
  ('sim_0047', 0.0222, 0.0074, 0.0345),
  ('sim_0048', 0.0181, 0.0045, 0.0262),
  ('sim_0049', 0.0413, 0.0138, 0.0273),
  ('sim_0050', 0.0288, 0.0096, 0.0133);

INSERT INTO attendance (student_id, lesson_id, status, minutes_missed)
SELECT x.student_id, x.lesson_id,
       CASE WHEN x.r_day < x.p_ill OR x.r_skip < x.p_skip THEN 'abwesend'
            WHEN x.r_late < x.p_late THEN 'verspaetet'
            ELSE 'anwesend' END,
       CASE WHEN x.r_day < x.p_ill OR x.r_skip < x.p_skip THEN x.lesson_minutes
            WHEN x.r_late < x.p_late THEN 3 + x.late_extra
            ELSE 0 END
FROM (
    SELECT u.id AS student_id, l.id AS lesson_id, st.p_ill, st.p_skip, st.p_late,
           TIME_TO_SEC(TIMEDIFF(t.end_time, t.start_time)) DIV 60          AS lesson_minutes,
           (CRC32(CONCAT('ill-',  u.id, '-', l.date)) % 10000) / 10000     AS r_day,
           (CRC32(CONCAT('skip-', u.id, '-', l.id))   % 10000) / 10000     AS r_skip,
           (CRC32(CONCAT('late-', u.id, '-', l.id))   % 10000) / 10000     AS r_late,
            CRC32(CONCAT('min-',  u.id, '-', l.id))   % 18                 AS late_extra
    FROM lessons l
        JOIN timetable t               ON t.id = l.timetable_id
        JOIN class_subject_students cs ON cs.class_subject_id = t.class_subject_id
        JOIN users u                   ON u.id = cs.student_id
        JOIN sim_tendency st           ON st.username = u.username
    WHERE l.date <= CURDATE()
      AND l.cancelled = FALSE
      AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.student_id = u.id AND a.lesson_id = l.id)
) x;

DROP TEMPORARY TABLE sim_tendency;

-- Kontrolle
SELECT a.status, COUNT(*) AS n, SUM(a.minutes_missed) AS minutes
FROM attendance a JOIN users u ON u.id = a.student_id
WHERE u.username LIKE 'sim\_%'
GROUP BY a.status;
