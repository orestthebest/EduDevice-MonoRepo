"""
seed_attendance.py — simulated attendance for the sim students (SQL for Gridi).

What it writes
--------------
  sim_timetable.sql    a weekly timetable for the five sim class_subjects, but
                       only for a class_subject that has no timetable yet - if
                       Gridi already made one, his stays untouched
  sim_attendance.sql   attendance rows (with minutes) for every sim student in
                       every lesson that already took place

Order on the server
-------------------
  1. sim_timetable.sql
  2. python -m scripts.generate_lessons        (backend; creates the lessons)
  3. sim_attendance.sql

Why the attendance is generated IN SQL
--------------------------------------
The lesson ids only exist after step 2, and Gridi may already have his own
timetable. So the file does not list lessons. It ships one small table of
per-student tendencies and lets MySQL walk over whatever lessons exist:

  * a "sick day" is decided per student and DATE, so a sick student misses
    every lesson that day, like a real one
  * single missed lessons and late arrivals are decided per student and lesson
  * the dice are CRC32 hashes of the ids, not RAND(): the same database gives
    the same attendance every time, and a second run inserts nothing new

Only lessons up to the day the file is run, not cancelled, and only for
lessons with no attendance row yet for that student - real entries made in
Orest's attendance page are never touched.

Tendencies follow the archetype the sim grades were generated with, so absence
and grades fit together (failing students also miss more). The same seed as
the grade seed reproduces the same archetypes.

Usage
-----
  python src/seed_attendance.py            (writes both files into the dsp folder)
"""

from __future__ import annotations

import argparse
import random
from datetime import date
from pathlib import Path

import seed_edudevice_real as seed

GRADE_SEED = 20261025        # the seed the server's sim_seed_edudevice.sql was made with
PER_CLASS = 25

# (share of days ill, share of single lessons skipped, share of lessons late)
TENDENCY = {
    "failing":     (0.090, 0.060, 0.060),
    "declining":   (0.045, 0.030, 0.040),
    "volatile":    (0.040, 0.020, 0.050),
    "sudden_drop": (0.030, 0.015, 0.030),
    "improving":   (0.030, 0.010, 0.030),
    "incomplete":  (0.030, 0.010, 0.020),
    "steady":      (0.020, 0.005, 0.020),
}

# 50-minute periods (like Gridi's seed: 08:00-08:50)
PERIODS = {1: ("08:00", "08:50"), 2: ("08:50", "09:40"), 3: ("09:55", "10:45"),
           4: ("10:45", "11:35"), 5: ("11:45", "12:35"), 6: ("12:35", "13:25")}

# class_subject_id -> [(weekday, period)], no clashes within a class
#   5B: 3 Mathematics, 4 Software Development, 5 INSY      4A: 2 Mathematik, 6 SEW
TIMETABLE = {
    3: [("Mo", 1), ("Mi", 3), ("Fr", 2)],
    4: [("Di", 1), ("Di", 2), ("Do", 3), ("Do", 4)],
    5: [("Mo", 3), ("Mi", 1), ("Fr", 4)],
    2: [("Mo", 2), ("Mi", 4), ("Do", 1)],
    6: [("Di", 3), ("Di", 4), ("Fr", 1), ("Fr", 2)],
}


def tendencies(rng: random.Random) -> list[tuple[str, float, float, float]]:
    students, _, _ = seed.generate(PER_CLASS, GRADE_SEED)
    out = []
    for s in sorted(students, key=lambda s: s.username):
        ill, skip, late = TENDENCY[s.archetype]
        jitter = rng.uniform(0.6, 1.4)          # no two students of a type identical
        out.append((s.username, round(ill * jitter, 4), round(skip * jitter, 4),
                    round(late * rng.uniform(0.6, 1.4), 4)))
    return out


def timetable_sql() -> str:
    lines = [
        "-- ===========================================================================",
        f"-- sim_timetable.sql - weekly timetable for the sim class_subjects ({date.today()})",
        "-- Inserts only for a class_subject that has NO timetable entry yet.",
        "-- Run before: python -m scripts.generate_lessons",
        "-- ===========================================================================",
        "",
        "USE edudevice_db;",
        "",
    ]
    for cs_id, slots in TIMETABLE.items():
        rows = " UNION ALL ".join(
            f"SELECT {cs_id} AS cs, '{wd}' AS wd, '{PERIODS[p][0]}' AS st, '{PERIODS[p][1]}' AS en"
            for wd, p in slots)
        lines += [
            f"INSERT INTO timetable (class_subject_id, weekday, start_time, end_time, room)",
            f"SELECT v.cs, v.wd, v.st, v.en, 'SIM' FROM ({rows}) v",
            f"WHERE EXISTS (SELECT 1 FROM class_subjects WHERE id = {cs_id})",
            f"  AND NOT EXISTS (SELECT 1 FROM timetable WHERE class_subject_id = {cs_id});",
            "",
        ]
    lines += [
        "-- Kontrolle: Stunden pro Woche je Fach",
        "SELECT class_subject_id, COUNT(*) AS per_week FROM timetable",
        f"WHERE class_subject_id IN ({', '.join(map(str, TIMETABLE))}) GROUP BY class_subject_id;",
    ]
    return "\n".join(lines) + "\n"


def attendance_sql(rows) -> str:
    values = ",\n".join(f"  ('{u}', {ill}, {skip}, {late})" for u, ill, skip, late in rows)
    return f"""-- ===========================================================================
-- sim_attendance.sql - simulated attendance for the sim students ({date.today()})
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
{values};

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
WHERE u.username LIKE 'sim\\_%'
GROUP BY a.status;
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent),
                    help="folder for the two SQL files (default: the dsp folder)")
    ap.add_argument("--seed", type=int, default=GRADE_SEED + 1)
    args = ap.parse_args()

    rows = tendencies(random.Random(args.seed))
    out = Path(args.out)
    (out / "sim_timetable.sql").write_text(timetable_sql(), encoding="utf-8")
    (out / "sim_attendance.sql").write_text(attendance_sql(rows), encoding="utf-8")
    print(f"wrote {out / 'sim_timetable.sql'}")
    print(f"wrote {out / 'sim_attendance.sql'}  ({len(rows)} students)")


if __name__ == "__main__":
    main()
