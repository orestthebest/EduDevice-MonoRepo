"""
grade_stats.py — the grading arithmetic for EduDevice, against the real schema.

This replaces the earlier version, which assumed the database stored M1/M2/M3
directly. It does not. `grades` stores individual weighted marks tagged with a
`category`, and the components are derived from them.

Mapping, taken from the grades.category ENUM in the live schema:

    M1  Mitarbeit    homework, mini_test, oral, presentation,
                     classwork, participation, behaviour
    M2  Schularbeit  schularbeit
    M3  Projekt      project

Weighting, from the school rules: M1 40%, M2 40%, M3 20%, grades on 4..10
where 10 is best.

Where the period lives
----------------------
The database decides this, not us. period_grades carries a CHECK:

    (kind IN ('M1','M2') AND trimester_id IS NOT NULL)
 OR (kind IN ('M3','FINAL') AND trimester_id IS NULL)

So M1 and M2 are per trimester, M3 and FINAL are per year. An M3 cannot be
attached to a trimester even if the teacher graded the project in October —
only the grade's `date` moves, never the period it counts in. That removes the
"which trimester does the Projekt belong to" question entirely.

Within a component, individual marks are combined by their own `weight` column
(a Schularbeit may count double a homework). Across components, the 40/40/20
split applies, renormalised over whatever exists so far, with the result marked
provisional until all three are in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_FLOOR
from typing import Iterable, Optional, Sequence

GRADE_MIN = Decimal("4")
GRADE_MAX = Decimal("10")

# The school's rounding rule: a fractional part of 0.6 or more rounds up.
# 4.6 -> 5 (pass), 4.5 -> 4 (fail). Not half-up. See round_grade.
ROUND_UP_AT = Decimal("0.6")

# A computed average of 4.6 or more rounds to 5 and passes.
PASS_THRESHOLD = Decimal("4.6")

CATEGORY_TO_COMPONENT = {
    "homework": "M1",
    "mini_test": "M1",
    "oral": "M1",
    "presentation": "M1",
    "classwork": "M1",
    "participation": "M1",
    "behaviour": "M1",
    "schularbeit": "M2",
    "project": "M3",
}

COMPONENT_WEIGHT = {
    "M1": Decimal("0.40"),
    "M2": Decimal("0.40"),
    "M3": Decimal("0.20"),
}

# M1 and M2 are reported per trimester; M3 and FINAL only for the whole year.
PER_TRIMESTER = ("M1", "M2")
PER_YEAR = ("M3", "FINAL")


class GradeError(ValueError):
    """A grade or component set violates the school's rules."""


def _dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def check_grade(value, label: str = "grade") -> Decimal:
    d = _dec(value)
    if d < GRADE_MIN or d > GRADE_MAX:
        raise GradeError(f"{label}: {value} is outside the 4..10 scale")
    return d


def component_of(category: str) -> str:
    try:
        return CATEGORY_TO_COMPONENT[category]
    except KeyError as exc:
        raise GradeError(f"unknown grades.category {category!r}") from exc


def round_grade(value: Decimal) -> int:
    """Round to a displayable whole grade using the school's rule.

    The school does NOT round half up. A fractional part of 0.6 or more rounds
    up; anything below stays. So 4.6 becomes a 5 and passes, while 4.5 stays a
    4 and fails. Standard rounding would hand a pass to every student sitting
    between 4.50 and 4.59, which is the difference between repeating the year
    and not.

    This mirrors rules.round_final, which has carried the same rule since
    September. The difference is that this version works in Decimal, so the
    comparison is exact and needs no epsilon: in binary floats 4.6 - 4 is
    0.5999999999999996, which is what made the first version of this return 4.

    Kept separate from the raw value on purpose: trends and charts want the
    unrounded number, the screen wants the integer.
    """
    d = _dec(value)
    whole = int(d.to_integral_value(rounding=ROUND_FLOOR))
    return whole + 1 if (d - whole) >= ROUND_UP_AT else whole


@dataclass(frozen=True)
class Mark:
    """One row of the grades table, reduced to what the arithmetic needs."""

    category: str
    value: Decimal
    weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        check_grade(self.value, self.category)
        if _dec(self.weight) <= 0:
            raise GradeError(f"{self.category}: weight must be positive")

    @property
    def component(self) -> str:
        return component_of(self.category)


@dataclass(frozen=True)
class Result:
    """A computed figure, raw and rounded, with where it came from."""

    raw: Optional[Decimal]
    rounded: Optional[int]
    provisional: bool
    parts_used: dict = field(default_factory=dict)
    missing: tuple = ()
    n_marks: int = 0

    @property
    def exists(self) -> bool:
        return self.raw is not None

    def as_dict(self) -> dict:
        # raw is rounded to 2 decimals for transport only. The full-precision
        # Decimal stays on the object for any further arithmetic.
        return {
            "raw": round(float(self.raw), 2) if self.raw is not None else None,
            "rounded": self.rounded,
            "provisional": self.provisional,
            "parts_used": {k: float(v) for k, v in self.parts_used.items()},
            "missing": list(self.missing),
            "n_marks": self.n_marks,
        }


def _weighted(pairs: Sequence[tuple[str, Optional[Decimal], Decimal]],
              n_marks: int = 0) -> Result:
    """Weighted mean over (label, value, weight), renormalised over what exists."""
    present = [(lbl, v, w) for lbl, v, w in pairs if v is not None]
    missing = tuple(lbl for lbl, v, _ in pairs if v is None)

    if not present:
        return Result(None, None, True, {}, missing, n_marks)

    total = sum(w for _, _, w in present)
    raw = sum(v * w for _, v, w in present) / total
    return Result(
        raw=raw,
        rounded=round_grade(raw),
        provisional=bool(missing),
        parts_used={lbl: (w / total) for lbl, _, w in present},
        missing=missing,
        n_marks=n_marks,
    )


def component_grade(marks: Iterable[Mark], component: str) -> Result:
    """Fold the individual marks of one component into a single figure.

    Marks are combined by their own `weight`, so a Schularbeit entered with
    weight 2.00 counts double a homework entered with 1.00.
    """
    selected = [m for m in marks if m.component == component]
    if not selected:
        return Result(None, None, True, {}, (component,), 0)

    total = sum(_dec(m.weight) for m in selected)
    raw = sum(_dec(m.value) * _dec(m.weight) for m in selected) / total
    by_cat: dict[str, Decimal] = {}
    for m in selected:
        by_cat[m.category] = by_cat.get(m.category, Decimal("0")) + _dec(m.weight)

    return Result(
        raw=raw,
        rounded=round_grade(raw),
        provisional=False,
        parts_used={c: w / total for c, w in by_cat.items()},
        missing=(),
        n_marks=len(selected),
    )


def subject_grade(m1: Optional[Decimal], m2: Optional[Decimal],
                  m3: Optional[Decimal], n_marks: int = 0) -> Result:
    """Combine the three components into the subject grade, 40/40/20.

    Any component that does not exist yet is left out and the remaining weights
    are renormalised, so a subject with only Mitarbeit so far reports that
    figure rather than a number dragged toward an invented zero. The result is
    flagged provisional until all three are present.
    """
    return _weighted(
        [
            ("M1", None if m1 is None else _dec(m1), COMPONENT_WEIGHT["M1"]),
            ("M2", None if m2 is None else _dec(m2), COMPONENT_WEIGHT["M2"]),
            ("M3", None if m3 is None else _dec(m3), COMPONENT_WEIGHT["M3"]),
        ],
        n_marks=n_marks,
    )


def mean_or_none(values: Sequence[Decimal]) -> Optional[Decimal]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(_dec(v) for v in vals) / Decimal(len(vals))
