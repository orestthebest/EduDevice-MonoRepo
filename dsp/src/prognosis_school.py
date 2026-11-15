"""
prognosis_school.py — the likely final grade with an 80 % range, on school data.

What it answers
---------------
For one student in one subject, at any point in the year: where will the final
grade (raw, 4-10) probably end up? The answer is a range, not a number:
"likely between 6.4 and 7.9". The page draws it as a darker band inside the
"still possible" band from the rules (backend/app/services/final_range.py).

Why a second model next to model_prognosis.py
---------------------------------------------
model_prognosis.py works on OULAD, whose features (clicks, submissions) do not
exist in the school database. This one uses only what the school stores: the
marks, their dates and categories.

Training data
-------------
The final grade of a year is only known at the end of that year. The school
has no finished year yet, and the server's sim grades stop at the day they
were loaded. So the model learns from whole simulated years, made with the
same generator as the server's sim data (seed_edudevice_real.py) but with
OTHER seeds - it never sees the students it later predicts. Students of the
"incomplete" type are left out of training: their year is not finished, so
their last average is not a final grade.

Every student-subject gives one snapshot per checkpoint (10 %, 15 %, ... 95 %
of the year): features from the marks up to that day, label = the final grade.

Candidates and choice
---------------------
  baseline   final = today's average. Any model has to beat this.
  ridge      linear regression on the features below.
Both are scored on years they were not fitted on (leave one simulated year
out). At each checkpoint the one with the lower error is used: in autumn the
model adds something to today's average, near the end of the year today's
average is already almost the final grade and wins.

The 80 % range and the chance to fail
-------------------------------------
Conformal prediction, the same method as model_prognosis.py: the errors on
held-out years become the range. One pool of errors per checkpoint (October
is less certain than May) and per forecast level (students near the bottom
scatter less). The chance to fail is the share of the same errors that would
put the final grade below 4.6 - so the teacher's number and the band can never
contradict each other. The numbers printed by `main` are measured one level
further out (a year that took part neither in fitting nor in calibrating).

Honesty
-------
Trained on generated data, the model has learned the generator's rules. The
numbers show that the pipeline works end to end, not that the method works
on real students. The model card carries that warning. Retrain on real data
once a school year with real marks is complete.

Usage
-----
  python src/prognosis_school.py                (8 simulated years, saves to dsp/models)
  python src/prognosis_school.py --seeds 4      (faster, for trying it out)
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import backend_rules
import model_store
import scoring
from grade_stats import PASS_THRESHOLD
from model_prognosis import conformal_offsets

MODEL_NAME = "prognosis_school"
ALPHA = 0.20                       # 80 % range
CHECKPOINTS = [round(0.10 + 0.05 * i, 2) for i in range(18)]      # 10 %, 15 %, ... 95 %
SHOW_FROM = 0.15                   # earlier: too few marks, no forecast (like the absence projection)
RECENT_DAYS = 30                   # "recent" marks for the recent-vs-older feature
SEED_BASE = 1000                   # training seeds 1001, 1002, ... - never the server's 20261025
PASS = float(PASS_THRESHOLD)       # a final raw grade below 4.6 fails
POINT_BANDS = (5.5, 7.0)           # forecast levels with their own error pool (see band_of)

FEATURES = [
    "average",            # today's average (missing parts left out, like the page)
    "m1", "m2", "m3",     # component averages, today's average where a part has no mark yet
    "has_m2", "has_m3",   # 1 if that part has a mark
    "n_marks",
    "share",              # share of the year that has passed
    "class_average",      # average of the class in the subject, same day
    "recent_change",      # recent marks minus older marks
    "spread",             # how much the student's marks scatter
    "average_x_share",    # the later in the year, the more today's average counts
    "class_x_share",
    "m3_known",           # the project mark if graded, else 0
]


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

def year_share(day: date, first: date, last: date) -> float:
    """How much of the year has passed on `day` (0 to 1)."""
    total = (last - first).days
    return min(max((day - first).days / total, 0.0), 1.0) if total > 0 else 1.0


def features(marks: list[scoring.DatedMark], day: date, share: float,
             class_average: Optional[float], trimesters) -> Optional[dict]:
    """One feature row from the marks up to `day`. None without any usable mark.
    Averages per trimester like the page (final_range.year_components)."""
    raw = scoring.subject_raw(marks, trimesters)
    if raw is None:
        return None
    comp = scoring._YEAR.year_components([(m.component, m.value, m.weight, m.date) for m in marks],
                                         list(trimesters))
    average = float(raw)
    values = [float(m.value) for m in marks]
    recent = [float(m.value) for m in marks if (day - m.date).days <= RECENT_DAYS]
    older = [float(m.value) for m in marks if (day - m.date).days > RECENT_DAYS]
    cls = average if class_average is None else class_average
    m3 = None if comp["M3"] is None else float(comp["M3"])
    return {
        "average": average,
        "m1": average if comp["M1"] is None else float(comp["M1"]),
        "m2": average if comp["M2"] is None else float(comp["M2"]),
        "m3": average if m3 is None else m3,
        "has_m2": float(comp["M2"] is not None),
        "has_m3": float(m3 is not None),
        "n_marks": float(len(values)),
        "share": share,
        "class_average": cls,
        "recent_change": statistics.fmean(recent) - statistics.fmean(older) if recent and older else 0.0,
        "spread": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "average_x_share": average * share,
        "class_x_share": cls * share,
        "m3_known": 0.0 if m3 is None else m3,
    }


def class_averages(pairs: dict, trimesters: dict) -> dict[int, float]:
    """class_subject_id -> mean of the students' averages. pairs: {(student, cs): marks},
    trimesters: {cs: [(start, end)]}."""
    per_cs = defaultdict(list)
    for (_, cs), marks in pairs.items():
        raw = scoring.subject_raw(marks, trimesters.get(cs, ()))
        if raw is not None:
            per_cs[cs].append(float(raw))
    return {cs: statistics.fmean(v) for cs, v in per_cs.items()}


def checkpoint_for(share: float) -> Optional[float]:
    """The checkpoint whose range applies: the last one at or before `share`.
    Using the earlier one makes the range a little wider, never too narrow."""
    passed = [c for c in CHECKPOINTS if c <= share + 1e-9]
    return passed[-1] if passed else None


# ---------------------------------------------------------------------------
# Training data: whole simulated years
# ---------------------------------------------------------------------------

@contextmanager
def _cheap_password_hashes(seed_module):
    """The generator bcrypt-hashes a throwaway password per student at cost 12
    (a quarter second each). Training never uses them: hash at the minimum cost."""
    real = seed_module.bcrypt.gensalt
    seed_module.bcrypt.gensalt = lambda rounds=12, prefix=b"2b": real(rounds=4, prefix=prefix)
    try:
        yield
    finally:
        seed_module.bcrypt.gensalt = real


def simulated_year(seed: int, per_class: int = 25) -> list[dict]:
    """Snapshots of one simulated year: features + label + the rules' possible range."""
    import seed_edudevice_real as sim

    ranges = backend_rules.load("final_range")
    with _cheap_password_hashes(sim):
        _, grades, truth = sim.generate(per_class, seed)
    kind = {t["username"]: t["archetype"] for t in truth}
    tris = [sim.TRIMESTER_WINDOWS[n] for n in sorted(sim.TRIMESTER_WINDOWS)]
    first, last = tris[0][0], tris[-1][1]
    per_cs = defaultdict(lambda: tris)

    full = defaultdict(list)
    for g in grades:
        full[(g.username, g.class_subject_id)].append(
            scoring.DatedMark(g.category, Decimal(str(g.value)), Decimal(str(g.weight)), g.on))

    rows = []
    for cp in CHECKPOINTS:
        day = first + timedelta(days=round(cp * (last - first).days))
        upto = {k: [m for m in v if m.date <= day] for k, v in full.items()}
        cls = class_averages(upto, per_cs)
        for (user, cs), marks in upto.items():
            if kind[user] == "incomplete" or not marks:
                continue
            f = features(marks, day, cp, cls.get(cs), tris)
            if f is None:
                continue
            possible = ranges.final_range([(m.component, m.value, m.weight, m.date) for m in marks],
                                          tris, day)
            rows.append(dict(f, year=seed, checkpoint=cp,
                             final=float(scoring.subject_raw(full[(user, cs)], tris)),
                             possible_low=float(possible.low), possible_high=float(possible.high)))
    return rows


def _arrays(rows: list[dict]):
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    y = np.array([r["final"] for r in rows], dtype=float)
    return X, y


# ---------------------------------------------------------------------------
# Models and the range
# ---------------------------------------------------------------------------

class TodaysAverage:
    """The baseline: the final grade equals today's average."""

    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.asarray(X, dtype=float)[:, FEATURES.index("average")]


def candidates() -> dict:
    return {
        "baseline": TodaysAverage,
        "ridge": lambda: Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0))]),
    }


def held_out_predictions(make, rows: list[dict]) -> np.ndarray:
    """Every year predicted by a model fitted on the other years only."""
    X, y = _arrays(rows)
    years = np.array([r["year"] for r in rows])
    pred = np.empty(len(rows))
    for year in np.unique(years):
        out = years == year
        pred[out] = make().fit(X[~out], y[~out]).predict(X[out])
    return pred


def band_of(point: float) -> int:
    """0 = forecast below 5.5, 1 = 5.5 to 7, 2 = from 7. Students near the
    bottom of the scale scatter much less around their forecast (spread 0.35
    against 0.8 in the middle), so one pool of errors for everyone would make
    their range too wide and their chance to fail too mild."""
    return sum(point >= edge for edge in POINT_BANDS)


def group_errors(rows: list[dict], points: np.ndarray, residuals: np.ndarray) -> dict:
    """{(checkpoint, band): sorted held-out errors} - one pool per point in the
    year and forecast level ("Mondrian" conformal prediction)."""
    groups = defaultdict(list)
    for r, p, e in zip(rows, points, residuals):
        groups[(float(r["checkpoint"]), band_of(p))].append(round(float(e), 3))
    return {k: sorted(v) for k, v in groups.items()}


def fit(rows: list[dict]) -> dict:
    """The saved bundle: the fitted ridge model, which of the two candidates to
    use at each checkpoint, and the held-out errors per checkpoint and forecast
    level - the 80 % range and the chance to fail both come from them.

    The choice is made per checkpoint because the answer changes over the year:
    in autumn the model adds information to today's average, shortly before
    the end today's average is already almost the final grade and the model's
    corrections only add noise. Only plain data and sklearn objects go in, so
    the bundle loads anywhere.
    """
    X, y = _arrays(rows)
    cps = np.array([r["checkpoint"] for r in rows])
    held_out = {name: held_out_predictions(make, rows) for name, make in candidates().items()}
    choice = {}
    for cp in np.unique(cps):
        m = cps == cp
        errors = {name: float(np.abs(y[m] - p[m]).mean()) for name, p in held_out.items()}
        choice[float(cp)] = min(errors, key=errors.get)
    combined = np.array([held_out[choice[float(c)]][i] for i, c in enumerate(cps)])
    errors = group_errors(rows, combined, y - combined)
    return {"ridge": candidates()["ridge"]().fit(X, y), "choice": choice,
            "features": list(FEATURES), "errors": errors,
            "offsets": {k: tuple(float(v) for v in conformal_offsets(e, ALPHA)) for k, e in errors.items()},
            "alpha": ALPHA, "show_from": SHOW_FROM}


def _points(bundle: dict, X: np.ndarray, checkpoints) -> np.ndarray:
    """The point forecast: ridge or today's average, whichever the checkpoint uses."""
    X = np.asarray(X, dtype=float)
    ridge = bundle["ridge"].predict(X)
    average = X[:, bundle["features"].index("average")]
    return np.array([ridge[i] if bundle["choice"][c] == "ridge" else average[i]
                     for i, c in enumerate(checkpoints)])


def _group(bundle: dict, checkpoint: float, point: float) -> tuple:
    """The error pool for this forecast; a band never seen in training falls back to its neighbour."""
    band = band_of(point)
    for b in sorted(range(len(POINT_BANDS) + 1), key=lambda x: abs(x - band)):
        if (checkpoint, b) in bundle["errors"]:
            return checkpoint, b
    raise KeyError(f"no errors for checkpoint {checkpoint}")


def fail_probability(bundle: dict, X: np.ndarray, checkpoints) -> np.ndarray:
    """Chance that the final grade ends below the pass mark 4.6.

    The same held-out errors that make the 80 % range: how often, in the test
    years, would point + error have landed below 4.6? So the chance to fail
    and the likely band come from one model and cannot contradict each other.
    """
    point = _points(bundle, X, checkpoints)
    out = np.empty(len(point))
    for i, (p, c) in enumerate(zip(point, checkpoints)):
        errors = bundle["errors"][_group(bundle, c, p)]
        out[i] = np.searchsorted(errors, PASS - p, side="left") / len(errors)
    return out


def predict_interval(bundle: dict, X: np.ndarray, checkpoints) -> tuple:
    """(low, point, high) arrays, on the grade scale 4-10."""
    point = _points(bundle, X, checkpoints)
    offsets = [bundle["offsets"][_group(bundle, c, p)] for p, c in zip(point, checkpoints)]
    low = np.array([o[0] for o in offsets])
    high = np.array([o[1] for o in offsets])
    return np.clip(point + low, 4, 10), np.clip(point, 4, 10), np.clip(point + high, 4, 10)


def predict_current(bundle: dict, pairs: dict, trimesters: dict, today: date) -> dict:
    """{(student, cs): {"low", "point", "high", "fail_probability"}} for every pair
    the forecast applies to.

    pairs       {(student, cs): [DatedMark, ...]} - everything known today
    trimesters  {cs: [(start, end)]}, cut at the class's last lesson day
    No forecast before SHOW_FROM of the year has passed, or after the year ended.
    """
    cls = class_averages(pairs, trimesters)
    keys, rows, cps = [], [], []
    for (sid, cs), marks in pairs.items():
        tris = trimesters.get(cs)
        if not tris or not marks:
            continue
        share = year_share(today, tris[0][0], tris[-1][1])
        cp = checkpoint_for(share)
        if share < bundle["show_from"] or share >= 1 or cp is None:
            continue
        f = features(marks, today, share, cls.get(cs), tris)
        if f is None:
            continue
        keys.append((sid, cs))
        rows.append([f[name] for name in bundle["features"]])
        cps.append(cp)
    if not rows:
        return {}
    X = np.array(rows, dtype=float)
    low, point, high = predict_interval(bundle, X, cps)
    fail = fail_probability(bundle, X, cps)
    return {k: {"low": float(a), "point": float(b), "high": float(c), "fail_probability": float(p)}
            for k, a, b, c, p in zip(keys, low, point, high, fail)}


# ---------------------------------------------------------------------------
# Evaluation and training
# ---------------------------------------------------------------------------

def evaluate(rows: list[dict]) -> dict:
    """Error of both candidates and of the saved combination, and coverage of
    the 80 % range, all on years the model has not seen.

    Nested: for each year, the choice per checkpoint and the range come from
    the other years only, so the year is new on both levels.
    """
    _, y = _arrays(rows)
    cps = np.array([r["checkpoint"] for r in rows])
    years = np.array([r["year"] for r in rows])
    out = {"n_rows": len(rows), "n_years": int(len(np.unique(years))), "per_checkpoint": {}}

    errors = {name: np.abs(y - held_out_predictions(make, rows)) for name, make in candidates().items()}

    point, fail = np.zeros(len(rows)), np.zeros(len(rows))
    inside, inside_clipped, width = np.zeros(len(rows), bool), np.zeros(len(rows), bool), np.zeros(len(rows))
    for year in np.unique(years):
        bundle = fit([r for r in rows if r["year"] != year])
        idx = np.where(years == year)[0]
        X, _ = _arrays([rows[i] for i in idx])
        low, point[idx], high = predict_interval(bundle, X, cps[idx])
        fail[idx] = fail_probability(bundle, X, cps[idx])
        plow = np.array([rows[i]["possible_low"] for i in idx])
        phigh = np.array([rows[i]["possible_high"] for i in idx])
        clow, chigh = np.clip(low, plow, phigh), np.clip(high, plow, phigh)
        inside[idx] = (y[idx] >= low) & (y[idx] <= high)
        inside_clipped[idx] = (y[idx] >= clow) & (y[idx] <= chigh)
        width[idx] = chigh - clow
    errors["saved"] = np.abs(y - point)

    possible = np.array([(r["possible_low"] <= r["final"] <= r["possible_high"]) for r in rows])
    pwidth = np.array([r["possible_high"] - r["possible_low"] for r in rows])
    choice = fit(rows)["choice"]
    for cp in np.unique(cps):
        m = cps == cp
        out["per_checkpoint"][f"{cp:.2f}"] = {
            "n": int(m.sum()),
            "uses": choice[float(cp)],
            **{f"mae_{k}": round(float(e[m].mean()), 3) for k, e in errors.items()},
            "coverage": round(float(inside[m].mean()), 3),
            "coverage_after_clip": round(float(inside_clipped[m].mean()), 3),
            "likely_width": round(float(width[m].mean()), 2),
            "possible_width": round(float(pwidth[m].mean()), 2),
            "final_inside_possible": round(float(possible[m].mean()), 3),
        }
    out.update({f"mae_{k}": round(float(e.mean()), 3) for k, e in errors.items()})
    # Chance to fail: only shown where the rules leave the outcome open (undecided).
    # Is it calibrated - do 30 % predictions fail about 30 % of the time?
    failed = y < PASS
    open_ = np.array([r["possible_low"] < PASS <= r["possible_high"] for r in rows])
    out["fail"] = {
        "n_undecided": int(open_.sum()),
        "fail_rate": round(float(failed[open_].mean()), 3),
        "brier": round(float(((fail - failed) ** 2)[open_].mean()), 4),
        "brier_base_rate": round(float(((failed[open_].mean() - failed) ** 2)[open_].mean()), 4),
        "calibration": [],
    }
    for lo, hi in ((0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)):
        m = open_ & (fail >= lo) & (fail < hi)
        if m.any():
            out["fail"]["calibration"].append({"predicted": f"{lo:.0%}-{min(hi, 1):.0%}", "n": int(m.sum()),
                                               "mean_predicted": round(float(fail[m].mean()), 3),
                                               "actually_failed": round(float(failed[m].mean()), 3)})
    out["coverage"] = round(float(inside.mean()), 3)
    out["coverage_after_clip"] = round(float(inside_clipped.mean()), 3)
    out["final_inside_possible"] = round(float(possible.mean()), 3)
    return out


def print_report(metrics: dict) -> None:
    print(f"{metrics['n_rows']} snapshots from {metrics['n_years']} simulated years")
    print(f"mean error on unseen years: today's average {metrics['mae_baseline']:.3f}, "
          f"ridge {metrics['mae_ridge']:.3f}, saved combination {metrics['mae_saved']:.3f}")
    print(f"80 % range: coverage {metrics['coverage']:.3f} "
          f"(after clipping into the possible range {metrics['coverage_after_clip']:.3f}), target 0.800")
    print(f"final grade inside the rules' possible range: {metrics['final_inside_possible']:.3f}")
    f = metrics["fail"]
    print(f"chance to fail, undecided cases ({f['n_undecided']}, {f['fail_rate']:.0%} failed): Brier "
          f"{f['brier']:.4f} (always guessing the fail rate: {f['brier_base_rate']:.4f})")
    for c in f["calibration"]:
        print(f"   predicted {c['predicted']:>9}: n {c['n']:5}  mean {c['mean_predicted']:.2f}"
              f"  actually failed {c['actually_failed']:.2f}")
    print()
    print("share  uses      MAE avg  MAE ridge  coverage  likely width  possible width  final in possible")
    for cp, m in metrics["per_checkpoint"].items():
        print(f"{float(cp):5.0%}  {m['uses']:<8}  {m['mae_baseline']:7.3f}  {m['mae_ridge']:9.3f}"
              f"  {m['coverage_after_clip']:8.3f}  {m['likely_width']:12.2f}  {m['possible_width']:14.2f}"
              f"  {m['final_inside_possible']:17.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=8, help="number of simulated years")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent / "models"))
    args = ap.parse_args()

    rows = []
    for i in range(1, args.seeds + 1):
        rows += simulated_year(SEED_BASE + i)
    metrics = evaluate(rows)
    print_report(metrics)

    bundle = fit(rows)
    card = model_store.ModelCard(
        name=MODEL_NAME, task="grade_forecast",
        version=model_store.next_version(args.root, MODEL_NAME), created_at="",
        data_source="school_sim", synthetic_training_data=True, n_training_rows=len(rows),
        target="final raw subject grade (4-10), 80 % conformal range per checkpoint",
        features=list(FEATURES),
        hyperparameters={"candidates": ["todays_average", "ridge"], "choice": bundle["choice"],
                         "ridge_alpha": 1.0, "range": "80 %",
                         "checkpoints": CHECKPOINTS, "show_from": SHOW_FROM,
                         "seeds": [SEED_BASE + i for i in range(1, args.seeds + 1)]},
        notes="Trained on whole simulated years (other seeds than the server's sim data). "
              "Retrain on real data once a school year with real marks is complete.",
    )
    path = model_store.save(bundle, card, metrics, args.root)
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()