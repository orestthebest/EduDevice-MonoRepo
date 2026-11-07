"""
EduDevice - rule layer.

Contains all deterministic school rules: grade scale, grade formula,
rounding, pass/fail status and attendance thresholds.

No machine learning and no data access here. Everything in this module is
exact school regulation, so the results are always explainable and the
module works unchanged on OULAD data and on the real school data.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

MIN_GRADE = 4.0
MAX_GRADE = 10.0

# A final average of 4.6 or higher rounds up to 5 and counts as a pass.
PASS_THRESHOLD = 4.6

# Tolerance for float comparisons. Averages such as 0.4*6.667 + ... do not
# land exactly on 4.6 in binary, so comparisons are made with this margin.
# It is far smaller than any real grade difference and never changes a rule.
EPS = 1e-9

# Weights of the year components
WEIGHT_M1 = 0.4   # Mitarbeit
WEIGHT_M2 = 0.4   # Schularbeit
WEIGHT_M3 = 0.2   # Projekt (once per year)

TRIMESTERS = 3

# Attendance thresholds per subject (share of lessons missed)
ATTENDANCE_EXAM_THRESHOLD = 0.20   # exam at year end required
ATTENDANCE_FAIL_THRESHOLD = 0.30   # subject can no longer be assessed

# Percentage to grade (used to convert OULAD scores)
# Lower bound of the next grade -> grade below it
_PERCENT_BANDS = [(51, 4), (57, 5), (63, 6), (72, 7), (82, 8), (92, 9)]


# ---------------------------------------------------------------------
# Grade scale
# ---------------------------------------------------------------------

def percent_to_grade(percent: float) -> int:
    """Convert a percentage score (0-100) to a grade on the 4-10 scale.

    4: 0-50, 5: 51-56, 6: 57-62, 7: 63-71, 8: 72-81, 9: 82-91, 10: 92-100
    """
    if not 0 <= percent <= 100:
        raise ValueError(f"percent must be between 0 and 100, got {percent}")
    for lower_bound, grade in _PERCENT_BANDS:
        if percent < lower_bound:
            return grade
    return 10


def round_final(value: float) -> int:
    """Round a final average to a whole grade (.6 and above rounds up)."""
    _check_grade(value, "value")
    whole = int(value)
    # Without EPS this fails: 4.6 - 4 is 0.5999999999999996 in binary
    return whole + 1 if (value - whole) >= 0.6 - EPS else whole


def passes(final_value: float) -> bool:
    """True if the (unrounded) final average is a pass."""
    return final_value >= PASS_THRESHOLD - EPS


# ---------------------------------------------------------------------
# Averages
# ---------------------------------------------------------------------

def weighted_average(values, weights=None) -> float:
    """Weighted average of single grades, e.g. all M1 entries of a trimester.

    Without weights this is the plain mean. Used to build a component grade
    out of individual entries when the teacher has not entered one.
    """
    if not values:
        raise ValueError("values must not be empty")
    for v in values:
        _check_grade(v, "grade")

    if weights is None:
        return sum(values) / len(values)

    if len(weights) != len(values):
        raise ValueError("values and weights must have the same length")
    if any(w <= 0 for w in weights):
        raise ValueError("weights must be positive")
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


# ---------------------------------------------------------------------
# State of a student in one subject
# ---------------------------------------------------------------------

@dataclass
class SubjectState:
    """Known component grades of a student in one subject in one school year.

    m1 and m2 each hold three entries, one per trimester; None means not
    graded yet. m3 is the year project, None until it is graded.
    """
    m1: list = field(default_factory=lambda: [None] * TRIMESTERS)
    m2: list = field(default_factory=lambda: [None] * TRIMESTERS)
    m3: float | None = None

    def __post_init__(self):
        for name, values in (("m1", self.m1), ("m2", self.m2)):
            if len(values) != TRIMESTERS:
                raise ValueError(f"{name} must have {TRIMESTERS} entries")
            for v in values:
                if v is not None:
                    _check_grade(v, name)
        if self.m3 is not None:
            _check_grade(self.m3, "m3")

    def missing_count(self) -> int:
        """Number of components that are still ungraded."""
        missing = sum(1 for v in self.m1 + self.m2 if v is None)
        return missing + (1 if self.m3 is None else 0)

    def is_complete(self) -> bool:
        return self.missing_count() == 0


def final_grade(state: SubjectState, fill: float | None = None) -> float:
    """Final year average from the formula.

    0.4 * mean(M1 trimesters) + 0.4 * mean(M2 trimesters) + 0.2 * M3

    Ungraded components are replaced by `fill`. Without `fill` the state
    must be complete.
    """
    if fill is None and not state.is_complete():
        raise ValueError("state is incomplete - pass a fill value")
    if fill is not None:
        _check_grade(fill, "fill")

    m1 = [v if v is not None else fill for v in state.m1]
    m2 = [v if v is not None else fill for v in state.m2]
    m3 = state.m3 if state.m3 is not None else fill

    return (WEIGHT_M1 * (sum(m1) / TRIMESTERS)
            + WEIGHT_M2 * (sum(m2) / TRIMESTERS)
            + WEIGHT_M3 * m3)


def best_case(state: SubjectState) -> float:
    """Best possible final grade: every remaining component is a 10."""
    return final_grade(state, fill=MAX_GRADE)


def worst_case(state: SubjectState) -> float:
    """Worst possible final grade: every remaining component is a 4."""
    return final_grade(state, fill=MIN_GRADE)


def status(state: SubjectState) -> str:
    """'secured_pass', 'fail_unavoidable' or 'undecided'.

    Decided purely by the formula, without any model. Only 'undecided'
    cases need a risk prediction.
    """
    if passes(worst_case(state)):
        return "secured_pass"
    if not passes(best_case(state)):
        return "fail_unavoidable"
    return "undecided"


def required_remaining_avg(state: SubjectState) -> float | None:
    """Average needed in all remaining components to pass.

    Returns None when nothing is left to grade. Values below 4 mean the pass
    is already secured; values above 10 mean it is out of reach. Check
    status() first and use this number for display.
    """
    if state.is_complete():
        return None

    # final_grade is linear in the fill value, so two points determine it.
    at_zero = final_grade(state, fill=MIN_GRADE) - MIN_GRADE * _fill_slope(state)
    slope = _fill_slope(state)
    return (PASS_THRESHOLD - at_zero) / slope


def _fill_slope(state: SubjectState) -> float:
    """How much the final grade changes per point on the remaining components."""
    missing_m1 = sum(1 for v in state.m1 if v is None)
    missing_m2 = sum(1 for v in state.m2 if v is None)
    missing_m3 = 1 if state.m3 is None else 0
    return (WEIGHT_M1 * missing_m1 / TRIMESTERS
            + WEIGHT_M2 * missing_m2 / TRIMESTERS
            + WEIGHT_M3 * missing_m3)


# ---------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------

def absence_rate(missed_lessons: int, held_lessons: int) -> float:
    """Share of lessons missed. Cancelled lessons must not be counted."""
    if held_lessons <= 0:
        raise ValueError("held_lessons must be positive")
    if not 0 <= missed_lessons <= held_lessons:
        raise ValueError("missed_lessons must be between 0 and held_lessons")
    return missed_lessons / held_lessons


def attendance_status(missed_lessons: int, held_lessons: int) -> str:
    """'ok', 'exam_required' (>= 20%) or 'not_assessable' (>= 30%)."""
    rate = absence_rate(missed_lessons, held_lessons)
    if rate >= ATTENDANCE_FAIL_THRESHOLD:
        return "not_assessable"
    if rate >= ATTENDANCE_EXAM_THRESHOLD:
        return "exam_required"
    return "ok"


def projected_absence_rate(missed_lessons: int, held_lessons: int,
                           planned_lessons: int) -> float:
    """Absence rate at year end if the student keeps missing at the current rate.

    Used for the early warning: the alert fires before a threshold is
    actually crossed.
    """
    if planned_lessons < held_lessons:
        raise ValueError("planned_lessons must be at least held_lessons")
    return absence_rate(missed_lessons, held_lessons)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _check_grade(value: float, name: str) -> None:
    if not MIN_GRADE <= value <= MAX_GRADE:
        raise ValueError(f"{name} must be between {MIN_GRADE} and {MAX_GRADE}, "
                         f"got {value}")