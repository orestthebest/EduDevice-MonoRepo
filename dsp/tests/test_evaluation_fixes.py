"""Tests for the three evaluation fixes (November 2026):
EWMA comparison restricted to eligible students, conformal intervals
calibrated on unseen course runs, and the tree printout with real counts."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from anomaly import eligible_pairs, summarise
from model_prognosis import IntervalModel, conformal_offsets
from model_risk import tree_with_counts


# ---------------------------------------------------------------- anomaly

def _toy_alerts():
    """A: 5 grades, flagged at the 5th. B: 5 grades, never flagged.
    C: only 2 grades, so the detector (MIN_HISTORY = 3) could never run."""
    rows = []
    for sid, n, alert_at in (("A", 5, 5), ("B", 5, None), ("C", 2, None)):
        for t in range(1, n + 1):
            rows.append({"student_id": sid, "course_id": "X",
                         "date": pd.Timestamp("2026-09-01") + pd.Timedelta(days=7 * t),
                         "alert": t == alert_at})
    return pd.DataFrame(rows)


def _toy_enrollments():
    return pd.DataFrame({"student_id": ["A", "B", "C"], "course_id": "X",
                         "start_date": pd.Timestamp("2026-09-01"),
                         "end_date": pd.Timestamp("2027-06-30"),
                         "failed": [1, 0, 1]})


def test_eligible_excludes_students_the_detector_never_saw():
    pairs = eligible_pairs(_toy_alerts(), min_history=3)
    assert set(pairs["student_id"]) == {"A", "B"}


def test_summarise_compares_only_eligible_students():
    s = summarise(_toy_alerts(), _toy_enrollments(), "toy")
    # C failed but could never be flagged; counting it would make
    # "not flagged" look like a 50% fail rate instead of 0%
    assert s["eligible_share"] == pytest.approx(2 / 3)
    assert s["fail_rate_not_flagged"] == 0
    assert s["fail_rate_flagged"] == 1
    assert s["base_fail_rate"] == 0.5
    assert s["lift"] == 2


# ---------------------------------------------------------------- conformal

def test_conformal_offsets_finite_sample_rank():
    r = np.arange(1, 20)                       # 19 residuals, alpha 0.10
    assert conformal_offsets(r, 0.10) == (1, 19)   # ranks floor(20*.05)=1, ceil(20*.95)=19
    low, high = conformal_offsets(np.arange(5), 0.10)
    assert low == -np.inf and high == np.inf   # 5 residuals cannot support a 90% interval


def _runs(n_runs, rng, start):
    """Course runs that differ from each other (another teacher, other tasks):
    each run shifts all its grades by its own offset. `course` is a feature
    that identifies the run, like OULAD's course-specific features do, so a
    tree can learn the offsets of the runs it was trained on - but not of a
    new run. That is the situation in which held-out students look better
    than new course runs really are."""
    parts = []
    for k in range(n_runs):
        x = rng.uniform(5, 9, 150)
        shift = rng.normal(0, 0.8)
        parts.append(pd.DataFrame({"x": x, "course": rng.uniform(0, 1),
                                   "y": x + shift + rng.normal(0, 0.4, 150),
                                   "run": f"R{start + k}",
                                   "student": np.arange(150) + 1000 * (start + k)}))
    return pd.concat(parts, ignore_index=True)


def test_course_run_calibration_covers_new_runs():
    """Averaged over 10 simulated school years, so one lucky draw cannot pass."""
    coverage = {"random_students": [], "course_runs": []}
    for seed in range(10):
        rng = np.random.default_rng(seed)
        train, test = _runs(12, rng, 0), _runs(40, rng, 12)
        for mode in coverage:
            m = IntervalModel(DecisionTreeRegressor(min_samples_leaf=20, random_state=0),
                              alpha=0.10, calibration=mode)
            m.fit(train[["x", "course"]], train["y"], pd.Series(0.5, index=train.index),
                  students=train["student"], runs=train["run"])
            low, _, high = m.predict_interval(test[["x", "course"]], pd.Series(0.5, index=test.index))
            coverage[mode].append(((test["y"] >= low) & (test["y"] <= high)).mean())
    old, new = np.mean(coverage["random_students"]), np.mean(coverage["course_runs"])

    # random students share their runs with the fitted data -> far too narrow
    assert old < 0.70, old
    # held-out runs see the run-to-run shift -> close to the promised 90%.
    # Not exactly 90%: the run effect is estimated from only 12 runs.
    assert new > 0.80 and new - old > 0.15, (old, new)


def test_course_runs_needs_runs():
    m = IntervalModel(LinearRegression(), calibration="course_runs")
    X, y = pd.DataFrame({"x": [1.0, 2, 3]}), pd.Series([1.0, 2, 3])
    with pytest.raises(ValueError):
        m.fit(X, y, pd.Series([0.5] * 3), runs=pd.Series(["R1"] * 3))


# ---------------------------------------------------------------- tree printout

def test_tree_shows_real_counts_not_balanced_weights():
    X = pd.DataFrame({"x": np.r_[np.zeros(90), np.ones(10)]})
    y = np.r_[np.zeros(85), np.ones(5), np.zeros(2), np.ones(8)]
    tree = DecisionTreeClassifier(max_depth=1, class_weight="balanced").fit(X, y)
    text = tree_with_counts(tree, X, y, ["x"])
    assert "all: 100 students, 13 failed" in text
    assert "90 students, 5 failed (6%)" in text      # balanced weights would show 19.23
    assert "10 students, 8 failed (80%)" in text
