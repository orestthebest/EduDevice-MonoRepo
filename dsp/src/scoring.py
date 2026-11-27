"""
scoring.py — the rules of the nightly scoring job, without any database.

score_job.py reads the database, calls these functions and writes the results.
Keeping the rules here means every one of them can be tested with a handful of
made-up marks.

Three things are decided here
-----------------------------
1. The possible range of the final grade is computed by the backend's
   final_range.py (shared with the page); Envelope carries it through the
   alerts here. Not a model: everything still open - coming trimesters, the
   rest of the running one, parts without a mark - is filled with 4s and with
   10s. The likely range inside it comes from the prognosis model
   (prognosis_school.py). The subject average follows the same file: M1 and M2
   per trimester, then the mean of the trimesters.

2. Alerts for teachers. Each fires once and is not repeated every night.
   The anomaly evaluation (decisions.md) showed that a drop in the grade curve
   barely predicts failing, so a drop is reported as "changed", never as risk;
   failing risk comes only from the risk model and the rules.

3. The weekly observations for students ("What we noticed"). A change only
   counts when it is large compared with the student's OWN normal ups and
   downs, so a single new grade cannot flip "improving" on and off. At most
   three are shown, at least one positive one if there is any.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import backend_rules
from grade_stats import PASS_THRESHOLD, component_of, subject_grade

_YEAR = backend_rules.load("final_range")   # the year rule, shared with the page

RECENT_DAYS = 14            # a mark counts as "recent" for this long
MIN_HISTORY = 3             # marks needed before one can be "unusual"
SD_FLOOR = 0.75             # nobody's normal spread is counted as smaller than this
DROP_MIN = 1.5              # a drop must be at least this many grade points ...
DROP_SDS = 2.0              # ... and at least this many own standard deviations
TRIMESTER_MIN_CHANGE = 0.5  # trimester-to-trimester change worth mentioning ...
TRIMESTER_MIN_Z = 1.5       # ... and clearly larger than the own noise
FAIL_RISK_ALERT = 0.5       # model probability from which teachers get an alert
INSIGHTS_SHOWN = 3
ROUND_UP_GAP = 0.15         # "close to rounding up" only when at most this far away


def _day(d: date) -> str:
    return f"{d.day} {d:%b}"           # 9 Nov, not 09 Nov


def _pct(rate: float) -> str:
    return f"{rate * 100:.0f} %"       # 18 %, written like the rest of the page


def _a(n: int) -> str:
    return f"an {n}" if n == 8 else f"a {n}"

CATEGORY_LABEL = {
    "mini_test": "mini test", "oral": "oral exam", "homework": "homework",
    "classwork": "classwork", "presentation": "presentation", "participation": "participation",
    "behaviour": "behaviour mark", "schularbeit": "written exam", "project": "project",
}


@dataclass(eq=False)
class DatedMark:
    """A mark with its date (grade_stats.Mark has none). eq=False: two marks with
    the same value on the same day are still two marks."""
    category: str
    value: Decimal
    weight: Decimal
    date: date

    @property
    def component(self) -> str:
        return component_of(self.category)


def subject_raw(marks: list[DatedMark], trimesters=()) -> Optional[Decimal]:
    """Subject average with the same rules as the page: M1 and M2 averaged per
    trimester, then over the trimesters (final_range.year_components); missing
    parts left out. trimesters: [(start, end)] - without, the year is one block."""
    c = _YEAR.year_components([(m.component, m.value, m.weight, m.date) for m in marks], list(trimesters))
    return subject_grade(c["M1"], c["M2"], c["M3"]).raw


# ---------------------------------------------------------------------------
# 1. Possible range and status
# ---------------------------------------------------------------------------

@dataclass
class Envelope:
    """The possible range from final_range.py, plus today's average."""
    current: Optional[Decimal]     # today's average (missing parts left out)
    low: Decimal                   # everything still open all 4
    high: Decimal                  # everything still open all 10
    status: str                    # secured_pass | undecided | fail_unavoidable
    required: Optional[Decimal]    # average needed on everything still open, None if nothing is


# ---------------------------------------------------------------------------
# Helpers on a student's marks in one subject
# ---------------------------------------------------------------------------

def _values(marks: list[DatedMark]) -> list[float]:
    return [float(m.value) for m in marks]


def own_spread(values: list[float]) -> float:
    return max(SD_FLOOR, statistics.pstdev(values)) if len(values) > 1 else SD_FLOOR


def unusual_drop(marks: list[DatedMark], today: date) -> Optional[dict]:
    """Newest mark (if recent) far below this student's usual level in the subject."""
    if len(marks) <= MIN_HISTORY:
        return None
    ordered = sorted(marks, key=lambda m: m.date)
    newest, before = ordered[-1], ordered[:-1]
    if (today - newest.date).days > RECENT_DAYS:
        return None
    values = _values(before)
    usual, spread = statistics.fmean(values), own_spread(values)
    gap = usual - float(newest.value)
    if gap >= DROP_MIN and gap >= DROP_SDS * spread:
        return {"mark": newest, "usual": usual, "spread": spread, "gap": gap}
    return None


def trimester_change(marks: list[DatedMark], trimester_of) -> Optional[dict]:
    """Current vs previous trimester (Mitarbeit + Schularbeit), in own-noise units."""
    by_tri: dict[int, list[float]] = {}
    for m in marks:
        t = trimester_of(m.date)
        if t is not None and m.component in ("M1", "M2"):
            by_tri.setdefault(t, []).append(float(m.value))
    tris = sorted(t for t, v in by_tri.items() if len(v) >= 2)
    if len(tris) < 2:
        return None
    prev, cur = by_tri[tris[-2]], by_tri[tris[-1]]
    d = statistics.fmean(cur) - statistics.fmean(prev)
    spread = own_spread(_values(marks))
    z = d / (spread * (1 / len(cur) + 1 / len(prev)) ** 0.5)
    return {"prev": statistics.fmean(prev), "cur": statistics.fmean(cur), "d": d, "z": z}


# ---------------------------------------------------------------------------
# 2. Alerts for teachers
# ---------------------------------------------------------------------------

@dataclass
class AlertDraft:
    type: str        # alerts.type enum
    severity: str    # info | warning | critical
    message: str


def alerts_for(env: Envelope, fail_probability: Optional[float], absence: Optional[dict],
               marks: list[DatedMark], today: date, model_note: str) -> list[AlertDraft]:
    out: list[AlertDraft] = []
    if env.status == "fail_unavoidable":
        out.append(AlertDraft("fail_risk", "critical",
                              f"Cannot pass anymore: even 10s on everything still open give at most "
                              f"{float(env.high):.2f} (pass mark {PASS_THRESHOLD})."))
    elif env.status == "undecided" and fail_probability is not None and fail_probability >= FAIL_RISK_ALERT:
        need = "" if env.required is None else f" Needs {float(env.required):.2f} on the remaining work."
        out.append(AlertDraft("fail_risk", "critical" if fail_probability >= 0.7 else "warning",
                              f"Fail probability {_pct(fail_probability)} ({model_note}). "
                              f"Current average {float(env.current):.2f}.{need}"))

    if absence:
        if absence["status"] == "not_assessable":
            out.append(AlertDraft("attendance_30", "critical",
                                  f"Missed {absence['rate'] * 100:.1f} % of the year's lessons - over 30 %, "
                                  f"not assessable."))
        elif absence["status"] == "exam_required":
            out.append(AlertDraft("attendance_20", "warning",
                                  f"Missed {absence['rate'] * 100:.1f} % of the year's lessons - over 20 %, "
                                  f"extra exam required."))
        elif absence["status"] == "trending":
            out.append(AlertDraft("attendance_trend", "info",
                                  f"At the current pace about {_pct(absence['projected_rate'])} of the "
                                  f"year's lessons will be missed (now {absence['rate'] * 100:.1f} %)."))

    drop = unusual_drop(marks, today)
    if drop:
        m = drop["mark"]
        out.append(AlertDraft("deterioration", "info",
                              f"Latest mark {float(m.value):g} ({CATEGORY_LABEL.get(m.category, m.category)}, "
                              f"{_day(m.date)}) is well below this student's usual level "
                              f"({drop['usual']:.1f} ± {drop['spread']:.1f}). A change, not a failing risk."))
    return out


# ---------------------------------------------------------------------------
# 3. Weekly observations for the student
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    class_subject_id: Optional[int]   # None = about all subjects
    kind: str
    tone: str                         # positive | neutral | attention
    score: float
    message: str                      # never contains the subject name - the page adds it
    params: dict = field(default_factory=dict)   # the numbers in the message, so the page can translate it


def _effect(marks: list[DatedMark], mark: DatedMark, trimesters=()) -> Optional[float]:
    """How much `mark` moved the subject average (with it minus without it)."""
    with_it = subject_raw(marks, trimesters)
    without = subject_raw([m for m in marks if m is not mark], trimesters)
    if with_it is None or without is None:
        return None
    return float(with_it - without)


def subject_insights(cs_id: int, marks: list[DatedMark], raw: Optional[Decimal], absence: Optional[dict],
                     today: date, trimester_of, trimesters=()) -> list[Insight]:
    out: list[Insight] = []
    ordered = sorted(marks, key=lambda m: m.date)

    change = trimester_change(marks, trimester_of)
    if change and abs(change["d"]) >= TRIMESTER_MIN_CHANGE and abs(change["z"]) >= TRIMESTER_MIN_Z:
        if change["d"] > 0:
            out.append(Insight(cs_id, "trimester_up", "positive", abs(change["z"]),
                               f"Up {change['d']:.1f} on last trimester ({change['prev']:.1f} → "
                               f"{change['cur']:.1f}).",
                               params={"diff": round(change["d"], 1), "prev": round(change["prev"], 1),
                                       "cur": round(change["cur"], 1)}))
        else:
            out.append(Insight(cs_id, "trimester_down", "attention", abs(change["z"]),
                               f"Down {-change['d']:.1f} compared with last trimester ({change['prev']:.1f} → "
                               f"{change['cur']:.1f}). Worth a look before the next written exam.",
                               params={"diff": round(-change["d"], 1), "prev": round(change["prev"], 1),
                                       "cur": round(change["cur"], 1)}))

    newest = ordered[-1] if ordered else None
    if newest and (today - newest.date).days <= RECENT_DAYS:
        label = CATEGORY_LABEL.get(newest.category, newest.category)
        effect = _effect(marks, newest, trimesters)
        before = _values(ordered[:-1])
        usual = statistics.fmean(before) if before else None
        about = {"category": newest.category, "date": newest.date.isoformat(), "value": float(newest.value)}
        if effect is not None and effect >= 0.25:
            out.append(Insight(cs_id, "recent_lift", "positive", 1.0 + 2 * effect,
                               f"Your {label} on {_day(newest.date)} ({float(newest.value):g}) lifted your "
                               f"average by {effect:.2f}.",
                               params=dict(about, effect=round(effect, 2))))
        elif usual is not None and len(before) >= MIN_HISTORY and float(newest.value) >= usual + 0.75:
            out.append(Insight(cs_id, "good_mark", "positive", 0.8,
                               f"Your {label} on {_day(newest.date)} "
                               f"({float(newest.value):g}) was above your usual level.",
                               params=about))

    if len(ordered) >= MIN_HISTORY + 3:
        earlier = _values(ordered[:-3])
        usual = statistics.fmean(earlier)
        if all(float(m.value) >= usual + 0.5 for m in ordered[-3:]):
            out.append(Insight(cs_id, "streak", "positive", 1.2,
                               "Your last three marks were all above your usual level."))

    drop = unusual_drop(marks, today)
    if drop:
        m = drop["mark"]
        out.append(Insight(cs_id, "unusual_drop", "attention", 1.3,
                           f"Your {CATEGORY_LABEL.get(m.category, m.category)} on {_day(m.date)} "
                           f"({float(m.value):g}) was well below your usual level ({drop['usual']:.1f}). "
                           f"One mark - but worth a look.",
                           params={"category": m.category, "date": m.date.isoformat(), "value": float(m.value),
                                   "usual": round(drop["usual"], 1)}))

    if raw is not None:
        frac = float(raw) - int(raw)
        gap = round(0.6 - frac, 2)
        if 0 < gap <= ROUND_UP_GAP and int(raw) + 1 <= 10:
            # a nudge, not news: weaker than any real change in the marks
            out.append(Insight(cs_id, "near_round_up", "neutral", 0.7 - gap,
                               f"Your average is {float(raw):.2f} - just {gap:.2f} short of rounding up "
                               f"to {_a(int(raw) + 1)}.",
                               params={"average": round(float(raw), 2), "gap": gap, "next": int(raw) + 1}))

    if absence and absence.get("projected_rate") is not None and 0.15 <= absence["projected_rate"] < 0.20:
        out.append(Insight(cs_id, "absence_pace", "attention", 1.1,
                           f"At your current pace you'd miss about {_pct(absence['projected_rate'])} of this "
                           f"year's lessons. From 20 % an extra exam is required.",
                           params={"rate": round(absence["projected_rate"] * 100)}))
    return out


def attendance_streak(held_lessons: list[tuple[date, int]], today: date) -> Optional[Insight]:
    """held_lessons: (date, minutes_missed) of every lesson held so far, all subjects.
    'No missed lessons in the last four weeks' - only with enough lessons to mean something."""
    window = [missed for day, missed in held_lessons if today - timedelta(days=28) <= day <= today]
    if len(window) >= 8 and sum(window) == 0:
        return Insight(None, "attendance_clean", "positive", 0.9,
                       "No missed lessons in the last four weeks.")
    return None


def pick(candidates: list[Insight], n: int = INSIGHTS_SHOWN) -> list[Insight]:
    """The strongest n, at most two 'attention', at least one positive if there is one,
    at most two about the same subject."""
    chosen: list[Insight] = []
    per_subject: dict = {}
    for c in sorted(candidates, key=lambda c: c.score, reverse=True):
        if len(chosen) == n:
            break
        if c.tone == "attention" and sum(x.tone == "attention" for x in chosen) == 2:
            continue
        if per_subject.get(c.class_subject_id, 0) == 2 and c.class_subject_id is not None:
            continue
        chosen.append(c)
        per_subject[c.class_subject_id] = per_subject.get(c.class_subject_id, 0) + 1
    positives = [c for c in candidates if c.tone == "positive"]
    if positives and not any(c.tone == "positive" for c in chosen):
        best = max(positives, key=lambda c: c.score)
        if len(chosen) == n:
            chosen[-1] = best
        else:
            chosen.append(best)
    return chosen


def week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())
