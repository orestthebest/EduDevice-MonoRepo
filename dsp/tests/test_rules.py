"""
Hand-made test cases for the rule layer.

Run with:   python -m pytest tests/test_rules.py -v
or simply:  python tests/test_rules.py

Every case has an answer worked out by hand, so a change to rules.py that
breaks a school rule shows up immediately.
"""

import pytest

from src.rules import (
    SubjectState, attendance_status, absence_rate, best_case, final_grade,
    passes, percent_to_grade, required_remaining_avg, round_final, status,
    weighted_average, worst_case,
)


# ---------------------------------------------------------------------
# Percentage to grade
# ---------------------------------------------------------------------

def test_percent_band_bounds():
    # Lower and upper bound of every band
    assert percent_to_grade(0) == 4
    assert percent_to_grade(50) == 4
    assert percent_to_grade(51) == 5
    assert percent_to_grade(56) == 5
    assert percent_to_grade(57) == 6
    assert percent_to_grade(62) == 6
    assert percent_to_grade(63) == 7
    assert percent_to_grade(71) == 7
    assert percent_to_grade(72) == 8
    assert percent_to_grade(81) == 8
    assert percent_to_grade(82) == 9
    assert percent_to_grade(91) == 9
    assert percent_to_grade(92) == 10
    assert percent_to_grade(100) == 10


def test_percent_invalid():
    with pytest.raises(ValueError):
        percent_to_grade(-1)
    with pytest.raises(ValueError):
        percent_to_grade(101)


# ---------------------------------------------------------------------
# Rounding and pass rule
# ---------------------------------------------------------------------

def test_rounding():
    assert round_final(4.5) == 4       # below .6 -> down
    assert round_final(4.59) == 4
    assert round_final(4.6) == 5       # exactly .6 -> up
    assert round_final(7.0) == 7
    assert round_final(9.99) == 10


def test_pass_rule():
    assert passes(4.6) is True
    assert passes(4.59) is False
    assert passes(10.0) is True


# ---------------------------------------------------------------------
# Averages
# ---------------------------------------------------------------------

def test_weighted_average():
    assert weighted_average([5, 7]) == 6.0
    # Mini test counted twice as heavily as homework
    assert weighted_average([4, 10], [2, 1]) == pytest.approx(6.0)


def test_weighted_average_errors():
    with pytest.raises(ValueError):
        weighted_average([])
    with pytest.raises(ValueError):
        weighted_average([5, 6], [1])
    with pytest.raises(ValueError):
        weighted_average([3])           # 3 is not a valid grade


# ---------------------------------------------------------------------
# Final grade formula
# ---------------------------------------------------------------------

def test_final_grade_complete():
    # M1 = 8, M2 = 6, M3 = 5  ->  0.4*8 + 0.4*6 + 0.2*5 = 6.6
    state = SubjectState(m1=[8, 8, 8], m2=[6, 6, 6], m3=5)
    assert final_grade(state) == pytest.approx(6.6)


def test_final_grade_mixed_trimesters():
    # M1 = (7+8+9)/3 = 8, M2 = (4+5+6)/3 = 5, M3 = 10
    # 0.4*8 + 0.4*5 + 0.2*10 = 3.2 + 2.0 + 2.0 = 7.2
    state = SubjectState(m1=[7, 8, 9], m2=[4, 5, 6], m3=10)
    assert final_grade(state) == pytest.approx(7.2)


def test_final_grade_incomplete_needs_fill():
    state = SubjectState(m1=[8, None, None], m2=[7, None, None], m3=None)
    with pytest.raises(ValueError):
        final_grade(state)


# ---------------------------------------------------------------------
# Status: the worked example from the planning
# ---------------------------------------------------------------------

def test_secured_pass_example():
    # After T1 and T2: M1 = 8, 8 and M2 = 7, 7
    # Worst case: M1 = (8+8+4)/3 = 6.667, M2 = (7+7+4)/3 = 6.0, M3 = 4
    # 0.4*6.667 + 0.4*6.0 + 0.2*4 = 5.867 -> pass is secured
    state = SubjectState(m1=[8, 8, None], m2=[7, 7, None], m3=None)
    assert worst_case(state) == pytest.approx(5.8667, abs=1e-3)
    assert status(state) == "secured_pass"


def test_fail_unavoidable():
    # Everything graded and below the threshold
    state = SubjectState(m1=[4, 4, 4], m2=[4, 4, 4], m3=4)
    assert final_grade(state) == pytest.approx(4.0)
    assert status(state) == "fail_unavoidable"


def test_undecided_weak_student():
    # Weak but still open: T3 and the project can still save it
    state = SubjectState(m1=[4, 5, None], m2=[4, 4, None], m3=None)
    assert status(state) == "undecided"
    assert worst_case(state) < 4.6 < best_case(state)


def test_top_grades_in_t1_already_secure_the_pass():
    # Only T1 graded, but with 10s. Worst case:
    # M1 = (10+4+4)/3 = 6, M2 = 6, M3 = 4 -> 0.4*6 + 0.4*6 + 0.2*4 = 5.6
    # Because 4 is the lowest possible grade, the pass is already secured.
    state = SubjectState(m1=[10, None, None], m2=[10, None, None], m3=None)
    assert worst_case(state) == pytest.approx(5.6)
    assert status(state) == "secured_pass"


def test_single_ten_secures_the_pass():
    # A single 10 in M1 alone, nothing else graded. Worst case:
    # M1 = (10+4+4)/3 = 6, M2 = 4, M3 = 4
    # 0.4*6 + 0.4*4 + 0.2*4 = 2.4 + 1.6 + 0.8 = 4.8 -> secured
    state = SubjectState(m1=[10, None, None])
    assert worst_case(state) == pytest.approx(4.8)
    assert status(state) == "secured_pass"


def test_float_tolerance_on_threshold():
    # An average that lands on 4.6 only up to binary rounding must still pass
    state = SubjectState(m1=[8, 8, None], m2=[7, 7, None], m3=None)
    needed = required_remaining_avg(state)
    assert passes(final_grade(state, fill=max(needed, 4.0)))


def test_undecided_early_in_the_year():
    # Average T1 grades: still open in both directions
    state = SubjectState(m1=[6, None, None], m2=[5, None, None], m3=None)
    assert status(state) == "undecided"


def test_m3_narrows_the_range():
    # An early good project measurably improves the worst case
    without = SubjectState(m1=[6, None, None], m2=[6, None, None], m3=None)
    with_m3 = SubjectState(m1=[6, None, None], m2=[6, None, None], m3=10)
    assert worst_case(with_m3) > worst_case(without)


# ---------------------------------------------------------------------
# Required remaining average
# ---------------------------------------------------------------------

def test_required_remaining_avg_undecided():
    # M1 = 5 in T1, M2 = 4 in T1, four components plus M3 still open
    state = SubjectState(m1=[5, None, None], m2=[4, None, None], m3=None)
    needed = required_remaining_avg(state)
    # Filling exactly that value in must land on the pass threshold
    assert final_grade(state, fill=needed) == pytest.approx(4.6)


def test_required_remaining_avg_secured_is_low():
    # The pass is secured, so the required value falls below the scale
    state = SubjectState(m1=[8, 8, None], m2=[7, 7, None], m3=None)
    assert required_remaining_avg(state) < 4.0


def test_required_remaining_avg_complete_is_none():
    state = SubjectState(m1=[7, 7, 7], m2=[7, 7, 7], m3=7)
    assert required_remaining_avg(state) is None


# ---------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------

def test_absence_rate():
    assert absence_rate(10, 100) == pytest.approx(0.10)
    assert absence_rate(0, 50) == 0.0


def test_attendance_thresholds():
    assert attendance_status(19, 100) == "ok"
    assert attendance_status(20, 100) == "exam_required"   # exactly 20%
    assert attendance_status(29, 100) == "exam_required"
    assert attendance_status(30, 100) == "not_assessable"  # exactly 30%
    assert attendance_status(60, 100) == "not_assessable"


def test_attendance_invalid():
    with pytest.raises(ValueError):
        absence_rate(5, 0)
    with pytest.raises(ValueError):
        absence_rate(11, 10)


# ---------------------------------------------------------------------
# Validation of the state itself
# ---------------------------------------------------------------------

def test_state_rejects_invalid_grades():
    with pytest.raises(ValueError):
        SubjectState(m1=[11, None, None])       # above the scale
    with pytest.raises(ValueError):
        SubjectState(m2=[3, None, None])        # below the scale
    with pytest.raises(ValueError):
        SubjectState(m1=[7, 7])                 # wrong number of trimesters


def test_missing_count():
    assert SubjectState().missing_count() == 7            # 3 + 3 + 1
    assert SubjectState(m1=[7, 7, 7], m2=[7, 7, 7], m3=7).missing_count() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))