"""
notenstatistiken.py — the Notenstatistiken computation layer (Ziel-M-3, v1).

Turns the raw rows in `grades` into the figures a student or a teacher actually
wants to look at, and emits them as JSON for the API and the device to render.
No pandas and no scikit-learn: the volumes per student are small, and keeping it
to the standard library plus SQLAlchemy means the same module could run on the
Pi if the device ever computes locally for the offline Ziele.

What it deliberately is NOT
---------------------------
This is descriptive statistics about grades that already exist. It is not the
risk model and not the forecast - those live in model_risk.py and
model_prognosis.py and write to risk_assessments / grade_forecasts. The display
shows both side by side, but they are computed separately and must not be
confused: one reports what happened, the other guesses what will.

What it computes
----------------
Per student x subject   components M1/M2/M3, the 40/40/20 subject grade, the
                        trimester trend, a breakdown by grade category, and the
                        student's standing against their class
Per student overall     mean across subjects, best and weakest subject, how many
                        subjects are in trouble
Per class x subject     mean, median, spread, the full grade distribution, the
                        same component and category breakdown, and who is below
                        the threshold - the view a teacher uses to judge whether
                        a topic landed

Roles
-----
view_for(role, ...) filters what comes back:
  schueler    only their own data; class figures appear as aggregates only,
              never as a list of named classmates
  lehrkraft   full class views, but only for class_subjects they teach
  admin       everything
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import create_engine, text

from grade_stats import (
    COMPONENT_WEIGHT,
    Mark,
    Result,
    component_grade,
    component_of,
    mean_or_none,
    round_grade,
    subject_grade,
)

URL_ENV_VAR = "EDUDEVICE_DB_URL"
DEFAULT_URL = "mysql+pymysql://root@localhost/edudevice_db"

# Two different thresholds doing two different jobs. Conflating them is the
# commonest confusion here.
#
#   FAIL_BELOW     the school's own pass mark. A computed average of 4.6 or more
#                  rounds up to 5 and passes, so below 4.6 is already failing.
#                  This is a fact about the school, not a tuning choice.
#
#   FRAGILE_BELOW  a warning band: passing today, but close enough that one bad
#                  Schularbeit flips it. An early-warning system has to fire
#                  before the failure, so this sits above the pass mark.
#                  This one IS a choice - confirm the value with the Betreuer.
FAIL_BELOW = Decimal("4.6")
FRAGILE_BELOW = Decimal("5.5")


def standing(raw) -> str:
    """'failing' | 'fragile' | 'ok' for a computed subject grade."""
    if raw is None:
        return "unknown"
    v = raw if isinstance(raw, Decimal) else Decimal(str(raw))
    if v < FAIL_BELOW:
        return "failing"
    if v < FRAGILE_BELOW:
        return "fragile"
    return "ok"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GradeRow:
    student_id: int
    class_subject_id: int
    category: str
    weight: Decimal
    value: Decimal
    on: date
    trimester: Optional[int]


def connect(url: Optional[str] = None):
    return create_engine(url or os.environ.get(URL_ENV_VAR) or DEFAULT_URL,
                         pool_pre_ping=True)


def load(engine, school_year_id: int = 1):
    """Read everything needed for one school year in three queries."""
    with engine.connect() as con:
        trimesters = [
            dict(r._mapping)
            for r in con.execute(
                text("SELECT id, number, start_date, end_date FROM trimesters "
                     "WHERE school_year_id = :y ORDER BY number"),
                {"y": school_year_id},
            )
        ]

        subjects = {
            r._mapping["class_subject_id"]: dict(r._mapping)
            for r in con.execute(
                text(
                    """
                    SELECT cs.id   AS class_subject_id,
                           cs.teacher_id,
                           c.id     AS class_id,
                           c.name   AS class_name,
                           s.name   AS subject_name
                    FROM class_subjects cs
                    JOIN classes  c ON c.id = cs.class_id
                    JOIN subjects s ON s.id = cs.subject_id
                    WHERE c.school_year_id = :y
                    """
                ),
                {"y": school_year_id},
            )
        }

        students = {
            r._mapping["id"]: dict(r._mapping)
            for r in con.execute(
                text("SELECT id, first_name, last_name, username FROM users "
                     "WHERE role = 'schueler'")
            )
        }

        enrolled = defaultdict(set)   # class_subject_id -> {student_id}
        for r in con.execute(text("SELECT class_subject_id, student_id "
                                  "FROM class_subject_students")):
            enrolled[r._mapping["class_subject_id"]].add(r._mapping["student_id"])

        rows = [
            GradeRow(
                student_id=r._mapping["student_id"],
                class_subject_id=r._mapping["class_subject_id"],
                category=r._mapping["category"],
                weight=Decimal(str(r._mapping["weight"])),
                value=Decimal(str(r._mapping["value"])),
                on=r._mapping["date"],
                trimester=None,
            )
            for r in con.execute(
                text(
                    """
                    SELECT g.student_id, g.class_subject_id, g.category,
                           g.weight, g.value, g.date
                    FROM grades g
                    JOIN class_subjects cs ON cs.id = g.class_subject_id
                    JOIN classes c ON c.id = cs.class_id
                    WHERE c.school_year_id = :y
                    """
                ),
                {"y": school_year_id},
            )
        ]

    # Tag each mark with its trimester by date. A mark outside every window keeps
    # trimester=None and is counted in the year figures but in no trimester.
    tagged = []
    for r in rows:
        num = None
        for t in trimesters:
            if t["start_date"] <= r.on <= t["end_date"]:
                num = t["number"]
                break
        tagged.append(
            GradeRow(r.student_id, r.class_subject_id, r.category, r.weight,
                     r.value, r.on, num)
        )

    return {
        "trimesters": trimesters,
        "subjects": subjects,
        "students": students,
        "enrolled": enrolled,
        "grades": tagged,
    }


# ---------------------------------------------------------------------------
# Per student x subject
# ---------------------------------------------------------------------------

def _marks(rows) -> list[Mark]:
    return [Mark(r.category, r.value, r.weight) for r in rows]


def subject_report(rows: list[GradeRow]) -> dict:
    """Everything about one student in one subject for the year."""
    marks = _marks(rows)

    m1_year = component_grade(marks, "M1")
    m2_year = component_grade(marks, "M2")
    m3_year = component_grade(marks, "M3")

    overall = subject_grade(m1_year.raw, m2_year.raw, m3_year.raw, n_marks=len(marks))

    # M1 and M2 per trimester; M3 is a year-level component by schema rule.
    by_trimester = {}
    for num in (1, 2, 3):
        tri_marks = _marks([r for r in rows if r.trimester == num])
        if not tri_marks:
            by_trimester[num] = None
            continue
        t_m1 = component_grade(tri_marks, "M1")
        t_m2 = component_grade(tri_marks, "M2")
        # The trimester figure uses M1 and M2 only - the schema forbids an M3
        # with a trimester_id, so the Projekt never belongs to one.
        combined = subject_grade(t_m1.raw, t_m2.raw, None, n_marks=len(tri_marks))
        by_trimester[num] = {
            "M1": t_m1.as_dict(),
            "M2": t_m2.as_dict(),
            "combined": combined.as_dict(),
        }

    points = [
        {"trimester": n, "value": round(float(v["combined"]["raw"]), 2)}
        for n, v in by_trimester.items()
        if v and v["combined"]["raw"] is not None
    ]
    trend = None
    if len(points) >= 2:
        delta = points[-1]["value"] - points[0]["value"]
        trend = {
            "delta": round(delta, 2),
            # 10 is the best grade, so a rise is an improvement.
            "direction": "up" if delta > 0.25 else ("down" if delta < -0.25 else "flat"),
            "points": points,
        }

    by_category = []
    cats = defaultdict(list)
    for r in rows:
        cats[r.category].append(r)
    for cat, rs in sorted(cats.items()):
        vals = [float(x.value) for x in rs]
        by_category.append(
            {
                "category": cat,
                "component": component_of(cat),
                "mean": round(sum(vals) / len(vals), 2),
                "n": len(vals),
                "min": min(vals),
                "max": max(vals),
            }
        )

    recent = sorted(rows, key=lambda r: r.on, reverse=True)[:5]

    return {
        "current": overall.as_dict(),
        "standing": standing(overall.raw),
        "components": {
            "M1": m1_year.as_dict(),
            "M2": m2_year.as_dict(),
            "M3": m3_year.as_dict(),
            "weights": {k: float(v) for k, v in COMPONENT_WEIGHT.items()},
        },
        "by_trimester": by_trimester,
        "trend": trend,
        "by_category": by_category,
        "recent": [
            {"date": r.on.isoformat(), "category": r.category,
             "value": float(r.value), "weight": float(r.weight)}
            for r in recent
        ],
        "n_marks": len(rows),
    }


# ---------------------------------------------------------------------------
# Per class x subject
# ---------------------------------------------------------------------------

def class_subject_report(data: dict, class_subject_id: int,
                         include_names: bool = True) -> dict:
    """The teacher's view of one subject in one class."""
    meta = data["subjects"][class_subject_id]
    rows = [r for r in data["grades"] if r.class_subject_id == class_subject_id]
    by_student = defaultdict(list)
    for r in rows:
        by_student[r.student_id].append(r)

    per_student = {}
    for sid, srows in by_student.items():
        per_student[sid] = subject_report(srows)

    finals = [
        (sid, rep["current"]["raw"])
        for sid, rep in per_student.items()
        if rep["current"]["raw"] is not None
    ]
    values = [v for _, v in finals]

    distribution = defaultdict(int)
    for _, v in finals:
        distribution[round_grade(Decimal(str(v)))] += 1

    comp_means = {}
    for comp in ("M1", "M2", "M3"):
        vals = [
            rep["components"][comp]["raw"]
            for rep in per_student.values()
            if rep["components"][comp]["raw"] is not None
        ]
        comp_means[comp] = round(sum(vals) / len(vals), 2) if vals else None

    cat_means = []
    cats = defaultdict(list)
    for r in rows:
        cats[r.category].append(float(r.value))
    for cat, vals in sorted(cats.items()):
        cat_means.append(
            {
                "category": cat,
                "component": component_of(cat),
                "mean": round(sum(vals) / len(vals), 2),
                "n": len(vals),
            }
        )

    tri_means = {}
    for num in (1, 2, 3):
        vals = [
            rep["by_trimester"][num]["combined"]["raw"]
            for rep in per_student.values()
            if rep["by_trimester"].get(num)
            and rep["by_trimester"][num]["combined"]["raw"] is not None
        ]
        tri_means[num] = round(sum(vals) / len(vals), 2) if vals else None

    at_risk = []
    for sid, v in sorted(finals, key=lambda x: x[1]):
        band = standing(v)
        if band in ("failing", "fragile"):
            entry = {"student_id": sid, "grade": round(v, 2), "standing": band}
            if include_names:
                s = data["students"].get(sid, {})
                entry["name"] = f"{s.get('first_name','?')} {s.get('last_name','?')}"
            at_risk.append(entry)

    return {
        "class_subject_id": class_subject_id,
        "class_name": meta["class_name"],
        "subject_name": meta["subject_name"],
        "teacher_id": meta["teacher_id"],
        "n_students_enrolled": len(data["enrolled"].get(class_subject_id, set())),
        "n_students_graded": len(finals),
        "mean": round(statistics.fmean(values), 2) if values else None,
        "median": round(statistics.median(values), 2) if values else None,
        "stdev": round(statistics.pstdev(values), 2) if len(values) > 1 else None,
        "min": round(min(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
        "distribution": {str(k): distribution[k] for k in sorted(distribution)},
        "by_component": comp_means,
        "by_category": cat_means,
        "by_trimester": tri_means,
        "at_risk": at_risk,
    }


# ---------------------------------------------------------------------------
# Per student, all subjects
# ---------------------------------------------------------------------------

def student_report(data: dict, student_id: int,
                   with_class_comparison: bool = True,
                   predictions: Optional[dict] = None) -> dict:
    """Everything a student sees about themselves.

    `predictions` is the output of risk_school.predict_current(): a mapping of
    (student_id, class_subject_id) -> risk fields. When given, each subject gains
    a `prediction` block. The descriptive figures and the predicted ones stay in
    separate keys on purpose - one reports what happened, the other guesses what
    will, and the screen must never blur them together.
    """
    rows = [r for r in data["grades"] if r.student_id == student_id]
    by_subject = defaultdict(list)
    for r in rows:
        by_subject[r.class_subject_id].append(r)

    subjects = []
    for cs_id, srows in sorted(by_subject.items()):
        meta = data["subjects"][cs_id]
        rep = subject_report(srows)
        rep.update(
            {
                "class_subject_id": cs_id,
                "subject_name": meta["subject_name"],
                "class_name": meta["class_name"],
            }
        )

        if with_class_comparison and rep["current"]["raw"] is not None:
            peers = []
            for other in data["enrolled"].get(cs_id, set()):
                if other == student_id:
                    continue
                orows = [r for r in data["grades"]
                         if r.student_id == other and r.class_subject_id == cs_id]
                if not orows:
                    continue
                v = subject_report(orows)["current"]["raw"]
                if v is not None:
                    peers.append(v)
            if peers:
                mine = rep["current"]["raw"]
                below = sum(1 for p in peers if p < mine)
                # Aggregates only - a student never sees who their classmates are.
                rep["class_comparison"] = {
                    "class_mean": round(statistics.fmean(peers + [mine]), 2),
                    "delta": round(mine - statistics.fmean(peers + [mine]), 2),
                    "percentile": round(100 * below / len(peers)),
                    "n_compared": len(peers) + 1,
                }

        if predictions:
            pred = predictions.get((student_id, cs_id))
            if pred:
                rep["prediction"] = dict(pred)
        subjects.append(rep)

    graded = [s["current"]["raw"] for s in subjects if s["current"]["raw"] is not None]
    overall = {
        "mean": round(statistics.fmean(graded), 2) if graded else None,
        "rounded": round_grade(Decimal(str(statistics.fmean(graded)))) if graded else None,
        "n_subjects": len(subjects),
        "n_subjects_graded": len(graded),
        "best_subject": None,
        "weakest_subject": None,
        "subjects_at_risk": 0,
        "provisional": any(s["current"]["provisional"] for s in subjects),
    }
    if graded:
        ranked = sorted(
            [s for s in subjects if s["current"]["raw"] is not None],
            key=lambda s: s["current"]["raw"],
        )
        overall["weakest_subject"] = ranked[0]["subject_name"]
        overall["best_subject"] = ranked[-1]["subject_name"]
        overall["subjects_failing"] = sum(
            1 for v in graded if standing(v) == "failing"
        )
        overall["subjects_fragile"] = sum(
            1 for v in graded if standing(v) == "fragile"
        )
        overall["subjects_at_risk"] = (
            overall["subjects_failing"] + overall["subjects_fragile"]
        )

    s = data["students"].get(student_id, {})
    return {
        "student": {
            "id": student_id,
            "name": f"{s.get('first_name','?')} {s.get('last_name','?')}",
            "username": s.get("username"),
        },
        "as_of": date.today().isoformat(),
        "overall": overall,
        "subjects": subjects,
    }


# ---------------------------------------------------------------------------
# Role gate
# ---------------------------------------------------------------------------

def view_for(data: dict, role: str, user_id: int,
             student_id: Optional[int] = None,
             class_subject_id: Optional[int] = None,
             predictions: Optional[dict] = None) -> dict:
    """Return only what this role is allowed to see.

    The rule a student relies on: they can see their own numbers and how they sit
    against the class as an aggregate, never a ranked list naming classmates.
    """
    role = role.lower()

    if role == "schueler":
        if student_id is not None and student_id != user_id:
            raise PermissionError("a student may only read their own statistics")
        return {"view": "student",
                **student_report(data, user_id, predictions=predictions)}

    if role == "lehrkraft":
        mine = {
            cs_id for cs_id, m in data["subjects"].items()
            if m["teacher_id"] == user_id
        }
        if class_subject_id is not None:
            if class_subject_id not in mine:
                raise PermissionError("that subject is taught by someone else")
            return {"view": "class_subject",
                    **class_subject_report(data, class_subject_id)}
        if student_id is not None:
            report = student_report(data, student_id, predictions=predictions)
            report["subjects"] = [
                s for s in report["subjects"] if s["class_subject_id"] in mine
            ]
            return {"view": "student", **report}
        return {
            "view": "teacher_overview",
            "teacher_id": user_id,
            "class_subjects": [class_subject_report(data, c) for c in sorted(mine)],
        }

    if role == "admin":
        if class_subject_id is not None:
            return {"view": "class_subject",
                    **class_subject_report(data, class_subject_id)}
        if student_id is not None:
            return {"view": "student",
                    **student_report(data, student_id, predictions=predictions)}
        return {
            "view": "school_overview",
            "class_subjects": [
                class_subject_report(data, c) for c in sorted(data["subjects"])
            ],
        }

    raise PermissionError(f"unknown role {role!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=None)
    ap.add_argument("--school-year", type=int, default=1)
    ap.add_argument("--role", default="schueler",
                    choices=["schueler", "lehrkraft", "admin"])
    ap.add_argument("--user-id", type=int, required=True)
    ap.add_argument("--student-id", type=int, default=None)
    ap.add_argument("--class-subject-id", type=int, default=None)
    ap.add_argument("--out", default=None, help="write JSON here instead of stdout")
    ap.add_argument("--with-predictions", action="store_true",
                    help="load the saved risk model and include its output")
    args = ap.parse_args()

    data = load(connect(args.url), args.school_year)

    predictions = None
    if args.with_predictions:
        import model_store
        import risk_school
        model, card, _ = model_store.load(risk_school.MODEL_NAME)
        predictions = risk_school.predict_current(data, model, card)
        if card.synthetic_training_data:
            # stderr, not stdout: stdout carries the JSON payload and nothing
            # else, so `python notenstatistiken.py ... > payload.json` stays
            # machine-readable. A human at a terminal still sees this.
            print("# NOTE: risk model was trained on generated data - its numbers "
                  "demonstrate the pipeline, they are not evidence.",
                  file=sys.stderr)

    payload = view_for(data, args.role, args.user_id,
                       args.student_id, args.class_subject_id,
                       predictions=predictions)
    text_out = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text_out)
        print(f"wrote {args.out}")
    else:
        print(text_out)


if __name__ == "__main__":
    main()
