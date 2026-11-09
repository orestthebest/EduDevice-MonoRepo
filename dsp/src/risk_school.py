"""
risk_school.py — the risk model trained on the school's own grade data.

Why a second risk model
-----------------------
model_risk.py was built for OULAD, whose features are clicks, submissions and
VLE engagement. The school database has none of those. It has `grades`, and at
the moment nothing else: the sim seed creates no attendance, homework or lesson
rows, so attendance_rate and homework_completion_rate would be empty columns.

Rather than feed a model empty features, this one uses only what the school
actually stores today. When Gridi's attendance and homework tables start filling
up, the feature list here grows and the model is retrained - that is a new
version in the model store, not a rewrite.

What it predicts
----------------
For one student in one subject: will the year-end subject grade fall below the
pass mark of 4.6? Grades run 4..10 with 10 best, and a computed average of 4.6
or more rounds up to 5 and passes, so "fail" is raw < 4.6.

Training snapshots
------------------
Each student-subject contributes one row per cutoff - after trimester 1, and
after trimester 2. Features come only from marks dated before the cutoff; the
label comes from the full year. That mirrors how the model is used in February,
not how it would look with hindsight in July.

Honesty about the current metrics
---------------------------------
Trained on the sim data, this model is learning the rules seed_edudevice_real.py
used to invent the students. The accuracy is circular. It proves the pipeline
runs end to end; it is not evidence that the method works. The model card
carries that warning, and so does every printout.
"""

from __future__ import annotations

import argparse
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import model_store
import notenstatistiken as ns
from grade_stats import Mark, component_grade, subject_grade

MODEL_NAME = "risk_school"
PASS_THRESHOLD = Decimal("4.6")      # a computed average below this fails
LOW_GRADE = Decimal("5")             # a single mark at or below this is "low"

FEATURES = [
    "grade_so_far",
    "m1_mean",
    "m2_mean",
    "has_m3",
    "n_marks",
    "share_low",
    "volatility",
    "trend_delta",
    "vs_class_delta",
    "cutoff_trimester",
]


@dataclass
class Snapshot:
    student_id: int
    class_subject_id: int
    cutoff_trimester: int
    features: dict
    failed: Optional[int]      # None while the year has no final grade


def _safe(value, default=0.0) -> float:
    return default if value is None else float(value)


def _features_from(rows, class_mean_so_far: Optional[float],
                   cutoff: int) -> Optional[dict]:
    """Build one feature row from the marks dated before the cutoff."""
    if not rows:
        return None

    marks = [Mark(r.category, r.value, r.weight) for r in rows]
    m1 = component_grade(marks, "M1")
    m2 = component_grade(marks, "M2")
    m3 = component_grade(marks, "M3")
    overall = subject_grade(m1.raw, m2.raw, m3.raw)
    if overall.raw is None:
        return None

    values = [float(r.value) for r in rows]
    n_low = sum(1 for v in values if Decimal(str(v)) <= LOW_GRADE)

    per_tri = {}
    for num in (1, 2, 3):
        tri = [Mark(r.category, r.value, r.weight) for r in rows if r.trimester == num]
        if not tri:
            continue
        t1 = component_grade(tri, "M1")
        t2 = component_grade(tri, "M2")
        combined = subject_grade(t1.raw, t2.raw, None)
        if combined.raw is not None:
            per_tri[num] = float(combined.raw)
    trend = 0.0
    if len(per_tri) >= 2:
        ordered = [per_tri[k] for k in sorted(per_tri)]
        trend = ordered[-1] - ordered[0]

    return {
        "grade_so_far": float(overall.raw),
        "m1_mean": _safe(m1.raw, float(overall.raw)),
        "m2_mean": _safe(m2.raw, float(overall.raw)),
        "has_m3": 1.0 if m3.raw is not None else 0.0,
        "n_marks": float(len(rows)),
        "share_low": n_low / len(values),
        "volatility": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "trend_delta": trend,
        "vs_class_delta": (float(overall.raw) - class_mean_so_far)
        if class_mean_so_far is not None else 0.0,
        "cutoff_trimester": float(cutoff),
    }


def build_snapshots(data: dict, cutoffs=(1, 2)) -> list[Snapshot]:
    """One row per student, subject and cutoff, with the year-end label."""
    by_pair = defaultdict(list)
    for r in data["grades"]:
        by_pair[(r.student_id, r.class_subject_id)].append(r)

    # Final grade for the whole year = the label.
    final_by_pair = {}
    for pair, rows in by_pair.items():
        marks = [Mark(r.category, r.value, r.weight) for r in rows]
        overall = subject_grade(
            component_grade(marks, "M1").raw,
            component_grade(marks, "M2").raw,
            component_grade(marks, "M3").raw,
        )
        final_by_pair[pair] = overall.raw

    out: list[Snapshot] = []
    for cutoff in cutoffs:
        # Class mean up to this cutoff, so "vs class" compares like with like.
        class_vals = defaultdict(list)
        pending = {}
        for (sid, cs_id), rows in by_pair.items():
            upto = [r for r in rows if r.trimester is not None and r.trimester <= cutoff]
            if not upto:
                continue
            marks = [Mark(r.category, r.value, r.weight) for r in upto]
            g = subject_grade(
                component_grade(marks, "M1").raw,
                component_grade(marks, "M2").raw,
                component_grade(marks, "M3").raw,
            ).raw
            if g is not None:
                class_vals[cs_id].append(float(g))
                pending[(sid, cs_id)] = upto
        class_mean = {k: statistics.fmean(v) for k, v in class_vals.items()}

        for (sid, cs_id), upto in pending.items():
            feats = _features_from(upto, class_mean.get(cs_id), cutoff)
            if feats is None:
                continue
            final = final_by_pair.get((sid, cs_id))
            label = None if final is None else int(Decimal(str(final)) < PASS_THRESHOLD)
            out.append(Snapshot(sid, cs_id, cutoff, feats, label))
    return out


def _matrix(snaps: list[Snapshot]):
    X = np.array([[s.features[f] for f in FEATURES] for s in snaps], dtype=float)
    y = np.array([s.failed for s in snaps], dtype=float)
    return X, y


def train(data: dict, data_source: str, synthetic: bool,
          root=model_store.DEFAULT_ROOT, notes: str = "") -> tuple:
    snaps = [s for s in build_snapshots(data) if s.failed is not None]
    if not snaps:
        raise RuntimeError("no labelled snapshots - is there any grade data?")

    X, y = _matrix(snaps)
    n_pos = int(y.sum())
    if n_pos < 2 or n_pos == len(y):
        raise RuntimeError(
            f"cannot train: {n_pos} failing of {len(y)} rows. The model needs "
            f"both outcomes present."
        )

    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced",
                                       random_state=42)),
        ]
    )

    # Grouped hold-out by student, so the same student never sits in both halves.
    students = np.array([s.student_id for s in snaps])
    uniq = np.unique(students)
    rng = np.random.default_rng(42)
    rng.shuffle(uniq)
    cut = max(1, int(len(uniq) * 0.7))
    train_ids = set(uniq[:cut].tolist())
    tr = np.array([sid in train_ids for sid in students])

    metrics: dict = {"n_rows": len(y), "n_failing": n_pos,
                     "fail_rate": round(float(y.mean()), 4)}
    if tr.sum() > 0 and (~tr).sum() > 0 and len(set(y[~tr])) > 1:
        model.fit(X[tr], y[tr])
        p = model.predict_proba(X[~tr])[:, 1]
        pred = (p >= 0.5).astype(int)
        metrics.update(
            {
                "holdout_rows": int((~tr).sum()),
                "roc_auc": round(float(roc_auc_score(y[~tr], p)), 4),
                "average_precision": round(float(average_precision_score(y[~tr], p)), 4),
                "recall": round(float(recall_score(y[~tr], pred, zero_division=0)), 4),
                "precision": round(float(precision_score(y[~tr], pred, zero_division=0)), 4),
                "brier": round(float(brier_score_loss(y[~tr], p)), 4),
            }
        )
    else:
        metrics["holdout"] = "skipped - too few students or one-class holdout"

    # Refit on everything for the model that actually ships.
    model.fit(X, y)

    card = model_store.ModelCard(
        name=MODEL_NAME,
        task="risk_classification",
        version=model_store.next_version(root, MODEL_NAME),
        created_at="",
        data_source=data_source,
        synthetic_training_data=synthetic,
        n_training_rows=len(y),
        n_positive=n_pos,
        target=f"year-end subject grade < {PASS_THRESHOLD} (fail)",
        features=list(FEATURES),
        hyperparameters={"class_weight": "balanced", "max_iter": 1000,
                         "cutoffs": [1, 2]},
        notes=notes,
    )
    path = model_store.save(model, card, metrics, root)
    return model, card, metrics, path


def predict_current(data: dict, model, card) -> dict:
    """Score every student-subject on everything known so far.

    Returns {(student_id, class_subject_id): {...}} ready to merge into the
    Notenstatistiken payload or to write into risk_assessments.
    """
    by_pair = defaultdict(list)
    for r in data["grades"]:
        by_pair[(r.student_id, r.class_subject_id)].append(r)

    graded = [t["number"] for t in data["trimesters"]]
    cutoff = max(graded) if graded else 3

    class_vals = defaultdict(list)
    rows, keys = [], []
    for (sid, cs_id), grows in by_pair.items():
        marks = [Mark(r.category, r.value, r.weight) for r in grows]
        g = subject_grade(
            component_grade(marks, "M1").raw,
            component_grade(marks, "M2").raw,
            component_grade(marks, "M3").raw,
        ).raw
        if g is not None:
            class_vals[cs_id].append(float(g))
    class_mean = {k: statistics.fmean(v) for k, v in class_vals.items()}

    for (sid, cs_id), grows in by_pair.items():
        feats = _features_from(grows, class_mean.get(cs_id), cutoff)
        if feats is None:
            continue
        rows.append([feats[f] for f in FEATURES])
        keys.append((sid, cs_id))

    if not rows:
        return {}

    proba = model.predict_proba(np.array(rows, dtype=float))[:, 1]
    out = {}
    for (sid, cs_id), p in zip(keys, proba):
        out[(sid, cs_id)] = {
            "fail_probability": round(float(p), 4),
            "risk_score": int(round(float(p) * 100)),
            "model_name": card.name,
            "model_version": card.version,
            "trained_on": card.data_source,
            "synthetic_model": card.synthetic_training_data,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=None)
    ap.add_argument("--school-year", type=int, default=1)
    ap.add_argument("--root", default=str(model_store.DEFAULT_ROOT))
    ap.add_argument("--source", default="school_sim",
                    choices=["school_sim", "school_real"],
                    help="school_sim marks the model as trained on generated data")
    args = ap.parse_args()

    data = ns.load(ns.connect(args.url), args.school_year)
    synthetic = args.source == "school_sim"
    model, card, metrics, path = train(
        data, args.source, synthetic,
        root=args.root,
        notes="Grades-only feature set: the school database has no attendance or "
              "homework rows yet. Retrain with those features once they exist.",
    )
    print(f"saved {path}")
    print()
    print(model_store.describe(card.name, card.version, args.root))


if __name__ == "__main__":
    main()
