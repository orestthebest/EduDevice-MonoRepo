"""Tests for scoring.py - the rules of the nightly scoring job."""

from datetime import date, timedelta
from decimal import Decimal as D

import scoring
from scoring import DatedMark, Envelope, Insight

TODAY = date(2026, 11, 13)


def mark(value, days_ago, category="mini_test", weight="1"):
    return DatedMark(category, D(str(value)), D(weight), TODAY - timedelta(days=days_ago))


# ---------------------------------------------------------------- drops and alerts

def test_drop_must_be_large_compared_with_own_spread():
    steady = [mark(8, 40), mark(8, 30), mark(8, 20), mark(5.5, 2)]
    assert scoring.unusual_drop(steady, TODAY) is not None                  # 2.5 below a steady 8
    swingy = [mark(10, 40), mark(6, 30), mark(9, 20), mark(6, 2)]
    assert scoring.unusual_drop(swingy, TODAY) is None                      # normal for this student
    old = [mark(8, 60), mark(8, 50), mark(8, 40), mark(5, 30)]
    assert scoring.unusual_drop(old, TODAY) is None                         # not recent any more


def test_alerts_rules_model_and_attendance():
    # the range itself is tested in backend/tests/test_final_range.py
    undecided = Envelope(D("4.5"), D("4.3"), D("8.2"), "undecided", D("4.8"))
    types = [a.type for a in scoring.alerts_for(undecided, 0.62, None, [], TODAY, "m")]
    assert types == ["fail_risk"]
    assert scoring.alerts_for(undecided, 0.3, None, [], TODAY, "m") == []  # below the alert level
    absence = {"status": "trending", "rate": 0.07, "projected_rate": 0.21}
    secured = Envelope(D("8"), D("6.4"), D("9.2"), "secured_pass", D("1"))
    [a] = scoring.alerts_for(secured, None, absence, [], TODAY, "m")
    assert a.type == "attendance_trend" and "21 %" in a.message


# ---------------------------------------------------------------- observations

def test_recent_lift_and_no_subject_name_in_message():
    marks = [mark(6, 40), mark(6, 30), mark(6, 20), mark(9, 3)]
    found = scoring.subject_insights(7, marks, scoring.subject_raw(marks), None, TODAY, lambda d: 1)
    kinds = {i.kind: i for i in found}
    assert "recent_lift" in kinds and kinds["recent_lift"].tone == "positive"
    assert "Mathematics" not in kinds["recent_lift"].message and "10 Nov" in kinds["recent_lift"].message


def test_trimester_change_needs_to_beat_own_noise():
    tri = lambda d: 1 if d < TODAY - timedelta(days=30) else 2
    clear = [mark(5, 60), mark(5.5, 50), mark(5, 45), mark(7, 20), mark(7.5, 10), mark(7, 5)]
    assert any(i.kind == "trimester_up" for i in
               scoring.subject_insights(1, clear, scoring.subject_raw(clear), None, TODAY, tri))
    noise = [mark(5, 60), mark(9, 50), mark(6, 45), mark(8, 20), mark(5, 10), mark(7, 5)]
    assert not any(i.kind.startswith("trimester") for i in
                   scoring.subject_insights(1, noise, scoring.subject_raw(noise), None, TODAY, tri))


def test_near_round_up_only_when_close():
    def kinds(raw):
        return {i.kind for i in scoring.subject_insights(1, [mark(7, 50)], D(raw), None, TODAY, lambda d: 1)}
    assert "near_round_up" in kinds("7.50")          # 0.10 away
    assert "near_round_up" not in kinds("7.40")      # 0.20 away - too far
    assert "near_round_up" not in kinds("7.60")      # already rounds up


def test_pick_three_with_limits():
    c = [Insight(1, "a", "attention", 5, ""), Insight(2, "b", "attention", 4, ""),
         Insight(3, "c", "attention", 3, ""), Insight(4, "d", "neutral", 2, ""),
         Insight(5, "e", "positive", 0.5, "")]
    chosen = scoring.pick(c)
    assert len(chosen) == 3
    assert sum(i.tone == "attention" for i in chosen) == 2                  # never three warnings
    assert any(i.tone == "positive" for i in chosen)                        # the positive one gets in


def test_attendance_clean_needs_enough_lessons():
    lessons = [(TODAY - timedelta(days=d), 0) for d in range(1, 25, 3)]       # 8 lessons, none missed
    assert scoring.attendance_streak(lessons, TODAY).kind == "attendance_clean"
    assert scoring.attendance_streak(lessons[:5], TODAY) is None
    assert scoring.attendance_streak(lessons + [(TODAY - timedelta(days=2), 10)], TODAY) is None


def test_subject_average_counts_each_trimester_the_same():
    tris = [(date(2026, 9, 7), date(2026, 12, 4)), (date(2026, 12, 7), date(2027, 3, 19))]
    marks = [DatedMark("mini_test", D("8"), D("1"), date(2026, 10, d)) for d in (1, 2, 3)]
    marks.append(DatedMark("mini_test", D("5"), D("1"), date(2027, 1, 10)))
    assert scoring.subject_raw(marks, tris) == D("6.5")      # (8 + 5) / 2, same rule as the page
    assert scoring.subject_raw(marks) == D("7.25")           # without trimesters: one block