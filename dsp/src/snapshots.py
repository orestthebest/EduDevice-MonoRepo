"""
EduDevice - snapshots and features.

A snapshot answers one question: given everything known about a student in
a subject up to a cutoff date, how is that student doing?

The rule that matters: every feature uses ONLY data strictly before the
cutoff. That is what prevents leakage, and it is the same rule the live
system follows, where "now" is the cutoff.

Feature set v1
--------------
mean_to_date              mean of all grades so far
n_negative_grades         number of 4s so far
trend_slope               grade change per 30 days (0 with under 3 grades)
delta_vs_own_baseline     mean of the last 3 grades minus the earlier mean
attendance_rate           share of days with activity (OULAD: click proxy)
homework_completion_rate  share of due work that was handed in
n_grades_to_date          how much evidence there is
year_progress             share of the course elapsed at the cutoff
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    "mean_to_date", "n_negative_grades", "trend_slope", "delta_vs_own_baseline",
    "attendance_rate", "homework_completion_rate", "n_grades_to_date",
    "year_progress",
]

RECENT_N = 3          # how many grades count as "recent"
MIN_GRADES_FOR_SLOPE = 3
SLOPE_DAYS = 30       # slope expressed per 30 days
FAILING_GRADE = 4     # lowest grade on the 4-10 scale


# ---------------------------------------------------------------------
# Snapshot skeleton
# ---------------------------------------------------------------------

def build_snapshot_index(enrollments: pd.DataFrame,
                         fractions=(0.25, 0.50, 0.75),
                         trimesters: pd.DataFrame | None = None,
                         today: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per student, course and cutoff point.

    Two ways to place the cutoffs:

    - `fractions` (the OULAD case): shares of the course duration, because
      the data has no period structure of its own.
    - `trimesters` (the school case): the real trimester end dates, which is
      when a teacher would actually look at the system. Trimesters are not
      exactly equal in length, so these are not the same dates as 1/3 and 2/3.

    With `today` set, each enrollment also gets a snapshot at that date,
    which is what the live system computes: everything known right now.
    """
    rows = []
    base_columns = ["student_id", "course_id", "cohort_year", "start_date",
                    "end_date", "valid_until", "failed"]

    if trimesters is not None:
        if "presentation" not in enrollments.columns:
            raise ValueError("trimester cutoffs need a `presentation` column")
        ends = (trimesters[["presentation", "number", "end_date"]]
                .rename(columns={"end_date": "cutoff_date"}))
        merged = enrollments[base_columns + ["presentation"]].merge(
            ends, on="presentation", how="inner")
        duration = (merged["end_date"] - merged["start_date"]).dt.days
        elapsed = (merged["cutoff_date"] - merged["start_date"]).dt.days
        merged["year_progress"] = (elapsed / duration).round(3)
        merged["cutoff_kind"] = "trimester_" + merged["number"].astype(str)
        rows.append(merged.drop(columns="number"))
    else:
        for fraction in fractions:
            snap = enrollments[base_columns].copy()
            duration = snap["end_date"] - snap["start_date"]
            snap["cutoff_date"] = snap["start_date"] + duration * fraction
            snap["year_progress"] = fraction
            snap["cutoff_kind"] = f"fraction_{fraction}"
            rows.append(snap)

    if today is not None:
        live = enrollments[base_columns].copy()
        live["cutoff_date"] = pd.Timestamp(today)
        duration = (live["end_date"] - live["start_date"]).dt.days
        elapsed = (live["cutoff_date"] - live["start_date"]).dt.days
        live["year_progress"] = (elapsed / duration).round(3)
        live["cutoff_kind"] = "today"
        # Only years that are actually running on that date
        live = live[(live["start_date"] <= live["cutoff_date"])
                    & (live["cutoff_date"] <= live["end_date"])]
        rows.append(live)

    snapshots = pd.concat(rows, ignore_index=True)

    # A cutoff after the student left, or before the year began, has no meaning
    before = len(snapshots)
    snapshots = snapshots[(snapshots["cutoff_date"] <= snapshots["valid_until"])
                          & (snapshots["cutoff_date"] > snapshots["start_date"])]
    print(f"snapshots: {before} built, {before - len(snapshots)} dropped "
          f"(outside the student's time in the course), {len(snapshots)} kept")
    return snapshots.reset_index(drop=True)


# ---------------------------------------------------------------------
# Grade features
# ---------------------------------------------------------------------

def _grade_features(snapshots: pd.DataFrame, grades: pd.DataFrame) -> pd.DataFrame:
    """Everything derived from grades before the cutoff."""
    df = snapshots[["snapshot_id", "student_id", "course_id", "cutoff_date",
                    "start_date"]].merge(
        grades[["student_id", "course_id", "value", "date"]],
        on=["student_id", "course_id"], how="left")

    # THE cutoff rule
    df = df[df["date"] < df["cutoff_date"]].copy()

    df["days"] = (df["date"] - df["start_date"]).dt.days
    grouped = df.groupby("snapshot_id")

    out = grouped.agg(
        n_grades_to_date=("value", "size"),
        mean_to_date=("value", "mean"),
        sum_x=("days", "sum"),
        sum_y=("value", "sum"),
        sum_xx=("days", lambda s: (s ** 2).sum()),
    )
    out["n_negative_grades"] = grouped["value"].apply(
        lambda s: (s <= FAILING_GRADE).sum())

    # Slope via the closed-form least-squares formula (no per-group regression)
    sum_xy = df.assign(xy=df["days"] * df["value"]).groupby("snapshot_id")["xy"].sum()
    n = out["n_grades_to_date"]
    denom = n * out["sum_xx"] - out["sum_x"] ** 2
    slope = (n * sum_xy - out["sum_x"] * out["sum_y"]) / denom.replace(0, np.nan)
    # Scaled to grade points per 30 days: per day the numbers are so small
    # that a logistic regression coefficient becomes unreadable.
    out["trend_slope"] = (slope * SLOPE_DAYS).where(
        n >= MIN_GRADES_FOR_SLOPE, 0.0).fillna(0.0)

    # Recent grades against the student's own earlier level
    df = df.sort_values("date")
    df["rank_from_end"] = df.groupby("snapshot_id").cumcount(ascending=False)
    recent = df[df["rank_from_end"] < RECENT_N].groupby("snapshot_id")["value"].mean()
    earlier = df[df["rank_from_end"] >= RECENT_N].groupby("snapshot_id")["value"].mean()
    out["delta_vs_own_baseline"] = (recent - earlier).fillna(0.0)

    return out.drop(columns=["sum_x", "sum_y", "sum_xx"])


# ---------------------------------------------------------------------
# Homework and engagement features
# ---------------------------------------------------------------------

def _homework_features(snapshots: pd.DataFrame, submissions: pd.DataFrame,
                       assignments: pd.DataFrame) -> pd.Series:
    """Share of the work due so far that was actually handed in."""
    due = snapshots[["snapshot_id", "course_id", "cutoff_date"]].merge(
        assignments[["course_id", "assessment_id", "due_date"]],
        on="course_id", how="left")
    due = due[due["due_date"] < due["cutoff_date"]]
    n_due = due.groupby("snapshot_id").size()

    handed_in = snapshots[["snapshot_id", "student_id", "course_id", "cutoff_date"]].merge(
        submissions[["student_id", "course_id", "assessment_id", "submitted_at"]],
        on=["student_id", "course_id"], how="left")
    handed_in = handed_in[handed_in["submitted_at"] < handed_in["cutoff_date"]]
    n_done = handed_in.groupby("snapshot_id")["assessment_id"].nunique()

    rate = (n_done / n_due).clip(upper=1.0)
    # Nothing due yet counts as complete rather than as failure
    return rate.reindex(snapshots["snapshot_id"]).fillna(1.0)


def _engagement_features(snapshots: pd.DataFrame,
                         engagement: pd.DataFrame) -> pd.Series:
    """Share of days with activity - the attendance proxy in OULAD."""
    if engagement is None or engagement.empty:
        return pd.Series(np.nan, index=snapshots["snapshot_id"])

    df = snapshots[["snapshot_id", "student_id", "course_id", "cutoff_date",
                    "start_date"]].merge(
        engagement[["student_id", "course_id", "date", "clicks"]],
        on=["student_id", "course_id"], how="left")
    df = df[(df["date"] < df["cutoff_date"]) & (df["clicks"] > 0)]

    active_days = df.groupby("snapshot_id")["date"].nunique()
    elapsed = (snapshots.set_index("snapshot_id")["cutoff_date"]
               - snapshots.set_index("snapshot_id")["start_date"]).dt.days
    rate = (active_days.reindex(elapsed.index).fillna(0) / elapsed.clip(lower=1))
    return rate.clip(upper=1.0)


def _attendance_features(snapshots: pd.DataFrame,
                         attendance: pd.DataFrame) -> pd.Series:
    """Real attendance: lessons attended divided by lessons held.

    The school database has this properly, so no proxy is needed. The feature
    keeps the name `attendance_rate` either way, which is what lets the same
    model code run on both sources.
    """
    df = snapshots[["snapshot_id", "student_id", "course_id", "cutoff_date"]].merge(
        attendance[["student_id", "course_id", "date", "present"]],
        on=["student_id", "course_id"], how="left")
    df = df[df["date"] < df["cutoff_date"]]

    held = df.groupby("snapshot_id")["present"].size()
    attended = df.groupby("snapshot_id")["present"].sum()
    rate = (attended / held.replace(0, np.nan))
    # No lesson held yet is not an absence
    return rate.reindex(snapshots["snapshot_id"]).fillna(1.0)


# ---------------------------------------------------------------------
# Everything together
# ---------------------------------------------------------------------

def _component_features(snapshots: pd.DataFrame, grades: pd.DataFrame) -> pd.DataFrame:
    """Separate means for M1 (Mitarbeit) and M2 (Schularbeiten).

    They behave differently - M1 is frequent and fairly stable, M2 is rare
    and volatile - so a single average hides the distinction. Only available
    where the source marks components, which the school database does.
    """
    df = snapshots[["snapshot_id", "student_id", "course_id", "cutoff_date"]].merge(
        grades[["student_id", "course_id", "value", "date", "component"]],
        on=["student_id", "course_id"], how="left")
    df = df[df["date"] < df["cutoff_date"]]

    out = pd.DataFrame(index=snapshots["snapshot_id"])
    for component in ("M1", "M2"):
        part = df[df["component"] == component].groupby("snapshot_id")["value"]
        out[f"{component.lower()}_mean"] = part.mean()
        out[f"n_{component.lower()}_grades"] = part.size()
    out["n_m1_grades"] = out["n_m1_grades"].fillna(0).astype(int)
    out["n_m2_grades"] = out["n_m2_grades"].fillna(0).astype(int)
    return out.reset_index()


def build_features(tables: dict, fractions=(0.25, 0.50, 0.75),
                   today=None, split_components: bool = False) -> pd.DataFrame:
    """Snapshots with all v1 features and the target column `failed`.

    Source-independent: it uses real attendance when the source has it
    (`attendance`) and the click proxy when it does not (`engagement`), and
    real trimester dates when the source has them (`trimesters`).
    """
    snapshots = build_snapshot_index(tables["enrollments"], fractions,
                                     trimesters=tables.get("trimesters"),
                                     today=today)
    snapshots.insert(0, "snapshot_id", np.arange(len(snapshots)))

    grade_feats = _grade_features(snapshots, tables["grades"])
    out = snapshots.merge(grade_feats, on="snapshot_id", how="left")

    # No grades yet means no evidence, not a grade of zero
    out["n_grades_to_date"] = out["n_grades_to_date"].fillna(0).astype(int)
    out["n_negative_grades"] = out["n_negative_grades"].fillna(0).astype(int)
    out["trend_slope"] = out["trend_slope"].fillna(0.0)
    out["delta_vs_own_baseline"] = out["delta_vs_own_baseline"].fillna(0.0)
    # mean_to_date stays NaN on purpose - it is genuinely unknown

    out["homework_completion_rate"] = _homework_features(
        snapshots, tables["submissions"], tables["assignments"]).values

    if "attendance" in tables:
        out["attendance_rate"] = _attendance_features(
            snapshots, tables["attendance"]).values
    else:
        out["attendance_rate"] = _engagement_features(
            snapshots, tables.get("engagement")).values

    columns = ["snapshot_id", "student_id", "course_id", "cohort_year",
               "cutoff_date", *FEATURES, "failed"]
    if "cutoff_kind" in out.columns:
        columns.insert(5, "cutoff_kind")

    if split_components and "component" in tables["grades"].columns:
        out = out.merge(_component_features(snapshots, tables["grades"]),
                        on="snapshot_id", how="left")
        columns += ["m1_mean", "m2_mean", "n_m1_grades", "n_m2_grades"]

    return out[columns]


def check_no_leakage(features: pd.DataFrame, tables: dict, n_samples: int = 200) -> None:
    """Spot check: no grade used in a snapshot may lie after its cutoff."""
    rng = np.random.default_rng(0)
    sample = features.sample(min(n_samples, len(features)), random_state=0)
    grades = tables["grades"]
    problems = 0
    for row in sample.itertuples():
        used = grades[(grades.student_id == row.student_id)
                      & (grades.course_id == row.course_id)
                      & (grades.date < row.cutoff_date)]
        if len(used) != row.n_grades_to_date:
            problems += 1
    print(f"leakage check: {problems} of {len(sample)} sampled snapshots mismatched")
    assert problems == 0, "feature count does not match the data before the cutoff"


if __name__ == "__main__":
    import sys
    from pathlib import Path

    processed = Path(sys.argv[1] if len(sys.argv) > 1 else "data/processed")
    tables = {name: pd.read_parquet(processed / f"{name}.parquet")
              for name in ["enrollments", "grades", "submissions",
                           "assignments", "engagement"]
              if (processed / f"{name}.parquet").exists()}

    features = build_features(tables)
    features.to_parquet(processed / "features_v1.parquet", index=False)
    check_no_leakage(features, tables)
    print(features.describe().round(3).to_string())
