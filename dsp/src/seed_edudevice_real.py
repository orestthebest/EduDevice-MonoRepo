"""
seed_edudevice_real.py — demo data generator for the REAL edudevice_db schema.

Replaces the earlier generator, which targeted a schema I had guessed wrong.
Everything here is built from the actual DDL: users/role='schueler' instead of a
students table, class_subject_id instead of subject_id, the grades.category enum,
and the period_grades CHECK that fixes M1/M2 to a trimester and M3/FINAL to the year.

Design rules it obeys
---------------------
* No hardcoded ids. Users are inserted with AUTO_INCREMENT assigning ids; every
  child row finds its student by joining on the unique `username`. Nothing can
  collide with existing rows.
* Existing master data is reused, never re-created. The classes, subjects and
  class_subjects already on the server are referenced by the ids the recon
  reported; the script inserts none of them.
* Every sim row is identifiable: username `sim_NNNN`, email `@sim.edudevice.local`.
* Real bcrypt hashes of random passwords that are generated, used once and
  discarded, so no sim account is loginable but the hash column is still valid
  and the API returns 401 rather than crashing.
* Only `grades` rows are written, never `period_grades`. The M1/M2/M3 values are
  derived from these by the pipeline; seeding them directly would fake the output
  of the very component the Ziel is about.

Output
------
  sim_seed_edudevice.sql    the file Gridi loads
  sim_ground_truth.json     the answer key: archetype per sim student
  sim_preview.csv           a flat view of every grade row, for eyeballing

Usage
-----
  python seed_edudevice_real.py --per-class 10
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import bcrypt

# --- facts taken from the recon output, not guessed ---------------------------

SCHOOL_YEAR_ID = 1          # label '2026/27', 2026-09-07 .. 2027-07-02
YEAR_START = date(2026, 9, 7)
YEAR_END = date(2027, 7, 2)

# Trimester windows. NOT in the database yet - these are proposed, and Gridi must
# confirm them against the school calendar before the trimesters rows are created.
TRIMESTER_WINDOWS = {
    1: (date(2026, 9, 7), date(2026, 12, 4)),
    2: (date(2026, 12, 7), date(2027, 3, 19)),
    3: (date(2027, 3, 22), date(2027, 7, 2)),
}

# class_subjects that already exist. The two "Test" rows are deliberately excluded.
# (class_subject_id, class_id, class_name, subject_name)
CLASS_SUBJECTS = [
    (2, 2, "4A", "Mathematik"),
    (6, 2, "4A", "SEW"),
    (5, 1, "5B", "INSY"),
    (3, 1, "5B", "Mathematics"),
    (4, 1, "5B", "Software Development"),
]

# grades.category enum, split by which period component it rolls up into.
M1_CATEGORIES = [
    ("mini_test", 1.00),
    ("oral", 1.00),
    ("homework", 0.50),
    ("classwork", 1.00),
    ("presentation", 1.00),
    ("participation", 0.50),
    ("behaviour", 0.50),
]
M2_CATEGORY = ("schularbeit", 2.00)
M3_CATEGORY = ("project", 1.00)

GRADE_MIN, GRADE_MAX = 4.0, 10.0

FIRST_NAMES = [
    "Arben", "Besa", "Dritan", "Elira", "Festim", "Gentiana", "Ilir", "Jeta",
    "Kujtim", "Lindita", "Mirjeta", "Nikoll", "Ornela", "Petrit", "Rozafa",
    "Sokol", "Teuta", "Valon", "Xhemal", "Zana", "Agron", "Blerta", "Dardan",
    "Fatos", "Hana", "Krenar", "Luljeta", "Marsel", "Nora", "Endrit",
]
LAST_NAMES = [
    "Hoxha", "Krasniqi", "Shala", "Berisha", "Gjoni", "Kola", "Prifti",
    "Dervishi", "Marku", "Lleshi", "Bardhi", "Cela", "Hasani", "Zefi",
    "Pllumi", "Nikaj", "Tusha", "Vata", "Rexha", "Doda",
]

ARCHETYPES = {
    # "failing" exists because without it the dataset has almost no negative
    # cases: a student who declines from 7 to 4 still averages a pass over the
    # year. A real class has one or two who are genuinely below the line all
    # year, and the risk model has nothing to learn without them.
    "failing": (10, "Below the pass mark most of the year - the true positives"),
    "steady": (30, "Holds roughly level all year"),
    "improving": (20, "Climbs across the trimesters"),
    "declining": (16, "Falls across the trimesters - the risk model should flag these"),
    "volatile": (14, "Swings without a trend - should NOT be flagged as risk"),
    "sudden_drop": (12, "Level, then one sharp fall - EWMA should flag the trimester"),
    "incomplete": (8, "Year in progress: later trimesters not yet graded"),
}


def clamp(v: float) -> float:
    """Clamp to the scale and snap to a half step (grades.value is decimal(3,1))."""
    v = max(GRADE_MIN, min(GRADE_MAX, v))
    return round(v * 2) / 2


@dataclass
class SimStudent:
    username: str
    first_name: str
    last_name: str
    email: str
    password_hash: str
    class_id: int
    class_name: str
    archetype: str


@dataclass
class SimGrade:
    username: str
    class_subject_id: int
    category: str
    weight: float
    value: float
    on: date


def _level_series(rng: random.Random, archetype: str, base: float):
    """Per-trimester ability level, and which trimester (if any) holds a planted drop."""
    drop_at = None
    if archetype == "failing":
        levels = {t: base + rng.uniform(-0.5, 0.3) for t in (1, 2, 3)}
    elif archetype == "steady":
        levels = {t: base + rng.uniform(-0.4, 0.4) for t in (1, 2, 3)}
    elif archetype == "improving":
        step = rng.uniform(0.7, 1.3)
        levels = {t: base + (t - 1) * step + rng.uniform(-0.3, 0.3) for t in (1, 2, 3)}
    elif archetype == "declining":
        step = rng.uniform(0.7, 1.3)
        levels = {t: base - (t - 1) * step + rng.uniform(-0.3, 0.3) for t in (1, 2, 3)}
    elif archetype == "volatile":
        levels = {t: base + rng.choice([-1.8, -1.0, 1.0, 1.8]) for t in (1, 2, 3)}
    elif archetype == "sudden_drop":
        drop_at = rng.choice([2, 3])
        levels = {}
        for t in (1, 2, 3):
            v = base + rng.uniform(-0.3, 0.3)
            if t >= drop_at:
                v -= rng.uniform(2.5, 3.5)
            levels[t] = v
    elif archetype == "incomplete":
        graded_until = rng.choice([1, 2])
        levels = {
            t: (base + rng.uniform(-0.4, 0.4) if t <= graded_until else None)
            for t in (1, 2, 3)
        }
    else:
        raise ValueError(archetype)
    return levels, drop_at


def _date_in(rng: random.Random, trimester: int) -> date:
    start, end = TRIMESTER_WINDOWS[trimester]
    d = start + timedelta(days=rng.randrange((end - start).days))
    while d.weekday() >= 5:            # keep grades on school days
        d += timedelta(days=1)
    return min(d, end)


def generate(per_class: int, seed: int):
    rng = random.Random(seed)

    by_class: dict[int, list] = {}
    for cs_id, class_id, class_name, subject in CLASS_SUBJECTS:
        by_class.setdefault(class_id, []).append((cs_id, class_name, subject))

    names = list(ARCHETYPES)

    # Assign archetypes by proportional allocation rather than independent random
    # draws. Drawing each student independently leaves the counts to luck, and an
    # unlucky seed can produce five declining students out of fifty - too few for
    # the risk classifier to learn anything from. Largest-remainder apportionment
    # makes the counts match the intended mix exactly, every time.
    total_students = per_class * len(by_class)
    total_weight = sum(ARCHETYPES[a][0] for a in names)
    exact = {a: total_students * ARCHETYPES[a][0] / total_weight for a in names}
    alloc = {a: int(exact[a]) for a in names}
    remainder = total_students - sum(alloc.values())
    for a in sorted(names, key=lambda x: exact[x] - int(exact[x]), reverse=True)[:remainder]:
        alloc[a] += 1

    pool = [a for a in names for _ in range(alloc[a])]
    rng.shuffle(pool)

    students: list[SimStudent] = []
    grades: list[SimGrade] = []
    truth: list[dict] = []

    used = set()
    n = 0

    for class_id, subjects in sorted(by_class.items()):
        class_name = subjects[0][1]
        for _ in range(per_class):
            n += 1
            while True:
                fn, ln = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
                if (fn, ln) not in used:
                    used.add((fn, ln))
                    break

            username = f"sim_{n:04d}"
            raw_pw = secrets.token_urlsafe(24)       # generated, used once, discarded
            pw_hash = bcrypt.hashpw(raw_pw.encode(), bcrypt.gensalt(rounds=12)).decode()
            del raw_pw

            archetype = pool.pop()
            student = SimStudent(
                username=username,
                first_name=fn,
                last_name=ln,
                email=f"{username}@sim.edudevice.local",
                password_hash=pw_hash,
                class_id=class_id,
                class_name=class_name,
                archetype=archetype,
            )
            students.append(student)

            # A failing student sits near the floor of the scale; everyone else
            # is drawn from the normal range.
            ability = (rng.uniform(4.1, 5.1) if archetype == "failing"
                       else rng.uniform(5.5, 9.0))
            planted = {}

            for cs_id, _cname, subject in subjects:
                base = ability + rng.uniform(-0.8, 0.8)
                levels, drop_at = _level_series(rng, archetype, base)
                if drop_at:
                    planted[subject] = drop_at

                # M3 Projekt: once a year. The teacher may grade it in any trimester -
                # only the DATE moves, because period_grades forces M3 to the year level.
                m3_trimester = rng.choice([1, 2, 3])
                graded = [t for t, lv in levels.items() if lv is not None]
                if m3_trimester not in graded:
                    m3_trimester = graded[-1] if graded else None

                for t in (1, 2, 3):
                    level = levels[t]
                    if level is None:
                        continue

                    # M1 Mitarbeit: several small marks across the trimester.
                    for cat, w in rng.sample(M1_CATEGORIES, k=rng.randint(4, 6)):
                        grades.append(
                            SimGrade(
                                username, cs_id, cat, w,
                                clamp(level + rng.uniform(-1.0, 1.0)),
                                _date_in(rng, t),
                            )
                        )

                    # M2 Schularbeit: one per trimester.
                    cat, w = M2_CATEGORY
                    grades.append(
                        SimGrade(
                            username, cs_id, cat, w,
                            clamp(level + rng.uniform(-1.2, 1.2)),
                            _date_in(rng, t),
                        )
                    )

                    # M3 Projekt: exactly once in the year, dated in its trimester.
                    if t == m3_trimester:
                        cat, w = M3_CATEGORY
                        grades.append(
                            SimGrade(
                                username, cs_id, cat, w,
                                clamp(level + rng.uniform(-0.8, 1.2)),
                                _date_in(rng, t),
                            )
                        )

            truth.append(
                {
                    "username": username,
                    "name": f"{fn} {ln}",
                    "class": class_name,
                    "archetype": archetype,
                    "archetype_meaning": ARCHETYPES[archetype][1],
                    "ability_level": round(ability, 2),
                    "planted_drops": planted,
                }
            )

    return students, grades, truth


# --- SQL emission -------------------------------------------------------------

def _q(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def write_sql(path: Path, students, grades, per_class: int, seed: int) -> None:
    L: list[str] = []
    a = L.append

    a("-- ===========================================================================")
    a("-- sim_seed_edudevice.sql - demo data for edudevice_db")
    a(f"-- generated {date.today().isoformat()}  seed={seed}  per_class={per_class}")
    a("--")
    a(f"-- {len(students)} sim students, {len(grades)} grade rows.")
    a("--")
    a("-- Every row this file creates is identifiable:")
    a("--     users.username  LIKE 'sim\\_%'")
    a("--     users.email     LIKE '%@sim.edudevice.local'")
    a("--")
    a("-- It inserts into users, student_classes, class_subject_students and grades")
    a("-- ONLY. It creates no classes, subjects or class_subjects - the existing ones")
    a("-- are referenced by id. It writes no period_grades: those are computed from")
    a("-- these grades by the pipeline.")
    a("--")
    a("-- No id is hardcoded. Students are matched by username after AUTO_INCREMENT")
    a("-- assigns their ids, so nothing can collide with existing rows.")
    a("--")
    a("-- PREREQUISITE: the trimesters table is empty. It is not required for this")
    a("-- file to load, but period_grades cannot be written until it is filled.")
    a("-- See sim_trimesters.sql, and confirm the dates first.")
    a("-- ===========================================================================")
    a("")
    a("START TRANSACTION;")
    a("")

    a("-- --- 1. sim students --------------------------------------------------------")
    a("-- password_hash is a real bcrypt hash (cost 12) of a random password that was")
    a("-- generated, used once and discarded. No one can log in as these accounts, and")
    a("-- the API returns a clean 401 rather than crashing on a malformed hash.")
    a("INSERT INTO users (first_name, last_name, username, role, email, password_hash) VALUES")
    rows = [
        f"  ({_q(s.first_name)}, {_q(s.last_name)}, {_q(s.username)}, 'schueler', "
        f"{_q(s.email)}, {_q(s.password_hash)})"
        for s in students
    ]
    a(",\n".join(rows) + ";")
    a("")

    a("-- --- 2. class membership ----------------------------------------------------")
    by_class: dict[int, list[str]] = {}
    for s in students:
        by_class.setdefault(s.class_id, []).append(s.username)
    for class_id, unames in sorted(by_class.items()):
        lst = ", ".join(_q(u) for u in unames)
        a(f"INSERT INTO student_classes (student_id, class_id)")
        a(f"SELECT u.id, {class_id} FROM users u WHERE u.username IN ({lst});")
        a("")

    a("-- --- 3. subject enrolment ---------------------------------------------------")
    for cs_id, class_id, class_name, subject in CLASS_SUBJECTS:
        unames = by_class.get(class_id, [])
        if not unames:
            continue
        lst = ", ".join(_q(u) for u in unames)
        a(f"-- class_subject {cs_id}: {class_name} / {subject}")
        a(f"INSERT INTO class_subject_students (class_subject_id, student_id)")
        a(f"SELECT {cs_id}, u.id FROM users u WHERE u.username IN ({lst});")
        a("")

    a("-- --- 4. grades --------------------------------------------------------------")
    a("-- Staged in a temporary table so student ids are resolved by username in one")
    a("-- INSERT ... SELECT instead of being written by hand.")
    a("-- The username column is pinned to utf8mb4_unicode_ci to match")
    a("-- users.username. Without it the temporary table inherits the DATABASE")
    a("-- default collation, which on MySQL 8 is utf8mb4_0900_ai_ci, and the join")
    a("-- below dies with 'ERROR 1267 Illegal mix of collations'.")
    a("CREATE TEMPORARY TABLE sim_stage_grades (")
    a("  username         VARCHAR(50) COLLATE utf8mb4_unicode_ci NOT NULL,")
    a("  class_subject_id INT UNSIGNED  NOT NULL,")
    a("  category         VARCHAR(20)   NOT NULL,")
    a("  weight           DECIMAL(4,2)  NOT NULL,")
    a("  value            DECIMAL(3,1)  NOT NULL,")
    a("  date             DATE          NOT NULL")
    a(") ENGINE=InnoDB;")
    a("")

    CHUNK = 500
    for i in range(0, len(grades), CHUNK):
        chunk = grades[i : i + CHUNK]
        a("INSERT INTO sim_stage_grades (username, class_subject_id, category, weight, value, date) VALUES")
        a(
            ",\n".join(
                f"  ({_q(g.username)}, {g.class_subject_id}, {_q(g.category)}, "
                f"{g.weight:.2f}, {g.value:.1f}, {_q(g.on.isoformat())})"
                for g in chunk
            )
            + ";"
        )
        a("")

    a("INSERT INTO grades (student_id, class_subject_id, category, weight, value, date)")
    a("SELECT u.id, s.class_subject_id, s.category, s.weight, s.value, s.date")
    a("FROM sim_stage_grades s")
    a("-- The explicit COLLATE takes precedence over both columns' own collations,")
    a("-- so this join cannot raise 1267 whatever the server default happens to be.")
    a("JOIN users u ON u.username = s.username COLLATE utf8mb4_unicode_ci;")
    a("")
    a("DROP TEMPORARY TABLE sim_stage_grades;")
    a("")

    a("COMMIT;")
    a("")
    a("-- --- 5. verification --------------------------------------------------------")
    a("-- Expected: students = %d, grades = %d" % (len(students), len(grades)))
    a("SELECT 'sim students' AS what, COUNT(*) AS n FROM users WHERE username LIKE 'sim\\_%'")
    a("UNION ALL SELECT 'sim enrolments', COUNT(*) FROM class_subject_students css")
    a("  JOIN users u ON u.id = css.student_id WHERE u.username LIKE 'sim\\_%'")
    a("UNION ALL SELECT 'sim grades', COUNT(*) FROM grades g")
    a("  JOIN users u ON u.id = g.student_id WHERE u.username LIKE 'sim\\_%';")
    a("")
    a("-- Nothing outside the sim set should appear here.")
    a("SELECT id, username, email, role FROM users WHERE username LIKE 'sim\\_%' ORDER BY id LIMIT 5;")
    a("")
    a("")
    a("-- ===========================================================================")
    a("-- CLEANUP - DESTRUCTIVE. Deliberately left commented out.")
    a("--")
    a("-- Before running any of this: take a backup.")
    a("--   sudo mysqldump --defaults-file=/etc/mysql/debian.cnf edudevice_db > ~/backup.sql")
    a("--")
    a("-- The recon confirmed every FK from users that a SIM STUDENT touches is")
    a("-- ON DELETE CASCADE, so the single DELETE below removes their grades,")
    a("-- enrolments, class memberships, sessions, notifications, messages,")
    a("-- risk_assessments, alerts and period_grades with them.")
    a("--")
    a("-- It is only safe while sim accounts stay students. Three FKs into users are")
    a("-- NO ACTION - class_subjects.teacher_id, materials.uploaded_by and")
    a("-- quizzes.created_by - so if a sim account is ever made a teacher, assigned")
    a("-- as a subject teacher, or used to upload a material or create a quiz, this")
    a("-- DELETE will fail with a constraint error instead.")
    a("--")
    a("-- Check what would go first:")
    a("--   SELECT COUNT(*) FROM users WHERE username LIKE 'sim\\\\_%';")
    a("--")
    a("-- Note the escaped underscore. Without it, 'sim_%' is a wildcard that would")
    a("-- also match a real account whose name happened to begin 'sim' + any char.")
    a("--")
    a("-- DELETE FROM users WHERE username LIKE 'sim\\\\_%';")
    a("-- ===========================================================================")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_trimesters_sql(path: Path) -> None:
    L = [
        "-- ===========================================================================",
        "-- sim_trimesters.sql - master data, NOT demo data.",
        "--",
        "-- The trimesters table is empty. period_grades requires a trimester_id for",
        "-- every M1 and M2 row, so nothing can be computed until these exist.",
        "--",
        "-- THE DATES BELOW ARE A PROPOSAL, derived from the school year window",
        f"-- ({YEAR_START} .. {YEAR_END}) by splitting it in three. They are NOT the",
        "-- school's real trimester boundaries. Confirm them before running this.",
        "-- ===========================================================================",
        "",
    ]
    for num, (start, end) in TRIMESTER_WINDOWS.items():
        L.append(
            f"INSERT INTO trimesters (school_year_id, number, start_date, end_date) "
            f"VALUES ({SCHOOL_YEAR_ID}, {num}, '{start}', '{end}');"
        )
    L += ["", "SELECT * FROM trimesters ORDER BY number;", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--out", type=Path, default=Path("sim_out"))
    args = ap.parse_args()

    students, grades, truth = generate(args.per_class, args.seed)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    write_sql(out / "sim_seed_edudevice.sql", students, grades, args.per_class, args.seed)
    write_trimesters_sql(out / "sim_trimesters.sql")

    (out / "sim_ground_truth.json").write_text(
        json.dumps(
            {
                "seed": args.seed,
                "school_year_id": SCHOOL_YEAR_ID,
                "trimester_windows": {
                    str(k): [v[0].isoformat(), v[1].isoformat()]
                    for k, v in TRIMESTER_WINDOWS.items()
                },
                "archetypes": {k: v[1] for k, v in ARCHETYPES.items()},
                "students": truth,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with (out / "sim_preview.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["username", "class_subject_id", "category", "weight", "value", "date"])
        for g in grades:
            w.writerow([g.username, g.class_subject_id, g.category, f"{g.weight:.2f}",
                        f"{g.value:.1f}", g.on.isoformat()])

    counts: dict[str, int] = {}
    for t in truth:
        counts[t["archetype"]] = counts.get(t["archetype"], 0) + 1
    print(f"{len(students)} sim students, {len(grades)} grade rows")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:13} {v}")


if __name__ == "__main__":
    main()
