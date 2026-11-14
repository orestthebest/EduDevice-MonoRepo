"""Tests for scoring.py - the rules of the nightly scoring job."""

from datetime import date, timedelta
from decimal import Decimal as D

import scoring
from scoring import DatedMark, Insight, envelope

TODAY = date(2026, 11, 13)


def mark(value, days_ago, category="mini_test", weight="1"):
    return DatedMark(category, D(str(value)), D(weight), TODAY - timedelta(days=days_ago))


# ---------------------------------------------------------------- range and status

def test_envelope_fills_missing_parts_with_4_and_10():
    env = envelope({"M1": D("6"), "M2": D("5"), "M3": None}, D("5.5"))
    assert env.low == D("0.4") * 6 + D("0.4") * 5 + D("0.2") * 4          # 5.2
    assert env.high == D("0.4") * 6 + D("0.4") * 5 + D("0.2") * 10        # 6.4
    assert env.status == "secured_pass"                                     # even a 4 in M3 passes
    assert env.required == (D("4.6") - D("4.4")) / D("0.2")                 # 1.0 (below 4 = safe)


def test_envelope_status_undecided_and_unavoidable():
    assert envelope({"M1": D("4"), "M2": None, "M3": None}, D("4")).status == "undecided"
    assert envelope({"M1": D("4"), "M2": D("4"), "M3": D("4.5")}, D("4.1")).status == "fail_unavoidable"
    complete = envelope({"M1": D("7"), "M2": D("7"), "M3": D("7")}, D("7"))
    assert complete.low == complete.high == D("7") and complete.required is None


# ---------------------------------------------------------------- drops and alerts

def test_drop_must_be_large_compared_with_own_spread():
    steady = [mark(8, 40), mark(8, 30), mark(8, 20), mark(5.5, 2)]
    assert scoring.unusual_drop(steady, TODAY) is not None                  # 2.5 below a steady 8
    swingy = [mark(10, 40), mark(6, 30), mark(9, 20), mark(6, 2)]
    assert scoring.unusual_drop(swingy, TODAY) is None                      # normal for this student
    old = [mark(8, 60), mark(8, 50), mark(8, 40), mark(5, 30)]
    assert scoring.unusual_drop(old, TODAY) is None                         # not recent any more


def test_alerts_rules_model_and_attendance():
    undecided = envelope({"M1": D("4.5"), "M2": None, "M3": None}, D("4.5"))
    types = [a.type for a in scoring.alerts_for(undecided, 0.62, None, [], TODAY, "m")]
    assert types == ["fail_risk"]
    assert scoring.alerts_for(undecided, 0.3, None, [], TODAY, "m") == []  # below the alert level
    absence = {"status": "trending", "rate": 0.07, "projected_rate": 0.21}
    [a] = scoring.alerts_for(envelope({"M1": D("8"), "M2": None, "M3": None}, D("8")), None, absence,
                             [], TODAY, "m")
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
