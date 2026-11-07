"""
EduDevice - school database adapter.

Reads the real EduDevice MySQL database and returns the same contract tables
as oulad_adapter.py, so every stage after it (snapshots, features, models)
runs unchanged on either source.

Contract tables
---------------
enrollments : one row per student, subject and school year
    student_id, course_id, module, presentation, cohort_year,
    start_date, end_date, valid_until, final_result, failed

grades      : one graded piece of work
    student_id, course_id, assessment_id, category, value, date

assignments : every piece of work a course demanded, with its deadline
    course_id, assessment_id, category, due_date, weight

submissions : one handed-in piece of work
    student_id, course_id, assessment_id, due_date, submitted_at,
    days_late, is_late

attendance  : one row per lesson a student was expected at
    student_id, course_id, date, present, excused
    (OULAD has no real attendance and supplies `engagement` instead; the
    snapshot builder accepts either.)

final_grades: the regression target
    student_id, course_id, final_grade

trimesters  : the real period boundaries, used as snapshot cutoffs
    presentation, number, start_date, end_date

Differences from OULAD worth knowing
------------------------------------
  - course_id is the class_subject id: subject x class x teacher x year
  - attendance is real, not a click proxy
  - M3 (the year project) exists here and has no OULAD equivalent
  - the current school year has no final grades yet, so those rows carry
    failed = NaN: they are what the live system predicts, never trained on

Usage
-----
    export EDUDEVICE_DB_URL="mysql+pymysql://BENUTZER:PASSWORT@localhost:3306/edudevice_db"
    python school_adapter.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from rules import PASS_THRESHOLD

# No password in the source. The connection string comes from the environment
# variable EDUDEVICE_DB_URL, the same way notenstatistiken.py and
# generate_school_data.py read it. The fallback below is a local test database
# without a password and does not reach the school server.
#
# On the school server the database is only reachable through an SSH tunnel.
# DataGrip opens that tunnel itself - a Python script does not. So before
# running this, open one in its own window and leave it open:
#     ssh -L 3306:localhost:3306 <ssh-user>@172.20.1.115
URL_ENV_VAR = "EDUDEVICE_DB_URL"
DEFAULT_URL = "mysql+pymysql://root@localhost:3306/edudevice_db"


def db_url(url: str | None = None) -> str:
    """Connection string: argument beats environment variable beats fallback."""
    return url or os.environ.get(URL_ENV_VAR) or DEFAULT_URL

# How the database's grade categories map onto the year components
COMPONENT_OF_CATEGORY = {
    "schularbeit": "M2",
    "project": "M3",
    # everything else is Mitarbeit
    "homework": "M1", "mini_test": "M1", "oral": "M1", "presentation": "M1",
    "classwork": "M1", "participation": "M1", "behaviour": "M1",
}

PRESENT_STATUSES = ("anwesend", "verspaetet")   # late still counts as present


# ---------------------------------------------------------------------
# Contract tables
# ---------------------------------------------------------------------

def load_enrollments(engine, verbose: bool = True) -> pd.DataFrame:
    """Every student in every subject in every school year, plus the label."""
    query = """
        SELECT  css.student_id              AS student_id,
                cs.id                       AS course_id,
                sub.name                    AS module,
                sy.label                    AS presentation,
                sy.start_date               AS start_date,
                sy.end_date                 AS end_date,
                pg.value                    AS final_value
        FROM        class_subject_students css
        JOIN        class_subjects cs  ON cs.id = css.class_subject_id
        JOIN        classes c          ON c.id = cs.class_id
        JOIN        school_years sy    ON sy.id = c.school_year_id
        JOIN        subjects sub       ON sub.id = cs.subject_id
        LEFT JOIN   period_grades pg   ON pg.student_id = css.student_id
                                      AND pg.class_subject_id = cs.id
                                      AND pg.kind = 'FINAL'
    """
    df = pd.read_sql(query, engine, parse_dates=["start_date", "end_date"])

    df["cohort_year"] = df["presentation"].str[:4].astype(int)
    # The year is still running where no final grade has been issued
    df["valid_until"] = df["end_date"]
    df["failed"] = np.where(df["final_value"].notna(),
                            (df["final_value"] < PASS_THRESHOLD).astype(float),
                            np.nan)
    df["final_result"] = np.where(df["final_value"].isna(), "Running",
                                  np.where(df["failed"] == 1, "Fail", "Pass"))

    out = df[["student_id", "course_id", "module", "presentation", "cohort_year",
              "start_date", "end_date", "valid_until", "final_result", "failed"]]
    if verbose:
        labelled = out["failed"].notna()
        print(f"enrollments: {len(out)} rows, {labelled.sum()} with a final grade "
              f"(fail rate {out.loc[labelled, 'failed'].mean():.1%}), "
              f"{(~labelled).sum()} in the running year")
    return out.reset_index(drop=True)


def load_grades(engine, verbose: bool = True) -> pd.DataFrame:
    """Single grades, with the component each category belongs to."""
    query = """
        SELECT  g.student_id        AS student_id,
                g.class_subject_id  AS course_id,
                g.id                AS assessment_id,
                g.category          AS category,
                g.weight            AS weight,
                g.value             AS value,
                g.date              AS date
        FROM grades g
    """
    df = pd.read_sql(query, engine, parse_dates=["date"])
    df["value"] = df["value"].astype(float)
    df["weight"] = df["weight"].astype(float)
    df["component"] = df["category"].map(COMPONENT_OF_CATEGORY).fillna("M1")
    if verbose:
        print(f"grades: {len(df)} rows, mean {df['value'].mean():.2f}, "
              f"components {df['component'].value_counts().to_dict()}")
    return df[["student_id", "course_id", "assessment_id", "category",
               "component", "weight", "value", "date"]]


def load_assignments(engine, verbose: bool = True) -> pd.DataFrame:
    """Homework the course set, as the denominator for completion."""
    query = """
        SELECT  h.class_subject_id  AS course_id,
                h.id                AS assessment_id,
                h.due_date          AS due_date
        FROM homework h
    """
    df = pd.read_sql(query, engine, parse_dates=["due_date"])
    df["category"] = "homework"
    df["weight"] = 1.0
    if verbose:
        print(f"assignments: {len(df)} homework items")
    return df[["course_id", "assessment_id", "category", "due_date", "weight"]]


def load_submissions(engine, verbose: bool = True) -> pd.DataFrame:
    """Confirmed homework, with lateness measured against the deadline."""
    query = """
        SELECT  hc.student_id       AS student_id,
                h.class_subject_id  AS course_id,
                h.id                AS assessment_id,
                h.due_date          AS due_date,
                hc.confirmed_at     AS submitted_at,
                hc.status           AS status
        FROM homework_confirmations hc
        JOIN homework h ON h.id = hc.homework_id
    """
    df = pd.read_sql(query, engine, parse_dates=["due_date", "submitted_at"])
    df["days_late"] = (df["submitted_at"] - df["due_date"]).dt.days
    df["is_late"] = (df["days_late"] > 0).fillna(False).astype(int)
    if verbose:
        print(f"submissions: {len(df)} rows, {df['is_late'].mean():.1%} late")
    return df[["student_id", "course_id", "assessment_id", "due_date",
               "submitted_at", "days_late", "is_late"]]


def load_attendance(engine, verbose: bool = True) -> pd.DataFrame:
    """Real attendance per lesson. Cancelled lessons are excluded."""
    query = """
        SELECT  a.student_id        AS student_id,
                tt.class_subject_id AS course_id,
                l.date              AS date,
                a.status            AS status,
                a.excuse_id         AS excuse_id
        FROM        attendance a
        JOIN        lessons l   ON l.id = a.lesson_id
        JOIN        timetable tt ON tt.id = l.timetable_id
        WHERE l.cancelled = FALSE
    """
    df = pd.read_sql(query, engine, parse_dates=["date"])
    df["present"] = df["status"].isin(PRESENT_STATUSES).astype(int)
    df["excused"] = df["excuse_id"].notna().astype(int)
    if verbose:
        print(f"attendance: {len(df)} lesson records, "
              f"absence rate {1 - df['present'].mean():.1%}")
    return df[["student_id", "course_id", "date", "present", "excused"]]


def load_final_grades(engine, verbose: bool = True) -> pd.DataFrame:
    """The official final grade per student and subject: the regression target."""
    query = """
        SELECT  pg.student_id       AS student_id,
                pg.class_subject_id AS course_id,
                pg.value            AS final_grade
        FROM period_grades pg
        WHERE pg.kind = 'FINAL'
    """
    df = pd.read_sql(query, engine)
    df["final_grade"] = df["final_grade"].astype(float)
    if verbose:
        print(f"final grades: {len(df)} rows, mean {df['final_grade'].mean():.2f}")
    return df


def load_period_grades(engine, verbose: bool = True) -> pd.DataFrame:
    """Official M1/M2/M3 values per trimester - the teacher's own figures."""
    query = """
        SELECT  pg.student_id       AS student_id,
                pg.class_subject_id AS course_id,
                pg.kind             AS kind,
                pg.value            AS value,
                t.number            AS trimester,
                pg.finalized_at     AS finalized_at
        FROM        period_grades pg
        LEFT JOIN   trimesters t ON t.id = pg.trimester_id
        WHERE pg.kind <> 'FINAL'
    """
    df = pd.read_sql(query, engine, parse_dates=["finalized_at"])
    df["value"] = df["value"].astype(float)
    if verbose:
        print(f"period grades: {len(df)} rows")
    return df


def load_trimesters(engine, verbose: bool = True) -> pd.DataFrame:
    """Period boundaries, used as the natural snapshot cutoffs."""
    query = """
        SELECT  sy.label    AS presentation,
                t.number    AS number,
                t.start_date AS start_date,
                t.end_date  AS end_date
        FROM        trimesters t
        JOIN        school_years sy ON sy.id = t.school_year_id
    """
    df = pd.read_sql(query, engine, parse_dates=["start_date", "end_date"])
    if verbose:
        print(f"trimesters: {len(df)} periods across "
              f"{df['presentation'].nunique()} school years")
    return df


# ---------------------------------------------------------------------
# Everything at once
# ---------------------------------------------------------------------

def build_all(url: str | None = None, out_dir: Path | str | None = None,
              verbose: bool = True) -> dict:
    """Build all contract tables from the school database."""
    engine = create_engine(db_url(url), pool_pre_ping=True)
    tables = {
        "enrollments": load_enrollments(engine, verbose),
        "grades": load_grades(engine, verbose),
        "assignments": load_assignments(engine, verbose),
        "submissions": load_submissions(engine, verbose),
        "attendance": load_attendance(engine, verbose),
        "final_grades": load_final_grades(engine, verbose),
        "period_grades": load_period_grades(engine, verbose),
        "trimesters": load_trimesters(engine, verbose),
    }
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, df in tables.items():
            df.to_parquet(out_dir / f"{name}.parquet", index=False)
        if verbose:
            print(f"cached to {out_dir}")
    return tables


def temporal_split(enrollments: pd.DataFrame, drop_repeat_students: bool = False,
                   verbose: bool = True):
    """Train on the finished school years, test on the newest one.

    Rows without a final grade belong to the running year: they are the live
    prediction set and are never trained on.

    Why repeated students are KEPT by default, unlike with OULAD. There,
    a student appearing in two course runs was a coincidence worth removing.
    At a school it is the norm - the same student advances from 3A to 4A every
    year - so removing them would delete most of the test set and describe a
    situation that never occurs. The deployed system will always have been
    trained on earlier years of the very students it is scoring. The honest
    consequence is that part of what the model knows is the student, not only
    their current performance, which `split_by_student` below measures.
    """
    labelled = enrollments[enrollments["failed"].notna()]
    running = enrollments[enrollments["failed"].isna()]

    years = sorted(labelled["cohort_year"].unique())
    if len(years) < 2:
        raise ValueError("at least two finished school years are needed "
                         f"for a temporal split, found {years}")
    train = labelled[labelled["cohort_year"] < years[-1]]
    test = labelled[labelled["cohort_year"] == years[-1]]

    repeated = set(train["student_id"]) & set(test["student_id"])
    if drop_repeat_students:
        test = test[~test["student_id"].isin(repeated)]
    if verbose:
        print(f"split: train {len(train)} rows (years {years[:-1]}), "
              f"test {len(test)} rows (year {years[-1]}), "
              f"{len(repeated)} students appear in both "
              f"({'removed' if drop_repeat_students else 'kept, as in deployment'}), "
              f"{len(running)} rows in the running year to predict")
    return (train.reset_index(drop=True), test.reset_index(drop=True),
            running.reset_index(drop=True))


def split_by_student(enrollments: pd.DataFrame, test_share: float = 0.3,
                     seed: int = 42, verbose: bool = True):
    """Secondary check: train and test on disjoint sets of students.

    Answers a different question from temporal_split - does the model
    generalise to students it has never seen? Comparing the two tells you how
    much of its performance comes from recognising individuals.
    """
    labelled = enrollments[enrollments["failed"].notna()]
    students = np.array(sorted(labelled["student_id"].unique()))
    rng = np.random.default_rng(seed)
    rng.shuffle(students)
    cut = int(len(students) * (1 - test_share))
    train_ids, test_ids = set(students[:cut]), set(students[cut:])

    train = labelled[labelled["student_id"].isin(train_ids)]
    test = labelled[labelled["student_id"].isin(test_ids)]
    if verbose:
        print(f"student split: train {len(train)} rows / {len(train_ids)} students, "
              f"test {len(test)} rows / {len(test_ids)} students")
    return train.reset_index(drop=True), test.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None,
                        help="otherwise EDUDEVICE_DB_URL, otherwise the local fallback")
    parser.add_argument("--out", default="data/processed_school")
    args = parser.parse_args()

    tables = build_all(args.url, out_dir=args.out)
    temporal_split(tables["enrollments"])


if __name__ == "__main__":
    main()