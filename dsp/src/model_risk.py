"""
EduDevice - risk classification.

Formulation
-----------
Binary classification per snapshot: will this student fail this subject?
    target 1 = failed (including withdrawal), 0 = passed

Rules of the game:
  - train on the 2013 course runs, test on 2014 (temporal split)
  - students appearing in both years are removed from the test set
  - the median for imputation comes from the training data only
  - the decision threshold is chosen on cross-validation within the training
    data, never on the test set

Missing a student at risk is worse than a false alarm, so the threshold is
picked for a recall target rather than for accuracy.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import (GroupKFold, GroupShuffleSplit,
                                     cross_val_predict)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from snapshots import FEATURES

RECALL_TARGET = 0.85      # at least 85% of failing students must be caught
RANDOM_STATE = 42

MODEL_FEATURES = FEATURES + ["has_grades"]


# ---------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------

def prepare(features: pd.DataFrame):
    """Temporal split, missing-value handling and feature matrices."""
    train = features[features["cohort_year"] == 2013].copy()
    test = features[features["cohort_year"] == 2014].copy()

    overlap = set(train["student_id"]) & set(test["student_id"])
    test = test[~test["student_id"].isin(overlap)].copy()

    # Option B: flag plus imputation, so "no information" stays distinguishable
    # from "average student". The median comes from the training data only.
    median = train["mean_to_date"].median()
    for part in (train, test):
        part["has_grades"] = part["mean_to_date"].notna().astype(int)
        part["mean_to_date"] = part["mean_to_date"].fillna(median)

    print(f"train {len(train)} snapshots (fail {train['failed'].mean():.1%}), "
          f"test {len(test)} (fail {test['failed'].mean():.1%}), "
          f"{len(overlap)} overlapping students removed")
    print(f"imputed mean_to_date with the training median {median:.2f} "
          f"for {(train['has_grades'] == 0).sum()} train and "
          f"{(test['has_grades'] == 0).sum()} test snapshots")
    return train, test


def tree_with_counts(tree, X, y, feature_names, max_depth: int = 3) -> str:
    """The fitted tree as text, with the REAL number of students per node.

    export_text(show_weights=True) is not usable here: the tree is trained
    with class_weight="balanced", so its node values are reweighted counts
    (a leaf with 5 real failures can show 19.2). Here every node lists how
    many training students reach it and how many of them actually failed,
    so the tree reads as "of the students who end up here, x% failed".
    """
    t = tree.tree_
    reach = tree.decision_path(X)                     # students x nodes, 1 = passes through
    y = np.asarray(y)
    n_node = np.asarray(reach.sum(axis=0)).ravel()
    fail_node = np.asarray(reach[y == 1].sum(axis=0)).ravel()

    def counts(node):
        n, f = int(n_node[node]), int(fail_node[node])
        return f"{n} students, {f} failed ({f / n:.0%})" if n else "0 students"

    lines = [f"all: {counts(0)}"]

    def walk(node, depth):
        if t.children_left[node] == -1:                # leaf
            return
        if depth >= max_depth:
            lines.append("|   " * depth + "|--- ...")
            return
        name, thr = feature_names[t.feature[node]], t.threshold[node]
        for child, op in ((t.children_left[node], "<="), (t.children_right[node], "> ")):
            lines.append("|   " * depth + f"|--- {name} {op} {thr:.2f}: {counts(child)}")
            walk(child, depth + 1)

    walk(0, 0)
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------

def build_models() -> dict:
    """Two baselines plus two interpretable models."""
    return {
        "baseline_always_fail": DummyClassifier(strategy="constant", constant=1),
        "baseline_rule": RuleBaseline(),
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000,
                                       class_weight="balanced",
                                       random_state=RANDOM_STATE)),
        ]),
        "decision_tree": DecisionTreeClassifier(max_depth=4,
                                                min_samples_leaf=200,
                                                class_weight="balanced",
                                                random_state=RANDOM_STATE),
    }


class RuleBaseline:
    """Simple, explainable rule: no grades yet, or an average of 5 or worse.

    Anything a model does must beat this, otherwise the machine learning is
    not worth its complexity.
    """

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        X = pd.DataFrame(X, columns=MODEL_FEATURES)
        flagged = ((X["has_grades"] == 0) | (X["mean_to_date"] <= 5)).astype(float)
        return np.column_stack([1 - flagged, flagged])

    def get_params(self, deep=False):
        return {}


# ---------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------

class CalibratedModel:
    """Wraps a classifier so its probabilities mean what they say.

    class_weight="balanced" helps recall but inflates the probabilities, so
    a raw 0.8 does not mean "80% of these students fail". Isotonic
    regression maps the raw scores onto observed failure rates. It is
    monotone, so the ranking and therefore ROC-AUC stay untouched; only the
    numbers on the 0-100 scale change.

    The calibration set is split off by student, so no student is used both
    for fitting the model and for calibrating it.
    """

    def __init__(self, model, calibration_size: float = 0.25):
        self.model = model
        self.calibration_size = calibration_size
        self.calibrator = IsotonicRegression(out_of_bounds="clip")

    def fit(self, X, y, groups):
        splitter = GroupShuffleSplit(n_splits=1, test_size=self.calibration_size,
                                     random_state=RANDOM_STATE)
        fit_idx, cal_idx = next(splitter.split(X, y, groups))
        self.model.fit(X.iloc[fit_idx], y.iloc[fit_idx])
        raw = self.model.predict_proba(X.iloc[cal_idx])[:, 1]
        self.calibrator.fit(raw, y.iloc[cal_idx])
        return self

    def predict_proba(self, X):
        raw = self.model.predict_proba(X)[:, 1]
        calibrated = self.calibrator.predict(raw)
        return np.column_stack([1 - calibrated, calibrated])

    def get_params(self, deep=False):
        return {"model": self.model, "calibration_size": self.calibration_size}


def calibration_table(y_true, proba, bins=5) -> pd.DataFrame:
    """Predicted probability against the share that actually failed."""
    df = pd.DataFrame({"proba": proba, "actual": y_true})
    df["bin"] = pd.cut(df["proba"], np.linspace(0, 1, bins + 1),
                       include_lowest=True)
    out = df.groupby("bin", observed=True).agg(
        predicted=("proba", "mean"), actual=("actual", "mean"), n=("actual", "size"))
    return out.round(3)


# ---------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------

def choose_threshold(model, X, y, groups, target_recall=RECALL_TARGET) -> float:
    """Lowest threshold reaching the recall target, via grouped CV on train.

    Grouped by student, so the same student is never in the training and the
    validation fold at once.
    """
    cv = GroupKFold(n_splits=5)
    proba = cross_val_predict(model, X, y, groups=groups, cv=cv,
                              method="predict_proba")[:, 1]

    best = 0.5
    for threshold in np.arange(0.05, 0.96, 0.01):
        if recall_score(y, proba >= threshold) >= target_recall:
            best = threshold           # keep raising while recall still holds
    return round(best, 2)


# ---------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------

def evaluate(name: str, y_true, proba, threshold: float,
             progress: pd.Series | None = None) -> dict:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    row = {
        "model": name,
        "threshold": threshold,
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred),
        "f1": f1_score(y_true, pred),
        "roc_auc": roc_auc_score(y_true, proba) if len(set(proba)) > 2 else np.nan,
        "brier": brier_score_loss(y_true, proba),
        "missed_students": fn,
        "false_alarms": fp,
    }
    if progress is not None:
        for value in sorted(progress.unique()):
            mask = progress == value
            row[f"recall@{int(value * 100)}%"] = recall_score(y_true[mask], pred[mask])
    return row


def risk_score(proba: np.ndarray) -> np.ndarray:
    """Risk score 0-100: the calibrated probability times 100.

    Not an invented number - it means "of all students with this score,
    roughly this percentage actually failed".
    """
    return np.round(proba * 100).astype(int)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main(processed: Path):
    features = pd.read_parquet(processed / "features_v1.parquet")
    train, test = prepare(features)

    X_train, y_train = train[MODEL_FEATURES], train["failed"]
    X_test, y_test = test[MODEL_FEATURES], test["failed"]
    groups = train["student_id"]

    models = build_models()
    models["logistic_calibrated"] = CalibratedModel(
        Pipeline([("scale", StandardScaler()),
                  ("clf", LogisticRegression(max_iter=1000,
                                             class_weight="balanced",
                                             random_state=RANDOM_STATE))]))

    results, fitted = [], {}
    for name, model in models.items():
        if isinstance(model, CalibratedModel):
            model.fit(X_train, y_train, groups)
        else:
            model.fit(X_train, y_train)
        fitted[name] = model

        if name.startswith("baseline"):
            threshold = 0.5
        elif isinstance(model, CalibratedModel):
            # Grid search on the calibrated test-independent CV is not
            # possible here, so reuse the uncalibrated threshold mapped
            # through the calibrator.
            raw_threshold = choose_threshold(model.model, X_train, y_train, groups)
            threshold = float(model.calibrator.predict([raw_threshold])[0])
        else:
            threshold = choose_threshold(model, X_train, y_train, groups)

        proba = model.predict_proba(X_test)[:, 1]
        results.append(evaluate(name, y_test.values, proba, threshold,
                                test["year_progress"]))

    table = pd.DataFrame(results).set_index("model")
    print("\n=== Test set: 2014 course runs ===")
    print(table.round(3).to_string())

    print("\n=== Calibration: logistic regression, before and after ===")
    raw_proba = fitted["logistic_regression"].predict_proba(X_test)[:, 1]
    cal_proba = fitted["logistic_calibrated"].predict_proba(X_test)[:, 1]
    print("uncalibrated:")
    print(calibration_table(y_test.values, raw_proba).to_string())
    print("calibrated:")
    print(calibration_table(y_test.values, cal_proba).to_string())

    # Interpretability: what did the models learn?
    logit = fitted["logistic_regression"]
    coefs = pd.Series(logit.named_steps["clf"].coef_[0],
                      index=MODEL_FEATURES).sort_values()
    print("\n=== Logistic regression coefficients (standardised) ===")
    print(coefs.round(3).to_string())

    print("\n=== Decision tree (real training counts per node) ===")
    print(tree_with_counts(fitted["decision_tree"], X_train, y_train,
                           MODEL_FEATURES, max_depth=3))

    # Example output for the dashboard
    sample = test.assign(risk_score=risk_score(cal_proba))[
        ["student_id", "course_id", "year_progress", "mean_to_date",
         "attendance_rate", "risk_score", "failed"]]
    print("\n=== Example risk scores ===")
    print(sample.sort_values("risk_score", ascending=False).head(5).round(2).to_string(index=False))
    return table


if __name__ == "__main__":
    import sys
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/processed"))