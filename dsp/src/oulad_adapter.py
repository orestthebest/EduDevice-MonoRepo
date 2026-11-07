"""
EduDevice - OULAD adapter.

Reads the raw OULAD CSV files and returns them in the EduDevice data
contract. Everything downstream (features, models) only ever sees the
contract, never OULAD's own column names.

Contract tables
---------------
enrollments : one row per student and course
    student_id, course_id, module, presentation, cohort_year,
    start_date, end_date, registration_date, unregistration_date,
    valid_until, final_result, failed

grades      : one graded piece of work
    student_id, course_id, assessment_id, category, percent, value, date

submissions : one handed-in piece of work (for homework behaviour)
    student_id, course_id, assessment_id, due_date, submitted_at, days_late,
    is_late

assignments : every piece of work a course demanded, with its deadline
    course_id, assessment_id, category, due_date, weight

engagement  : daily activity, the attendance proxy
    student_id, course_id, date, clicks

Known gaps compared with the real school data (see decisions.md):
    - no M3 equivalent: OULAD has no year project
    - no real attendance: clicks are only a proxy
    - no trimesters: the course run is split into three equal periods
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from rules import percent_to_grade

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

# OULAD stores dates as days relative to the course start. These artificial
# start dates turn them into real dates. B = February start, J = October.
PRESENTATION_START = {
    "2013B": dt.date(2013, 2, 1),
    "2013J": dt.date(2013, 10, 1),
    "2014B": dt.date(2014, 2, 1),
    "2014J": dt.date(2014, 10, 1),
}

# OULAD assessment type -> EduDevice grade category
# TMA (tutor-marked)    -> larger graded work, behaves like a Schularbeit
# CMA (computer-marked) -> small test, part of Mitarbeit
CATEGORY_MAP = {"TMA": "schularbeit", "CMA": "mini_test"}

PASSING_RESULTS = {"Pass", "Distinction"}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _course_id(module: pd.Series, presentation: pd.Series) -> pd.Series:
    """One course = module + course run, e.g. 'AAA_2013J'."""
    return module.str.cat(presentation, sep="_")


def _to_date(presentation: pd.Series, day_offset: pd.Series) -> pd.Series:
    """Convert OULAD day offsets into real dates."""
    starts = pd.to_datetime(presentation.map(PRESENTATION_START))
    return starts + pd.to_timedelta(day_offset, unit="D")


def _read(oulad_dir: Path | str, name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(Path(oulad_dir) / name, **kwargs)


# ---------------------------------------------------------------------
# Enrollments (students in a course, plus the label)
# ---------------------------------------------------------------------

def load_enrollments(oulad_dir: Path | str, verbose: bool = True) -> pd.DataFrame:
    """Students per course, cleaned and labelled.

    Applies the agreed filters:
      - students without a registration date are dropped
      - non-withdrawn students that still have an unregistration date are dropped
      - withdrawals before day 0 or before the first assessment are dropped
      - remaining withdrawals count as failures
    """
    info = _read(oulad_dir, "studentInfo.csv")
    reg = _read(oulad_dir, "studentRegistration.csv")
    courses = _read(oulad_dir, "courses.csv")
    assess = _read(oulad_dir, "assessments.csv")

    df = info.merge(reg, on=["id_student", "code_module", "code_presentation"])
    df = df.merge(courses, on=["code_module", "code_presentation"])
    before = len(df)

    # First assessment deadline per course: withdrawals before it leave no data
    first_deadline = (assess.dropna(subset=["date"])
                      .groupby(["code_module", "code_presentation"])["date"]
                      .min().rename("first_assessment_day").reset_index())
    df = df.merge(first_deadline, on=["code_module", "code_presentation"], how="left")

    withdrawn = df["final_result"] == "Withdrawn"
    drop_no_registration = df["date_registration"].isna()
    drop_inconsistent = ~withdrawn & df["date_unregistration"].notna()
    drop_no_unreg_date = withdrawn & df["date_unregistration"].isna()
    drop_never_started = withdrawn & (df["date_unregistration"] < 0)
    # mutually exclusive with the line above, so the printed counts add up
    drop_too_early = (withdrawn & (df["date_unregistration"] >= 0)
                      & (df["date_unregistration"] < df["first_assessment_day"]))

    drop = (drop_no_registration | drop_inconsistent | drop_no_unreg_date
            | drop_never_started | drop_too_early)
    if verbose:
        print(f"enrollments: {before} rows")
        print(f"  - no registration date       : {drop_no_registration.sum()}")
        print(f"  - not withdrawn but unreg.   : {drop_inconsistent.sum()}")
        print(f"  - withdrawn, no unreg. date  : {drop_no_unreg_date.sum()}")
        print(f"  - withdrawn before day 0     : {drop_never_started.sum()}")
        print(f"  - withdrawn before 1st assmt : {drop_too_early.sum()}")
    df = df[~drop].copy()

    df["course_id"] = _course_id(df["code_module"], df["code_presentation"])
    df["start_date"] = pd.to_datetime(df["code_presentation"].map(PRESENTATION_START))
    df["end_date"] = df["start_date"] + pd.to_timedelta(df["module_presentation_length"], unit="D")
    df["registration_date"] = _to_date(df["code_presentation"], df["date_registration"])
    df["unregistration_date"] = _to_date(df["code_presentation"], df["date_unregistration"])

    # Last date for which snapshots of this student may be built
    df["valid_until"] = df["unregistration_date"].fillna(df["end_date"])

    # Label: 1 = failed (including withdrawal), 0 = passed
    df["failed"] = (~df["final_result"].isin(PASSING_RESULTS)).astype(int)

    out = df.rename(columns={"id_student": "student_id",
                             "code_module": "module",
                             "code_presentation": "presentation"})
    out["cohort_year"] = out["presentation"].str[:4].astype(int)

    cols = ["student_id", "course_id", "module", "presentation", "cohort_year",
            "start_date", "end_date", "registration_date", "unregistration_date",
            "valid_until", "final_result", "failed"]
    out = out[cols].reset_index(drop=True)
    if verbose:
        print(f"  => {len(out)} rows kept, fail rate {out['failed'].mean():.1%}")
    return out


# ---------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------

def load_grades(oulad_dir: Path | str, enrollments: pd.DataFrame,
                include_exams: bool = False, verbose: bool = True) -> pd.DataFrame:
    """Assessment results as grades on the 4-10 scale.

    Exams are excluded by default: they take place at the end of the course
    and are effectively the outcome itself (leakage).
    """
    sa = _read(oulad_dir, "studentAssessment.csv")
    assess = _read(oulad_dir, "assessments.csv")
    before = len(sa)

    drop_banked = sa["is_banked"] == 1      # score carried over from an earlier run
    drop_no_score = sa["score"].isna()
    if verbose:
        print(f"grades: {before} assessment results")
        print(f"  - banked scores              : {drop_banked.sum()}")
        print(f"  - missing score              : {drop_no_score.sum()}")
    sa = sa[~(drop_banked | drop_no_score)]

    df = sa.merge(assess, on="id_assessment")
    if not include_exams:
        n_exam = (df["assessment_type"] == "Exam").sum()
        df = df[df["assessment_type"] != "Exam"]
        if verbose:
            print(f"  - exam results (excluded)    : {n_exam}")

    df["course_id"] = _course_id(df["code_module"], df["code_presentation"])
    df["category"] = df["assessment_type"].map(CATEGORY_MAP).fillna("project")
    df["value"] = df["score"].apply(percent_to_grade)
    # Date of the performance: when it was handed in, not the deadline
    df["date"] = _to_date(df["code_presentation"], df["date_submitted"])

    out = df.rename(columns={"id_student": "student_id",
                             "id_assessment": "assessment_id",
                             "score": "percent"})
    out = out[["student_id", "course_id", "assessment_id", "category",
               "percent", "value", "date"]]

    out = _restrict_to_enrollments(out, enrollments, verbose, "grades")
    if verbose:
        print(f"  => {len(out)} grades, mean {out['value'].mean():.2f}")
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------
# Submissions (homework behaviour)
# ---------------------------------------------------------------------

def load_submissions(oulad_dir: Path | str, enrollments: pd.DataFrame,
                     verbose: bool = True) -> pd.DataFrame:
    """Hand-ins with their deadline, for punctuality and missing work."""
    sa = _read(oulad_dir, "studentAssessment.csv")
    assess = _read(oulad_dir, "assessments.csv")

    df = sa[sa["is_banked"] == 0].merge(assess, on="id_assessment")
    df = df[df["assessment_type"] != "Exam"]
    df = df.dropna(subset=["date"])          # deadline unknown

    df["course_id"] = _course_id(df["code_module"], df["code_presentation"])
    df["due_date"] = _to_date(df["code_presentation"], df["date"])
    df["submitted_at"] = _to_date(df["code_presentation"], df["date_submitted"])
    df["days_late"] = df["date_submitted"] - df["date"]
    df["is_late"] = (df["days_late"] > 0).astype(int)

    out = df.rename(columns={"id_student": "student_id",
                             "id_assessment": "assessment_id"})
    out = out[["student_id", "course_id", "assessment_id", "due_date",
               "submitted_at", "days_late", "is_late"]]

    out = _restrict_to_enrollments(out, enrollments, verbose, "submissions")
    if verbose:
        print(f"  => {len(out)} submissions, {out['is_late'].mean():.1%} late")
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------
# Engagement (attendance proxy)
# ---------------------------------------------------------------------

def load_engagement(oulad_dir: Path | str, enrollments: pd.DataFrame,
                    chunksize: int = 2_000_000, verbose: bool = True) -> pd.DataFrame:
    """Daily click totals per student and course.

    studentVle.csv has about 10.6 million rows, so it is read in chunks and
    aggregated per student, course and day.
    """
    cols = ["code_module", "code_presentation", "id_student", "date", "sum_click"]
    parts = []
    for chunk in _read(oulad_dir, "studentVle.csv", usecols=cols, chunksize=chunksize):
        parts.append(chunk.groupby(
            ["code_module", "code_presentation", "id_student", "date"],
            as_index=False)["sum_click"].sum())
    df = pd.concat(parts)
    df = df.groupby(["code_module", "code_presentation", "id_student", "date"],
                    as_index=False)["sum_click"].sum()

    df["course_id"] = _course_id(df["code_module"], df["code_presentation"])
    df["date_real"] = _to_date(df["code_presentation"], df["date"])

    out = df.rename(columns={"id_student": "student_id", "sum_click": "clicks"})
    out = out[["student_id", "course_id", "date_real", "clicks"]].rename(
        columns={"date_real": "date"})

    out = _restrict_to_enrollments(out, enrollments, verbose, "engagement")
    if verbose:
        print(f"  => {len(out)} student-days")
    return out.reset_index(drop=True)


def load_assignments(oulad_dir: Path | str, verbose: bool = True) -> pd.DataFrame:
    """All assessments of a course with their deadline.

    Needed as the denominator for homework completion: how many pieces of
    work were due by the cutoff date, not just how many were handed in.
    """
    assess = _read(oulad_dir, "assessments.csv").dropna(subset=["date"])
    assess = assess[assess["assessment_type"] != "Exam"]

    assess["course_id"] = _course_id(assess["code_module"], assess["code_presentation"])
    assess["due_date"] = _to_date(assess["code_presentation"], assess["date"])
    assess["category"] = assess["assessment_type"].map(CATEGORY_MAP).fillna("project")

    out = assess.rename(columns={"id_assessment": "assessment_id"})
    out = out[["course_id", "assessment_id", "category", "due_date", "weight"]]
    if verbose:
        print(f"assignments: {len(out)} assessments with a deadline")
    return out.reset_index(drop=True)


def load_final_grades(oulad_dir: Path | str, enrollments: pd.DataFrame,
                      verbose: bool = True) -> pd.DataFrame:
    """Final grade per student and course - the target of the prognosis.

    Weighted average over the course work (TMA and CMA), whose weights sum
    to 100 per course. Exams are left out: their weight is another 100 or
    200 on top, and most students never sit them, which would drag every
    grade to the bottom of the scale. Work never handed in counts as 0
    percent, the way a missing piece of work affects a real grade. Courses
    whose assessments all carry weight 0 use an unweighted mean instead.
    """
    sa = _read(oulad_dir, "studentAssessment.csv")
    assess = _read(oulad_dir, "assessments.csv")
    sa = sa[(sa["is_banked"] == 0) & sa["score"].notna()]

    assess = assess[assess["assessment_type"] != "Exam"].copy()
    assess["course_id"] = _course_id(assess["code_module"], assess["code_presentation"])

    # Courses with weight 0 everywhere: treat all assessments as equal
    total_weight = assess.groupby("course_id")["weight"].sum()
    flat_courses = set(total_weight[total_weight == 0].index)
    assess.loc[assess["course_id"].isin(flat_courses), "weight"] = 1.0
    total_weight = assess.groupby("course_id")["weight"].sum()

    df = sa.merge(assess[["id_assessment", "course_id", "weight"]], on="id_assessment")
    df["weighted"] = df["score"] * df["weight"]
    achieved = df.groupby(["id_student", "course_id"])["weighted"].sum()

    out = achieved.reset_index().rename(columns={"id_student": "student_id"})
    out["final_percent"] = (out["weighted"] / out["course_id"].map(total_weight)).clip(0, 100)
    out["final_grade"] = out["final_percent"].apply(percent_to_grade)

    out = out.merge(enrollments[["student_id", "course_id"]],
                    on=["student_id", "course_id"], how="inner")
    out = out[["student_id", "course_id", "final_percent", "final_grade"]]
    if verbose:
        print(f"final grades: {len(out)} of {len(enrollments)} enrollments "
              f"(mean {out['final_grade'].mean():.2f})")
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------
# Shared filtering
# ---------------------------------------------------------------------

def _restrict_to_enrollments(df: pd.DataFrame, enrollments: pd.DataFrame,
                             verbose: bool, label: str) -> pd.DataFrame:
    """Keep only rows of kept enrollments and before the unregistration date."""
    before = len(df)
    keep = enrollments[["student_id", "course_id", "valid_until"]]
    df = df.merge(keep, on=["student_id", "course_id"], how="inner")

    date_col = "date" if "date" in df.columns else "submitted_at"
    after_leaving = df[date_col] > df["valid_until"]
    df = df[~after_leaving].drop(columns="valid_until")
    if verbose:
        print(f"  - {label}: {before - len(df)} rows dropped "
              f"(other enrollment or after leaving)")
    return df


# ---------------------------------------------------------------------
# Temporal split
# ---------------------------------------------------------------------

def temporal_split(enrollments: pd.DataFrame, drop_overlap: bool = True,
                   verbose: bool = True):
    """Train on the 2013 course runs, test on the 2014 ones.

    Students appearing in both years are removed from the test set, so the
    model is never evaluated on someone it has already seen.
    """
    train = enrollments[enrollments["cohort_year"] == 2013].copy()
    test = enrollments[enrollments["cohort_year"] == 2014].copy()

    if drop_overlap:
        overlap = set(train["student_id"]) & set(test["student_id"])
        test = test[~test["student_id"].isin(overlap)]
        if verbose:
            print(f"split: {len(overlap)} students in both years removed from test")
    if verbose:
        print(f"  train {len(train)} rows (fail {train['failed'].mean():.1%}), "
              f"test {len(test)} rows (fail {test['failed'].mean():.1%})")
    return train.reset_index(drop=True), test.reset_index(drop=True)


# ---------------------------------------------------------------------
# Everything at once
# ---------------------------------------------------------------------

def build_all(oulad_dir: Path | str, out_dir: Path | str | None = None,
              with_engagement: bool = True, verbose: bool = True) -> dict:
    """Build all contract tables and optionally cache them as parquet."""
    enrollments = load_enrollments(oulad_dir, verbose)
    tables = {
        "enrollments": enrollments,
        "grades": load_grades(oulad_dir, enrollments, verbose=verbose),
        "submissions": load_submissions(oulad_dir, enrollments, verbose=verbose),
        "assignments": load_assignments(oulad_dir, verbose=verbose),
        "final_grades": load_final_grades(oulad_dir, enrollments, verbose=verbose),
    }
    if with_engagement:
        tables["engagement"] = load_engagement(oulad_dir, enrollments, verbose=verbose)

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, df in tables.items():
            df.to_parquet(out_dir / f"{name}.parquet", index=False)
        if verbose:
            print(f"cached to {out_dir}")
    return tables


if __name__ == "__main__":
    import sys
    raw = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    build_all(raw, out_dir="data/processed")