"""
test_grade_stats.py — the grading arithmetic, checked against the school's rules.

These are the tests that matter most in the whole project. Everything else
(models, statistics, the display) reads numbers that come out of grade_stats.
If this module is wrong, every figure on the device is wrong and nothing
downstream would notice.

Each test names the rule it is defending, so a failure says which school rule
got broken rather than just which assertion blew up.
"""

from decimal import Decimal

import pytest

from grade_stats import (COMPONENT_WEIGHT, GRADE_MAX, GRADE_MIN, PASS_THRESHOLD,
                         GradeError,
                         Mark, check_grade, component_grade, component_of,
                         mean_or_none, round_grade, subject_grade)


def D(x):
    return Decimal(str(x))


# ---------------------------------------------------------------- the scale

def test_scale_is_four_to_ten():
    """Grades run 4..10 with 10 best. Not 1..5, not 0..100."""
    assert GRADE_MIN == Decimal("4")
    assert GRADE_MAX == Decimal("10")


@pytest.mark.parametrize("value", [4, 4.5, 7, 10, "6.75"])
def test_check_grade_accepts_in_range(value):
    assert check_grade(value) == D(value)


@pytest.mark.parametrize("value", [3, 3.99, 10.01, 11, 0, -5, 100])
def test_check_grade_rejects_out_of_range(value):
    with pytest.raises(GradeError):
        check_grade(value)


def test_check_grade_names_the_field():
    """The error has to say which mark was bad, or it is useless in a seeder."""
    with pytest.raises(GradeError, match="schularbeit"):
        check_grade(2, "schularbeit")


# -------------------------------------------------- category to component

def test_every_m1_category_maps_to_m1():
    for cat in ("homework", "mini_test", "oral", "presentation",
                "classwork", "participation", "behaviour"):
        assert component_of(cat) == "M1", cat


def test_schularbeit_is_m2_and_project_is_m3():
    assert component_of("schularbeit") == "M2"
    assert component_of("project") == "M3"


def test_unknown_category_raises_rather_than_guessing():
    """A new ENUM value in the DB must break loudly, not be silently dropped."""
    with pytest.raises(GradeError, match="exam"):
        component_of("exam")


# ------------------------------------------------------------- rounding

@pytest.mark.parametrize("raw,expect", [
    ("4.0", 4), ("4.49", 4), ("4.5", 4), ("4.59", 4),   # .5 does NOT round up
    ("4.6", 5), ("4.9", 5),
    ("5.5", 5), ("5.6", 6), ("6.59", 6), ("6.6", 7),
    ("9.6", 10), ("10.0", 10),
])
def test_round_grade_rounds_up_at_six_tenths(raw, expect):
    """The school rounds up at .6, not at .5.

    This is a school rule, not a convention we picked. Standard half-up
    rounding would promote everything from 4.50 upward to a 5, which is the
    difference between repeating the year and not for exactly the students
    sitting closest to the line.
    """
    assert round_grade(Decimal(raw)) == expect


def test_the_four_point_six_case():
    """The bug that started all this.

    4.6 must round to 5. With binary floats, 4.6 - 4 == 0.5999999999999996,
    so a float check of `frac >= 0.6` returned 4 and failed a student who had
    passed. rules.py solves it with an epsilon; grade_stats works in Decimal,
    where the comparison is exact and no epsilon is needed.
    """
    assert round_grade(Decimal("4.6")) == 5
    assert round_grade(Decimal("4.5")) == 4
    assert round_grade(Decimal("4.5999")) == 4


def test_round_grade_agrees_with_the_rule_layer():
    """grade_stats and rules must never disagree about a grade.

    Two modules now implement the same school rule - rules.py in float for the
    OULAD pipeline, grade_stats.py in Decimal for the school database. If they
    ever drift apart, one half of the project fails students the other half
    passes. This test is the tripwire.
    """
    import rules

    value = Decimal("4.00")
    while value <= Decimal("10.00"):
        assert round_grade(value) == rules.round_final(float(value)), value
        value += Decimal("0.01")


# ---------------------------------------------- marks inside a component

def test_component_grade_is_weighted_by_the_mark_weight():
    """A Schularbeit entered at weight 2 counts double a homework at weight 1."""
    marks = [
        Mark("schularbeit", D(10), D(2)),
        Mark("schularbeit", D(4), D(1)),
    ]
    # (10*2 + 4*1) / 3 = 8
    assert component_grade(marks, "M2").raw == D(8)


def test_component_grade_ignores_other_components():
    marks = [
        Mark("homework", D(10)),
        Mark("schularbeit", D(4)),
        Mark("project", D(7)),
    ]
    assert component_grade(marks, "M1").raw == D(10)
    assert component_grade(marks, "M2").raw == D(4)
    assert component_grade(marks, "M3").raw == D(7)


def test_missing_component_is_none_not_zero():
    """An ungraded component must not be read as a grade of 0.

    This is the single most dangerous possible bug in the project: treating
    "no Schularbeit yet" as a zero would fail half the school in October.
    """
    result = component_grade([Mark("homework", D(8))], "M2")
    assert result.raw is None
    assert result.rounded is None
    assert result.missing == ("M2",)
    assert result.n_marks == 0


def test_component_reports_which_categories_it_used():
    """Needed by the display: 'Mitarbeit (3 Hausübungen, 1 Test)'."""
    marks = [
        Mark("homework", D(8)), Mark("homework", D(6)),
        Mark("oral", D(9), D(2)),
    ]
    result = component_grade(marks, "M1")
    assert set(result.parts_used) == {"homework", "oral"}
    assert result.n_marks == 3
    # oral carries weight 2 of a total of 4
    assert result.parts_used["oral"] == Decimal("2") / Decimal("4")


def test_zero_or_negative_weight_is_rejected():
    with pytest.raises(GradeError):
        Mark("homework", D(8), D(0))
    with pytest.raises(GradeError):
        Mark("homework", D(8), D(-1))


# --------------------------------------------------- the 40/40/20 split

def test_weights_are_forty_forty_twenty():
    assert COMPONENT_WEIGHT["M1"] == Decimal("0.40")
    assert COMPONENT_WEIGHT["M2"] == Decimal("0.40")
    assert COMPONENT_WEIGHT["M3"] == Decimal("0.20")
    assert sum(COMPONENT_WEIGHT.values()) == Decimal("1.00")


def test_full_year_uses_all_three_weights():
    # 8*0.4 + 6*0.4 + 10*0.2 = 3.2 + 2.4 + 2.0 = 7.6
    result = subject_grade(D(8), D(6), D(10))
    assert result.raw == D("7.6")
    assert result.rounded == 8
    assert result.provisional is False
    assert result.missing == ()


def test_partial_year_renormalises_instead_of_assuming_zero():
    """With only M1 and M2 in, the grade is their 50/50 mean, not dragged down.

    0.4 and 0.4 renormalise to 0.5 and 0.5. If M3 were treated as a zero the
    answer would be 5.6 instead of 7, and every student would look like they
    were failing until the Projekt was graded.
    """
    result = subject_grade(D(8), D(6), None)
    assert result.raw == D(7)
    assert result.provisional is True
    assert result.missing == ("M3",)
    assert result.parts_used == {"M1": Decimal("0.5"), "M2": Decimal("0.5")}


def test_only_mitarbeit_reports_mitarbeit():
    result = subject_grade(D("6.5"), None, None)
    assert result.raw == D("6.5")
    assert result.provisional is True
    assert set(result.missing) == {"M2", "M3"}


def test_nothing_graded_yet_is_none():
    result = subject_grade(None, None, None)
    assert result.raw is None
    assert result.rounded is None
    assert result.provisional is True


# ------------------------------------------------------- the pass mark

def test_pass_mark_boundary():
    """4.6 passes (rounds to 5), 4.59 does not.

    The school rule is on the rounded grade: a computed average of 4.6 becomes
    a 5 and the student passes. The raw number is kept for the trend lines, but
    pass/fail is decided on the rounded value.
    """
    assert PASS_THRESHOLD == Decimal("4.6")
    assert round_grade(Decimal("4.60")) == 5      # pass
    assert round_grade(Decimal("4.59")) == 4      # fail
    assert round_grade(Decimal("4.599999")) == 4  # fail
    # and the two definitions of passing agree
    assert (Decimal("4.60") >= PASS_THRESHOLD) is (round_grade(Decimal("4.60")) >= 5)
    assert (Decimal("4.59") >= PASS_THRESHOLD) is (round_grade(Decimal("4.59")) >= 5)


def test_a_realistic_failing_student():
    marks = [
        Mark("homework", D(4)), Mark("homework", D(4)),
        Mark("classwork", D(4)),
        Mark("schularbeit", D(4), D(2)), Mark("schularbeit", D(5)),
        Mark("project", D(5)),
    ]
    m1 = component_grade(marks, "M1").raw     # (4+4+4)/3 = 4
    m2 = component_grade(marks, "M2").raw     # (4*2+5)/3 = 4.333...
    m3 = component_grade(marks, "M3").raw     # 5
    final = subject_grade(m1, m2, m3)
    # 4*0.4 + 4.333*0.4 + 5*0.2 = 1.6 + 1.733 + 1.0 = 4.333
    assert final.raw < PASS_THRESHOLD
    assert final.rounded == 4                 # fails


def test_the_student_standard_rounding_would_have_wrongly_passed():
    """A student landing on 4.5 exactly must fail, not pass.

    This is the case the ROUND_HALF_UP version of round_grade got wrong, and
    it is not a hypothetical: 4.5 falls out of a 4 in Mitarbeit, a 4 in
    Schularbeit and a 6.5 in the Projekt.
    """
    final = subject_grade(D(4), D(4), D("6.5"))
    assert final.raw == Decimal("4.5")
    assert final.rounded == 4
    assert final.raw < PASS_THRESHOLD


def test_a_realistic_passing_student():
    marks = [
        Mark("homework", D(7)), Mark("mini_test", D(6)),
        Mark("schularbeit", D(5), D(2)),
        Mark("project", D(8)),
    ]
    final = subject_grade(
        component_grade(marks, "M1").raw,
        component_grade(marks, "M2").raw,
        component_grade(marks, "M3").raw,
    )
    assert final.rounded >= 5
    assert final.provisional is False


# ------------------------------------------------------------ transport

def test_as_dict_is_json_safe():
    """The payload crosses to the Pi as JSON, so no Decimals may survive."""
    import json

    payload = subject_grade(D(8), D(6), D(10)).as_dict()
    json.dumps(payload)                       # must not raise
    assert isinstance(payload["raw"], float)
    assert payload["raw"] == 7.6
    assert payload["rounded"] == 8


def test_as_dict_keeps_none_as_none():
    payload = subject_grade(None, None, None).as_dict()
    assert payload["raw"] is None
    assert payload["rounded"] is None


def test_raw_precision_survives_on_the_object():
    """as_dict rounds to 2dp for transport only; the Decimal stays exact."""
    result = subject_grade(D("8.333333"), D("6.666666"), None)
    assert result.as_dict()["raw"] == 7.5
    assert result.raw == Decimal("7.4999995")


# ------------------------------------------------------------- helpers

def test_mean_or_none():
    assert mean_or_none([D(4), D(6)]) == D(5)
    assert mean_or_none([]) is None
    assert mean_or_none([None, None]) is None
    assert mean_or_none([D(5), None]) == D(5)
