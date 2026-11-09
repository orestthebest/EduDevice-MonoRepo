"""
EduDevice - anomaly detection.

Question answered here
----------------------
Not "is this student weak" (that is the risk model) but "has something
changed?" A student who always scored 9 and suddenly scores 6 is not at
risk of failing, yet something clearly happened and the teacher should
know. The baseline is therefore always the student's OWN history, never
the class or the scale.

Method: EWMA control chart
--------------------------
    z_t = lam * x_t + (1 - lam) * z_(t-1)

The EWMA value z smooths the grades, with lam deciding how strongly the
newest grade counts. A single bad grade does not set off an alarm, but two
or three in a row do.

The control limit comes from the student's own earlier grades:

    LCL_t = mu - L * sigma * sqrt( lam / (2 - lam) * (1 - (1 - lam)^(2t)) )

mu and sigma are the mean and standard deviation of that student's previous
grades (expanding window). An alert fires when z falls below LCL. Only
downward breaches are alerts; an upward one is good news.

Everything here is computed from data before the point in question, so the
detector can run live exactly as it is.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LAMBDA = 0.3          # weight of the newest grade
L = 2.5               # width of the control limit in standard deviations
MIN_HISTORY = 3       # grades needed before the chart may fire
MIN_SIGMA = 0.5       # floor, so a constant run of grades is not hypersensitive


# ---------------------------------------------------------------------
# EWMA per student and subject
# ---------------------------------------------------------------------

def ewma_series(values: np.ndarray, lam: float = LAMBDA, width: float = L,
                min_history: int = MIN_HISTORY) -> pd.DataFrame:
    """EWMA, control limit and alert flag for one grade series."""
    z = values[0]
    rows = []
    for t, value in enumerate(values, start=1):
        history = values[:t - 1]
        if len(history) >= min_history:
            mu = history.mean()
            sigma = max(history.std(ddof=1), MIN_SIGMA)
            spread = np.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * t)))
            lcl = mu - width * sigma * spread
        else:
            mu, lcl = np.nan, np.nan

        z = lam * value + (1 - lam) * z
        rows.append({"t": t, "value": value, "ewma": z, "baseline": mu,
                     "lcl": lcl, "alert": bool(lcl == lcl and z < lcl)})
    return pd.DataFrame(rows)


def compute_chart(grades: pd.DataFrame, lam: float = LAMBDA) -> pd.DataFrame:
    """EWMA, baseline and sigma for every student and subject.

    Same arithmetic as ewma_series, but expressed with pandas groupby
    operations so all 166k grades are processed in about a second instead
    of looping over 25k series. Nothing here depends on the control limit
    width, so several widths can be tried without recomputing this.
    """
    df = grades.sort_values(["student_id", "course_id", "date"]).copy()
    key = ["student_id", "course_id"]
    grouped = df.groupby(key, sort=False)["value"]

    df["ewma"] = (grouped.ewm(alpha=lam, adjust=False).mean()
                  .reset_index(level=[0, 1], drop=True))

    # Baseline from the student's earlier grades only: shift() excludes the
    # current grade, so the chart never judges a grade against itself.
    shifted = grouped.shift()
    expanding = shifted.groupby([df["student_id"], df["course_id"]],
                                sort=False).expanding()
    df["baseline"] = expanding.mean().reset_index(level=[0, 1], drop=True)
    df["sigma"] = (expanding.std().reset_index(level=[0, 1], drop=True)
                   .clip(lower=MIN_SIGMA))
    df["t"] = grouped.cumcount() + 1
    df["history"] = grouped.cumcount()
    return df


def detect(grades: pd.DataFrame, lam: float = LAMBDA, width: float = L,
           min_history: int = MIN_HISTORY, chart: pd.DataFrame | None = None
           ) -> pd.DataFrame:
    """Add control limit and alert flag for a given limit width."""
    df = compute_chart(grades, lam) if chart is None else chart.copy()
    spread = np.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * df["t"])))
    df["lcl"] = df["baseline"] - width * df["sigma"] * spread
    df["alert"] = (df["history"] >= min_history) & (df["ewma"] < df["lcl"])
    return df


# ---------------------------------------------------------------------
# A simpler alternative to compare against
# ---------------------------------------------------------------------

def simple_drop_rule(grades: pd.DataFrame, drop: float = 2.0) -> pd.DataFrame:
    """Alert when a grade is `drop` points below the student's running mean.

    No smoothing, no control limits. If EWMA cannot beat this, the extra
    complexity is not worth defending.
    """
    df = grades.sort_values(["student_id", "course_id", "date"]).copy()
    grouped = df.groupby(["student_id", "course_id"], sort=False)["value"]
    # assign first: that aligns on the index, a bare comparison would not
    df["running_mean"] = (grouped.shift()
                          .groupby([df["student_id"], df["course_id"]], sort=False)
                          .expanding().mean().reset_index(level=[0, 1], drop=True))
    df["alert"] = ((df["value"] <= df["running_mean"] - drop)
                   & (grouped.cumcount() >= MIN_HISTORY))
    return df


# ---------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------

def eligible_pairs(alerts: pd.DataFrame, min_history: int = MIN_HISTORY) -> pd.DataFrame:
    """Student-course pairs that could have been flagged at all.

    A detector can only fire once a student has `min_history` earlier
    grades. A student who handed in two assignments and then dropped out
    was never checked, so counting them as "not flagged" says nothing
    about the detector.
    """
    key = ["student_id", "course_id"]
    df = alerts.sort_values([*key, "date"])
    checked = df.groupby(key, sort=False).cumcount() >= min_history
    return df.loc[checked, key].drop_duplicates()


def summarise(alerts: pd.DataFrame, enrollments: pd.DataFrame, name: str,
              min_history: int = MIN_HISTORY) -> dict:
    """Who gets flagged, and does it mean anything?

    An anomaly is not the same as failing, so this is not a classifier
    scored on accuracy. What matters: do flagged students fail noticeably
    more often, and does the alert arrive early enough to act on?

    The comparison only includes students who COULD have been flagged
    (enough grades for the detector to run). The first version compared
    flagged students against everyone else, and "everyone else" included
    students who dropped out after one or two grades: they fail often and
    can never be flagged. That made "not flagged" look worse than
    "flagged" (50% vs 20% fail), which was a property of the comparison,
    not of the detector.
    """
    key = ["student_id", "course_id"]
    flagged = (alerts[alerts["alert"]]
               .groupby(key)["date"].min()
               .rename("first_alert").reset_index())

    eligible = eligible_pairs(alerts, min_history)
    df = enrollments.merge(eligible, on=key, how="inner")
    df = df.merge(flagged, on=key, how="left")
    df["flagged"] = df["first_alert"].notna()

    course_days = (df["end_date"] - df["start_date"]).dt.days
    elapsed = (df["first_alert"] - df["start_date"]).dt.days
    share_of_course = (elapsed / course_days).dropna()

    base_rate = df["failed"].mean()
    fail_flagged = df.loc[df["flagged"], "failed"].mean()
    return {
        "method": name,
        "eligible_share": len(df) / len(enrollments),
        "flagged_share": df["flagged"].mean(),
        "base_fail_rate": base_rate,
        "fail_rate_flagged": fail_flagged,
        "fail_rate_not_flagged": df.loc[~df["flagged"], "failed"].mean(),
        "lift": fail_flagged / base_rate if base_rate else np.nan,
        "median_alert_at": share_of_course.median(),
        "alerts_total": int(alerts["alert"].sum()),
    }


def main(processed: Path):
    grades = pd.read_parquet(processed / "grades.parquet")
    enrollments = pd.read_parquet(processed / "enrollments.parquet")

    rows = []
    chart = compute_chart(grades)
    for width in (2.0, 2.5, 3.0):
        alerts = detect(grades, width=width, chart=chart)
        rows.append(summarise(alerts, enrollments, f"EWMA L={width}"))
    for drop in (1.0, 2.0):
        rows.append(summarise(simple_drop_rule(grades, drop), enrollments,
                              f"simple drop >= {drop}"))

    table = pd.DataFrame(rows).set_index("method")
    print("\n=== Anomaly detection (only students with enough grades to be flagged) ===")
    print(table.round(3).to_string())
    print("\nlift = fail rate of flagged students / fail rate of all eligible students.\n"
          "Above 1: an alert means a higher chance of failing. The method with the\n"
          "best lift at a usable flagged_share is the one to run in production.")

    # One example series, to show in the thesis what the chart does
    alerts = detect(grades, width=L, chart=chart)
    example = alerts[alerts["alert"]].iloc[0]
    series = alerts[(alerts["student_id"] == example["student_id"])
                    & (alerts["course_id"] == example["course_id"])]
    print(f"\n=== Example: student {example['student_id']} "
          f"in {example['course_id']} ===")
    print(series[["t", "value", "ewma", "baseline", "lcl", "alert"]]
          .round(2).to_string(index=False))
    return table


if __name__ == "__main__":
    import sys
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/processed"))