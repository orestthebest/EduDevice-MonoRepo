"""
EduDevice - synthetic school data generator.

Fills the EduDevice MySQL schema with realistic but invented data, so the
pipeline can be run, demonstrated and developed end to end before real
student data exists.

IMPORTANT - what this data is and is not
----------------------------------------
This data is generated from rules that THIS FILE defines. A model trained on
it will rediscover those rules, so any accuracy measured here is circular and
must never be reported as evidence that the system works. The empirical
results come from OULAD.

What it IS good for:
  - proving the pipeline runs against the real schema
  - giving the dashboard and the device display real numbers to show
  - demonstrating the system at the presentation

Structure produced
------------------
  8 school years (7 finished, 1 in progress)
  20 classes per year: levels 6-9 with 3 classes each, levels 10-13 with 2
  ~28 students per lower class, ~20 per upper class -> ~496 per year
  10 subjects, 3 trimesters, M1/M2/M3 grades, lessons, attendance, excuses,
  homework.

Students advance one level per year, so every student has a multi-year
history. Moving from level 9 to level 10 the cohort shrinks from 3 classes to
2, as it does at a real HTL when part of the year group leaves after the
lower cycle.

Built-in cases, so every part of the system has something real to find:
  weak, sudden_drop, absence_problem, recovery, normal - redrawn each year,
  so a student can have one bad year and recover the next.

Usage
-----
    python generate_school_data.py --url mysql+pymysql://user:pw@host/db --wipe
    python generate_school_data.py --years 3 --wipe        # smaller test set
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass, field
import os

import numpy as np
from sqlalchemy import create_engine, text

from rules import TRIMESTERS, SubjectState, final_grade, weighted_average

SEED = 42

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

N_YEARS = 8                         # how many school years of history
FIRST_YEAR = 2019                   # the first year starts in September 2019

LOWER_LEVELS = [6, 7, 8, 9]         # Unterstufe: 3 classes each
UPPER_LEVELS = [10, 11, 12, 13]     # Oberstufe: 2 classes each
CLASSES_PER_LEVEL = {**{l: 3 for l in LOWER_LEVELS}, **{l: 2 for l in UPPER_LEVELS}}
STUDENTS_PER_CLASS = {**{l: 28 for l in LOWER_LEVELS}, **{l: 20 for l in UPPER_LEVELS}}

SUBJECTS = ["Mathematik", "Deutsch", "Englisch", "Physik", "Informatik",
            "Werkstaette", "Geschichte", "Chemie", "Albanisch", "Sport"]

# Subjects that are genuinely harder pull grades down a little
SUBJECT_DIFFICULTY = {"Mathematik": -0.8, "Physik": -0.6, "Werkstaette": -0.3,
                      "Chemie": -0.5, "Informatik": -0.2, "Deutsch": -0.1,
                      "Englisch": 0.0, "Geschichte": 0.2, "Albanisch": 0.3,
                      "Sport": 0.9}

# M1 entry categories: (category, teacher weight, entries per trimester)
M1_PLAN = [("homework", 1.0, 3), ("mini_test", 2.0, 2), ("oral", 1.5, 1),
           ("classwork", 1.5, 1), ("participation", 1.0, 1)]
M2_PER_TRIMESTER = 2                # Schularbeiten

LESSONS_PER_WEEK = 2
HOLIDAYS = [((12, 23), (1, 6)), ((4, 1), (4, 8))]   # (month, day) ranges

N_TEACHERS = 40

# Share of students drawn into each profile, redrawn every school year
P_WEAK = 0.15
P_SUDDEN_DROP = 0.06
P_ABSENCE_PROBLEM = 0.08
P_RECOVERY = 0.05


# ---------------------------------------------------------------------
# Student model
# ---------------------------------------------------------------------

@dataclass
class Student:
    """A student, with a baseline that persists across school years."""
    user_id: int = 0
    first_name: str = ""
    last_name: str = ""
    baseline: float = 7.5              # long-run ability, drifts slowly
    subject_offsets: dict = field(default_factory=dict)
    # Per-year state, refreshed by new_year()
    ability: float = 7.5
    diligence: float = 0.9
    absence_rate: float = 0.05
    profile: str = "normal"
    drop_after: float | None = None
    drop_size: float = 0.0

    def new_year(self, rng: np.random.Generator) -> None:
        """Draw this student's situation for one school year."""
        # The baseline drifts a little from year to year
        self.baseline = float(np.clip(self.baseline + rng.normal(0, 0.35), 4.1, 9.8))

        roll = rng.random()
        if roll < P_WEAK:
            self.profile = "weak"
            self.ability = self.baseline - abs(rng.normal(1.6, 0.5))
        elif roll < P_WEAK + P_SUDDEN_DROP:
            self.profile = "sudden_drop"
            self.ability = self.baseline
        elif roll < P_WEAK + P_SUDDEN_DROP + P_ABSENCE_PROBLEM:
            self.profile = "absence_problem"
            self.ability = self.baseline - 0.5
        elif roll < P_WEAK + P_SUDDEN_DROP + P_ABSENCE_PROBLEM + P_RECOVERY:
            self.profile = "recovery"
            self.ability = self.baseline - 1.2
        else:
            self.profile = "normal"
            self.ability = self.baseline

        self.ability = float(np.clip(self.ability, 4.1, 9.9))
        self.diligence = float(np.clip(rng.normal(0.55 + 0.05 * self.ability, 0.12), 0.1, 1.0))
        self.absence_rate = float(np.clip(rng.normal(0.08, 0.05), 0.0, 0.5))
        self.drop_after, self.drop_size = None, 0.0

        if self.profile == "sudden_drop":
            self.drop_after = float(rng.uniform(0.3, 0.6))
            self.drop_size = float(rng.uniform(-3.0, -1.8))
        elif self.profile == "absence_problem":
            self.absence_rate = float(rng.uniform(0.18, 0.42))
            self.diligence *= 0.6
        elif self.profile == "weak":
            self.diligence *= 0.7

    def ability_at(self, progress: float, subject: str) -> float:
        """Expected grade level at a point in the year, in one subject."""
        value = self.ability + self.subject_offsets.get(subject, 0.0)
        value += SUBJECT_DIFFICULTY.get(subject, 0.0)
        if self.drop_after is not None and progress >= self.drop_after:
            value += self.drop_size
        if self.profile == "recovery":
            value += 2.0 * progress
        return value


FIRST_NAMES = ["Arben", "Besa", "Dritan", "Elira", "Fatjon", "Gentiana", "Ilir",
               "Jeta", "Klaudia", "Leon", "Mirela", "Nora", "Orest", "Petrit",
               "Qendresa", "Rina", "Sokol", "Teuta", "Urim", "Vjosa", "Xhemal",
               "Ylli", "Zana", "Adrian", "Blerta", "Donika", "Endrit", "Flora",
               "Genti", "Hana", "Ismail", "Jonida", "Kreshnik", "Lindita",
               "Marjan", "Nertila", "Oltion", "Pranvera", "Rexhep", "Suela"]
LAST_NAMES = ["Hoxha", "Kelmendi", "Berisha", "Shala", "Krasniqi", "Gashi",
              "Morina", "Bytyqi", "Rexhepi", "Zeqiri", "Dervishi", "Bashi",
              "Kuci", "Bushati", "Ndoja", "Prenga", "Marku", "Gjoka", "Lleshi",
              "Nikolla", "Dedaj", "Camaj", "Luca", "Mhilli", "Pepa"]


# ---------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------

def school_year_dates(start_year: int) -> tuple[dt.date, dt.date]:
    """First Monday of September to the last Friday of June."""
    start = dt.date(start_year, 9, 1)
    while start.weekday() != 0:
        start += dt.timedelta(days=1)
    end = dt.date(start_year + 1, 6, 30)
    while end.weekday() != 4:
        end -= dt.timedelta(days=1)
    return start, end


def in_holiday(day: dt.date) -> bool:
    for (m1, d1), (m2, d2) in HOLIDAYS:
        if m2 < m1:                                      # spans the new year
            if day >= dt.date(day.year, m1, d1) or day <= dt.date(day.year, m2, d2):
                return True
        elif dt.date(day.year, m1, d1) <= day <= dt.date(day.year, m2, d2):
            return True
    return False


def trimester_bounds(start: dt.date, end: dt.date) -> list[tuple[dt.date, dt.date]]:
    length = (end - start).days
    cuts = [start + dt.timedelta(days=int(length * i / TRIMESTERS))
            for i in range(TRIMESTERS + 1)]
    return [(cuts[i], cuts[i + 1] - dt.timedelta(days=1)) for i in range(TRIMESTERS)]


def grade_from(rng: np.random.Generator, level: float, noise: float = 1.0) -> int:
    return int(np.clip(round(level + rng.normal(0, noise)), 4, 10))


# ---------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------

class Generator:
    """Builds the whole school, one year at a time.

    Everything that spans years (users, classes, timetable) is written first;
    the bulky per-lesson data is then written year by year and freed, so
    memory stays bounded no matter how many years are generated.
    """

    def __init__(self, engine, seed: int = SEED, n_years: int = N_YEARS,
                 today: dt.date | None = None):
        self.engine = engine
        self.rng = np.random.default_rng(seed)
        self.n_years = n_years
        self.today = today or dt.date.today()
        self.counts: dict[str, int] = {}

    # -- database helpers ----------------------------------------------------
    def insert(self, table: str, columns: list[str], rows: list[tuple]) -> None:
        """Bulk insert through the raw driver.

        pymysql rewrites executemany on a simple INSERT ... VALUES into one
        multi-row statement, which is roughly an order of magnitude faster
        than one round trip per row. At a few million attendance rows that is
        the difference between a minute and half an hour.
        """
        if not rows:
            return
        sql = (f"INSERT INTO {table} ({', '.join(columns)}) "
               f"VALUES ({', '.join(['%s'] * len(columns))})")
        raw = self.engine.raw_connection()
        try:
            cursor = raw.cursor()
            for i in range(0, len(rows), 20000):
                cursor.executemany(sql, rows[i:i + 20000])
            raw.commit()
        finally:
            raw.close()
        self.counts[table] = self.counts.get(table, 0) + len(rows)

    def ids_of(self, table: str, where: str = "") -> list[int]:
        clause = f" WHERE {where}" if where else ""
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(
                text(f"SELECT id FROM {table}{clause} ORDER BY id"))]

    def wipe(self) -> None:
        tables = ["email_log", "alerts", "risk_assessments", "notifications",
                  "messages", "sessions", "quiz_results", "quizzes",
                  "period_grades", "grades", "homework_confirmations", "homework",
                  "attendance", "excuses", "lessons", "timetable", "materials",
                  "class_subject_students", "class_subjects", "student_classes",
                  "classes", "trimesters", "school_years", "subjects", "users"]
        # DELETE rather than TRUNCATE: it needs no DROP privilege, so the
        # ordinary application user can run it. Tables the installed schema
        # does not have are skipped rather than treated as an error.
        with self.engine.connect() as conn:
            existing = {r[0] for r in conn.execute(text("SHOW TABLES"))}
        with self.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in tables:
                if table in existing:
                    conn.execute(text(f"DELETE FROM {table}"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        missing = [t for t in tables if t not in existing]
        print("wiped all tables" + (f" (not present: {', '.join(missing)})" if missing else ""))

    # -- the skeleton: people, classes, timetable ----------------------------
    def build_structure(self) -> None:
        rng = self.rng
        self.levels = LOWER_LEVELS + UPPER_LEVELS

        # School years ------------------------------------------------------
        self.years = []
        for i in range(self.n_years):
            start_year = FIRST_YEAR + i
            start, end = school_year_dates(start_year)
            label = f"{start_year}/{str(start_year + 1)[2:]}"
            self.years.append({"label": label, "start": start, "end": end,
                               "finished": end <= self.today})
        self.insert("school_years", ["label", "start_date", "end_date"],
                    [(y["label"], y["start"], y["end"]) for y in self.years])
        year_ids = dict(zip([y["label"] for y in self.years], self.ids_of("school_years")))
        for y in self.years:
            y["id"] = year_ids[y["label"]]

        # Trimesters --------------------------------------------------------
        rows, keys = [], []
        for y in self.years:
            for number, (t_start, t_end) in enumerate(
                    trimester_bounds(y["start"], y["end"]), start=1):
                rows.append((y["id"], number, t_start, t_end))
                keys.append((y["label"], number))
        self.insert("trimesters", ["school_year_id", "number", "start_date", "end_date"], rows)
        self.trimester_ids = dict(zip(keys, self.ids_of("trimesters")))
        self.trimester_dates = {k: (r[2], r[3]) for k, r in zip(keys, rows)}

        # Teachers ----------------------------------------------------------
        teachers = [(FIRST_NAMES[(i * 7) % len(FIRST_NAMES)],
                     LAST_NAMES[(i * 3) % len(LAST_NAMES)],
                     f"lehrer{i+1}", "lehrkraft",
                     f"lehrer{i+1}@edudevice.al", "$2y$10$demo")
                    for i in range(N_TEACHERS)]
        self.insert("users", ["first_name", "last_name", "username", "role",
                              "email", "password_hash"], teachers)
        self.teacher_ids = self.ids_of("users")

        # Cohorts -----------------------------------------------------------
        # A cohort is a year group. It sits at level 6 in its entry year and
        # advances one level per year. Entry offsets from -7 to n_years-1
        # cover every (year, level) pair in the window.
        lower_size = CLASSES_PER_LEVEL[6] * STUDENTS_PER_CLASS[6]
        upper_size = CLASSES_PER_LEVEL[10] * STUDENTS_PER_CLASS[10]

        self.cohorts: dict[int, list[Student]] = {}
        student_rows, student_objs = [], []
        for entry in range(-(len(self.levels) - 1), self.n_years):
            # Does this cohort ever sit in the Unterstufe inside our window?
            visible = [y for y in range(self.n_years)
                       if 0 <= y - entry < len(self.levels)]
            needs_lower = any(self.levels[y - entry] <= 9 for y in visible)
            size = lower_size if needs_lower else upper_size

            group = []
            for _ in range(size):
                student = Student(
                    first_name=FIRST_NAMES[int(rng.integers(len(FIRST_NAMES)))],
                    last_name=LAST_NAMES[int(rng.integers(len(LAST_NAMES)))],
                    baseline=float(np.clip(rng.normal(7.6, 1.2), 4.2, 9.8)),
                )
                student.subject_offsets = {s: float(rng.normal(0, 0.7)) for s in SUBJECTS}
                group.append(student)
                student_objs.append(student)
                n = len(student_rows) + 1
                student_rows.append((student.first_name, student.last_name,
                                     f"{student.first_name.lower()}.{student.last_name.lower()}{n}",
                                     "schueler", f"s{n}@edudevice.al", "$2y$10$demo"))
            self.cohorts[entry] = group

        self.insert("users", ["first_name", "last_name", "username", "role",
                              "email", "password_hash"], student_rows)
        student_ids = self.ids_of("users", where="role = 'schueler'")
        for student, uid in zip(student_objs, student_ids):
            student.user_id = uid
        print(f"  {len(student_objs)} distinct students across {len(self.cohorts)} cohorts")

        # Subjects ----------------------------------------------------------
        self.insert("subjects", ["name"], [(s,) for s in SUBJECTS])
        subject_ids = dict(zip(SUBJECTS, self.ids_of("subjects")))

        # Classes, class_subjects, enrollments --------------------------------
        class_rows, class_keys = [], []
        for y in self.years:
            for level in self.levels:
                for letter in "ABC"[:CLASSES_PER_LEVEL[level]]:
                    class_rows.append((y["id"], f"{level}{letter}"))
                    class_keys.append((y["label"], level, letter))
        self.insert("classes", ["school_year_id", "name"], class_rows)
        self.class_ids = dict(zip(class_keys, self.ids_of("classes")))

        cs_rows, cs_keys = [], []
        for (label, level, letter), cid in self.class_ids.items():
            for s_index, subject in enumerate(SUBJECTS):
                teacher = self.teacher_ids[(s_index * 4 + level) % len(self.teacher_ids)]
                cs_rows.append((cid, subject_ids[subject], teacher))
                cs_keys.append((label, level, letter, subject))
        self.insert("class_subjects", ["class_id", "subject_id", "teacher_id"], cs_rows)
        self.cs_ids = dict(zip(cs_keys, self.ids_of("class_subjects")))

        # Who sits in which class: split the cohort across its classes --------
        self.roster: dict[tuple[str, int, str], list[Student]] = {}
        sc_rows, css_rows = [], []
        for y_index, y in enumerate(self.years):
            for level in self.levels:
                entry = y_index - (level - 6)
                cohort = self.cohorts.get(entry)
                if cohort is None:
                    continue
                per_class = STUDENTS_PER_CLASS[level]
                letters = "ABC"[:CLASSES_PER_LEVEL[level]]
                # Leaving level 9 for 10 the year group shrinks: the first
                # (3*28) students become (2*20), the rest leave the school.
                needed = per_class * len(letters)
                taking = cohort[:needed]
                for i, letter in enumerate(letters):
                    members = taking[i * per_class:(i + 1) * per_class]
                    self.roster[(y["label"], level, letter)] = members
                    cid = self.class_ids[(y["label"], level, letter)]
                    for student in members:
                        sc_rows.append((student.user_id, cid))
                        for subject in SUBJECTS:
                            css_rows.append((self.cs_ids[(y["label"], level, letter, subject)],
                                             student.user_id))
        self.insert("student_classes", ["student_id", "class_id"], sc_rows)
        self.insert("class_subject_students", ["class_subject_id", "student_id"], css_rows)

        # Timetable ------------------------------------------------------------
        tt_rows, tt_keys = [], []
        for (label, level, letter, subject), csid in self.cs_ids.items():
            for slot in range(LESSONS_PER_WEEK):
                weekday = ["Mo", "Di", "Mi", "Do", "Fr"][
                    (SUBJECTS.index(subject) + slot * 2 + level) % 5]
                hour = 8 + (SUBJECTS.index(subject) + slot) % 6
                tt_rows.append((csid, weekday, f"{hour:02d}:00:00", f"{hour:02d}:50:00",
                                f"R{100 + SUBJECTS.index(subject)}"))
                tt_keys.append((label, level, letter, subject, weekday))
        self.insert("timetable", ["class_subject_id", "weekday", "start_time",
                                  "end_time", "room"], tt_rows)
        self.timetable = list(zip(tt_keys, self.ids_of("timetable")))

    # -- per year: lessons, attendance, homework, grades ----------------------
    def build_year(self, y: dict) -> None:
        rng = self.rng
        label, start, end = y["label"], y["start"], y["end"]
        year_days = (end - start).days
        horizon = min(end, self.today)

        # Everyone in this year gets a fresh situation
        in_year = {s.user_id: s for level in self.levels
                   for letter in "ABC"[:CLASSES_PER_LEVEL[level]]
                   for s in self.roster.get((label, level, letter), [])}
        for student in in_year.values():
            student.new_year(rng)

        weekday_num = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4}

        # Lessons ------------------------------------------------------------
        lesson_rows, lesson_meta = [], []
        for (tt_label, level, letter, subject, weekday), ttid in self.timetable:
            if tt_label != label:
                continue
            day = start
            while day.weekday() != weekday_num[weekday]:
                day += dt.timedelta(days=1)
            while day <= horizon:
                if not in_holiday(day):
                    cancelled = rng.random() < 0.03
                    lesson_rows.append((ttid, day, cancelled))
                    lesson_meta.append((level, letter, day, cancelled))
                day += dt.timedelta(days=7)
        self.insert("lessons", ["timetable_id", "date", "cancelled"], lesson_rows)
        lesson_ids = self.ids_of("lessons", where=f"timetable_id IN "
                                 f"(SELECT id FROM timetable WHERE class_subject_id IN "
                                 f"(SELECT id FROM class_subjects WHERE class_id IN "
                                 f"(SELECT id FROM classes WHERE school_year_id = {y['id']})))")
        assert len(lesson_ids) == len(lesson_rows), "lesson id mismatch"

        # Absences: correlated within a day ------------------------------------
        # A sick day takes out every lesson that day, which is what makes the
        # 20% / 30% rule and the excuse system behave realistically. A smaller
        # per-lesson chance covers skipping a single hour.
        sick_days: dict[tuple[int, dt.date], bool] = {}
        attendance_rows, absence_keys = [], []
        for (level, letter, day, cancelled), lid in zip(lesson_meta, lesson_ids):
            if cancelled:
                continue
            for student in self.roster[(label, level, letter)]:
                key = (student.user_id, day)
                if key not in sick_days:
                    sick_days[key] = rng.random() < student.absence_rate * 0.8
                if sick_days[key] or rng.random() < student.absence_rate * 0.25:
                    absence_keys.append((student.user_id, day, lid))
                elif rng.random() < 0.04:
                    attendance_rows.append((student.user_id, lid, "verspaetet", None))
                else:
                    attendance_rows.append((student.user_id, lid, "anwesend", None))

        # One excuse per student and absent day, for 70% of absences
        day_keys = sorted({(sid, day) for sid, day, _ in absence_keys})
        excused = {k for k in day_keys if rng.random() < 0.7}
        self.insert("excuses", ["student_id", "date_from", "date_to", "reason",
                                "status", "submitted_at"],
                    [(sid, day, day, "Krankheit", "accepted",
                      dt.datetime.combine(day, dt.time(7, 30)))
                     for sid, day in day_keys if (sid, day) in excused])
        excuse_ids = dict(zip([k for k in day_keys if k in excused],
                              self.ids_of("excuses",
                                          where=f"date_from BETWEEN '{start}' AND '{end}'")))
        for sid, day, lid in absence_keys:
            attendance_rows.append((sid, lid, "abwesend", excuse_ids.get((sid, day))))
        self.insert("attendance", ["student_id", "lesson_id", "status", "excuse_id"],
                    attendance_rows)
        del attendance_rows, absence_keys, lesson_rows, lesson_meta

        # Homework ---------------------------------------------------------------
        hw_rows, hw_meta = [], []
        for (cs_label, level, letter, subject), csid in self.cs_ids.items():
            if cs_label != label:
                continue
            day = start + dt.timedelta(days=3)
            while day <= horizon:
                if not in_holiday(day):
                    hw_rows.append((csid, f"{subject}: Uebung vom {day}",
                                    dt.datetime.combine(day + dt.timedelta(days=7),
                                                        dt.time(8, 0))))
                    hw_meta.append((level, letter, day + dt.timedelta(days=7)))
                day += dt.timedelta(days=14)
        self.insert("homework", ["class_subject_id", "description", "due_date"], hw_rows)
        hw_ids = self.ids_of("homework", where=f"class_subject_id IN "
                             f"(SELECT id FROM class_subjects WHERE class_id IN "
                             f"(SELECT id FROM classes WHERE school_year_id = {y['id']}))")
        assert len(hw_ids) == len(hw_rows), "homework id mismatch"

        conf_rows = []
        for (level, letter, due), hwid in zip(hw_meta, hw_ids):
            for student in self.roster[(label, level, letter)]:
                if rng.random() < student.diligence:
                    late = 0 if rng.random() > 0.15 else int(rng.integers(1, 4))
                    conf_rows.append((hwid, student.user_id,
                                      dt.datetime.combine(due, dt.time(7, 0))
                                      + dt.timedelta(days=late), "confirmed"))
                elif rng.random() < 0.1:
                    conf_rows.append((hwid, student.user_id, None, "excused"))
        self.insert("homework_confirmations",
                    ["homework_id", "student_id", "confirmed_at", "status"], conf_rows)
        del conf_rows, hw_rows, hw_meta

        # Grades -------------------------------------------------------------------
        grade_rows = []
        collected: dict[tuple[int, int], dict] = {}
        for (cs_label, level, letter, subject), csid in self.cs_ids.items():
            if cs_label != label:
                continue
            for student in self.roster[(label, level, letter)]:
                bucket = collected.setdefault(
                    (student.user_id, csid),
                    {"m1": [[], [], []], "m2": [[], [], []], "m3": None})
                for t_index in range(TRIMESTERS):
                    t_start, t_end = self.trimester_dates[(label, t_index + 1)]
                    span = max((t_end - t_start).days, 1)
                    for category, weight, count in M1_PLAN:
                        for _ in range(count):
                            day = t_start + dt.timedelta(days=int(rng.integers(0, span)))
                            if day > horizon:
                                continue
                            progress = (day - start).days / year_days
                            value = grade_from(rng, student.ability_at(progress, subject),
                                               noise=0.8 if category != "mini_test" else 1.1)
                            grade_rows.append((student.user_id, csid, category, weight,
                                               value, day, None))
                            bucket["m1"][t_index].append((value, weight))
                    for _ in range(M2_PER_TRIMESTER):
                        day = t_start + dt.timedelta(days=int(rng.integers(0, span)))
                        if day > horizon:
                            continue
                        progress = (day - start).days / year_days
                        # Schularbeiten are harsher and more volatile
                        value = grade_from(rng, student.ability_at(progress, subject) - 0.4,
                                           noise=1.3)
                        grade_rows.append((student.user_id, csid, "schularbeit", 1.0,
                                           value, day, None))
                        bucket["m2"][t_index].append((value, 1.0))
                # The project lands somewhere in the middle of the year
                day = start + dt.timedelta(days=int(rng.integers(int(year_days * 0.35),
                                                                 int(year_days * 0.8))))
                if day <= horizon:
                    value = grade_from(rng, student.ability_at(
                        (day - start).days / year_days, subject) + 0.5, noise=0.9)
                    grade_rows.append((student.user_id, csid, "project", 1.0, value, day, None))
                    bucket["m3"] = value
        self.insert("grades", ["student_id", "class_subject_id", "category", "weight",
                               "value", "date", "homework_id"], grade_rows)
        del grade_rows

        # Period grades: the official M1/M2/M3 and FINAL -----------------------------
        period_rows = []
        for (student_id, csid), bucket in collected.items():
            state = SubjectState()
            for t_index in range(TRIMESTERS):
                t_end = self.trimester_dates[(label, t_index + 1)][1]
                if t_end > self.today:
                    continue                      # trimester not over yet
                for kind in ("m1", "m2"):
                    entries = bucket[kind][t_index]
                    if not entries:
                        continue
                    value = round(weighted_average([v for v, _ in entries],
                                                   [w for _, w in entries]), 2)
                    period_rows.append((student_id, csid,
                                        self.trimester_ids[(label, t_index + 1)],
                                        kind.upper(), value,
                                        dt.datetime.combine(t_end, dt.time(16, 0))))
                    getattr(state, kind)[t_index] = float(np.clip(value, 4.0, 10.0))
            if bucket["m3"] is not None and y["finished"]:
                period_rows.append((student_id, csid, None, "M3", float(bucket["m3"]),
                                    dt.datetime.combine(end, dt.time(16, 0))))
                state.m3 = float(bucket["m3"])
            if y["finished"] and state.is_complete():
                period_rows.append((student_id, csid, None, "FINAL",
                                    round(final_grade(state), 2),
                                    dt.datetime.combine(end, dt.time(17, 0))))
        self.insert("period_grades", ["student_id", "class_subject_id", "trimester_id",
                                      "kind", "value", "finalized_at"], period_rows)

    def run(self) -> None:
        print("building structure ...")
        self.build_structure()
        for y in self.years:
            print(f"  year {y['label']} ...", flush=True)
            self.build_year(y)
        print("\nrows written:")
        for table, n in self.counts.items():
            print(f"  {table:28s} {n:>10,}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("EDUDEVICE_DB_URL"))
    parser.add_argument("--wipe", action="store_true",
                        help="delete all existing rows first (demo databases only)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--years", type=int, default=N_YEARS)
    parser.add_argument("--today", default=None, help="pretend it is this date (YYYY-MM-DD)")
    args = parser.parse_args()

    engine = create_engine(args.url, pool_pre_ping=True)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    generator = Generator(engine, seed=args.seed, n_years=args.years, today=today)
    if args.wipe:
        generator.wipe()
    generator.run()


if __name__ == "__main__":
    main()
