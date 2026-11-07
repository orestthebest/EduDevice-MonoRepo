"""
EduDevice - performance prognosis.

Formulation
-----------
Regression per snapshot: what final grade will this student reach in this
subject?
    target = final_grade (4-10), the weighted course-work average

Same rules as the risk model: temporal split 2013 -> 2014, overlapping
students removed from the test set, imputation fitted on training data only,
and every feature uses data from before the cutoff.

The prognosis complements the risk model. The classifier answers "is this
student in danger"; the regression answers "roughly where will they end up",
which is what the student interface shows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

from sklearn.base import clone
from sklearn.model_selection import GroupShuffleSplit, LeaveOneGroupOut

from model_risk import MODEL_FEATURES, RANDOM_STATE, prepare


class CurrentAverageBaseline:
    """The obvious guess: the final grade equals the current average.

    Any regression model has to beat this, otherwise it adds nothing over
    simply showing the student their average.
    """

    def __init__(self):
        self.fallback = 7.0

    def fit(self, X, y):
        self.fallback = float(np.mean(y))
        return self

    def predict(self, X):
        X = pd.DataFrame(X, columns=MODEL_FEATURES)
        return np.where(X["has_grades"] == 1, X["mean_to_date"], self.fallback)


def build_models() -> dict:
    return {
        "baseline_mean": DummyRegressor(strategy="mean"),
        "baseline_current_average": CurrentAverageBaseline(),
        "ridge": Pipeline([("scale", StandardScaler()),
                           ("reg", Ridge(alpha=1.0))]),
        "decision_tree": DecisionTreeRegressor(max_depth=5, min_samples_leaf=200,
                                               random_state=RANDOM_STATE),
    }


# ---------------------------------------------------------------------
# Prediction intervals
# ---------------------------------------------------------------------

def conformal_offsets(residuals, alpha: float) -> tuple[float, float]:
    """Lower and upper residual bounds with the finite-sample correction.

    A plain 5%/95% quantile of n residuals is slightly too narrow: the
    guarantee only holds when the bound is the ceil((n+1)(1-alpha/2))-th
    smallest residual, not the (1-alpha/2) quantile. With few residuals
    the difference is noticeable; with many it vanishes. If n is too small
    for the requested level, the bound is infinite (and clipped to the
    grade scale later), which is honest: there is not enough evidence.
    """
    r = np.sort(np.asarray(residuals, dtype=float))
    n = len(r)
    k_low = int(np.floor((n + 1) * alpha / 2))          # 1-based rank
    k_high = int(np.ceil((n + 1) * (1 - alpha / 2)))
    low = r[k_low - 1] if k_low >= 1 else -np.inf
    high = r[k_high - 1] if k_high <= n else np.inf
    return low, high


class IntervalModel:
    """Point prediction plus an honest range around it.

    Conformal prediction: the model predicts data it was not fitted on,
    and the spread of those errors (residuals) becomes the interval. If 90%
    of the held-out residuals lie between -2.3 and +1.7, the same interval
    should contain about 90% of future values.

    The bounds are computed per cutoff, because a prediction in October is
    less certain than one in April and the range should say so. No
    distribution is assumed, and nothing is invented.

    Where the residuals come from (`calibration`):

    "course_runs" (default) - every course run in the training data is held
        out once, a copy of the model is fitted on all other runs and
        predicts it. The test set consists of course runs the model has
        never seen (2014), so the residuals have to come from unseen runs
        too, otherwise they miss the run-to-run differences (another
        teacher, other assignments) and the interval comes out too narrow.
        The final model is then fitted on all training data.

    "random_students" - the first version: 25% of the students held out at
        random. Their course runs are the same ones the model was fitted on,
        which is why coverage on the 2014 test set came out at 87.9%
        instead of 90%. Kept so the two can be compared side by side.
    """

    def __init__(self, model, alpha: float = 0.10, calibration: str = "course_runs",
                 calibration_size: float = 0.25):
        if calibration not in ("course_runs", "random_students"):
            raise ValueError(f"unknown calibration {calibration!r}")
        self.model = model
        self.alpha = alpha                      # 0.10 -> 90% interval
        self.calibration = calibration
        self.calibration_size = calibration_size
        self.offsets: dict[float, tuple[float, float]] = {}

    def _residuals_course_runs(self, X, y, runs):
        residuals = np.empty(len(y))
        for _, held_out in LeaveOneGroupOut().split(X, y, runs):
            fit_idx = np.setdiff1d(np.arange(len(y)), held_out)
            copy = clone(self.model).fit(X.iloc[fit_idx], y.iloc[fit_idx])
            residuals[held_out] = y.iloc[held_out].values - copy.predict(X.iloc[held_out])
        self.model.fit(X, y)
        return residuals, np.arange(len(y))

    def _residuals_random_students(self, X, y, students):
        splitter = GroupShuffleSplit(n_splits=1, test_size=self.calibration_size,
                                     random_state=RANDOM_STATE)
        fit_idx, cal_idx = next(splitter.split(X, y, students))
        self.model.fit(X.iloc[fit_idx], y.iloc[fit_idx])
        return y.iloc[cal_idx].values - self.model.predict(X.iloc[cal_idx]), cal_idx

    def fit(self, X, y, progress, students=None, runs=None):
        if self.calibration == "course_runs":
            if runs is None or pd.Series(runs).nunique() < 2:
                raise ValueError("course_runs calibration needs at least two course runs")
            residuals, idx = self._residuals_course_runs(X, y, runs)
        else:
            residuals, idx = self._residuals_random_students(X, y, students)

        frame = pd.DataFrame({"residual": residuals, "progress": progress.iloc[idx].values})
        for value, group in frame.groupby("progress"):
            self.offsets[value] = conformal_offsets(group["residual"], self.alpha)
        return self

    def predict(self, X):
        return self.model.predict(X)

    def predict_interval(self, X, progress):
        point = self.model.predict(X)
        low = np.array([self.offsets[p][0] for p in progress])
        high = np.array([self.offsets[p][1] for p in progress])
        return (np.clip(point + low, 4, 10), point, np.clip(point + high, 4, 10))


def evaluate_intervals(y_true, lower, upper, progress: pd.Series) -> pd.DataFrame:
    """Does the interval keep its promise, and how wide is it?"""
    inside = (y_true >= lower) & (y_true <= upper)
    frame = pd.DataFrame({"inside": inside, "width": upper - lower,
                          "progress": progress.values})
    return frame.groupby("progress").agg(coverage=("inside", "mean"),
                                         mean_width=("width", "mean"),
                                         n=("inside", "size")).round(3)


def evaluate(name: str, y_true, pred, progress: pd.Series) -> dict:
    row = {
        "model": name,
        "MAE": mean_absolute_error(y_true, pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, pred)),
        "R2": r2_score(y_true, pred),
    }
    for value in sorted(progress.unique()):
        mask = progress == value
        row[f"MAE@{int(value * 100)}%"] = mean_absolute_error(y_true[mask], pred[mask])
    return row


def main(processed: Path):
    features = pd.read_parquet(processed / "features_v1.parquet")
    targets = pd.read_parquet(processed / "final_grades.parquet")

    before = len(features)
    features = features.merge(targets[["student_id", "course_id", "final_grade"]],
                              on=["student_id", "course_id"], how="inner")
    print(f"{before - len(features)} snapshots without a final grade removed "
          f"(student never handed anything in), {len(features)} left")

    train, test = prepare(features)
    X_train, y_train = train[MODEL_FEATURES], train["final_grade"]
    X_test, y_test = test[MODEL_FEATURES], test["final_grade"]

    results, fitted = [], {}
    for name, model in build_models().items():
        model.fit(X_train, y_train)
        fitted[name] = model
        results.append(evaluate(name, y_test.values, model.predict(X_test),
                                test["year_progress"]))

    table = pd.DataFrame(results).set_index("model")
    print("\n=== Test set: 2014 course runs (grades 4-10) ===")
    print(table.round(3).to_string())

    coefs = pd.Series(fitted["ridge"].named_steps["reg"].coef_,
                      index=MODEL_FEATURES).sort_values()
    print("\n=== Ridge coefficients (standardised) ===")
    print(coefs.round(3).to_string())

    # Prediction intervals on top of the best model. Both calibration
    # variants are printed, so the effect of the fix is visible in numbers.
    def tree():
        return DecisionTreeRegressor(max_depth=5, min_samples_leaf=200,
                                     random_state=RANDOM_STATE)

    old = IntervalModel(tree(), alpha=0.10, calibration="random_students")
    old.fit(X_train, y_train, train["year_progress"], students=train["student_id"])
    o_low, _, o_high = old.predict_interval(X_test, test["year_progress"])
    print("\n=== 90% intervals, OLD calibration (random students) - for comparison ===")
    print(evaluate_intervals(y_test.values, o_low, o_high, test["year_progress"]).to_string())

    interval_model = IntervalModel(tree(), alpha=0.10, calibration="course_runs")
    interval_model.fit(X_train, y_train, train["year_progress"], runs=train["course_id"])
    low, point, high = interval_model.predict_interval(X_test, test["year_progress"])

    print("\n=== 90% intervals, calibrated on held-out course runs (test set) ===")
    intervals = evaluate_intervals(y_test.values, low, high, test["year_progress"])
    print(intervals.to_string())
    overall = np.average(intervals["coverage"], weights=intervals["n"])
    print(f"weighted coverage {overall:.3f} (target 0.900)")
    print("\n=== Example output for the student interface ===")
    example = pd.DataFrame({
        "student_id": test["student_id"].values,
        "course": test["course_id"].values,
        "progress": test["year_progress"].values,
        "predicted": point.round(1),
        "range": [f"{a:.1f} - {b:.1f}" for a, b in zip(low, high)],
        "actual": y_test.values,
    })
    print(example.head(8).to_string(index=False))

    # Residuals: the basis for the uncertainty range
    residuals = y_test.values - fitted["ridge"].predict(X_test)
    print("\n=== Residuals of the ridge model ===")
    print(pd.DataFrame({"residual": residuals, "progress": test["year_progress"].values})
          .groupby("progress")["residual"]
          .agg(mean="mean", std="std",
               q05=lambda s: s.quantile(0.05), q95=lambda s: s.quantile(0.95))
          .round(2).to_string())
    return table


if __name__ == "__main__":
    import sys
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/processed"))