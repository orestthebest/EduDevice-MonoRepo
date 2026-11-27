"""Tests for notenstatistiken.py - the same year rule as the page (final_range.py)."""

from datetime import date
from decimal import Decimal as D

import notenstatistiken as ns

T = [(date(2026, 9, 7), date(2026, 12, 4)), (date(2026, 12, 7), date(2027, 3, 19))]


def _row(category, value, day, weight=1):
    return ns.GradeRow(3, 7, category, D(str(weight)), D(str(value)), day, None)


def test_each_trimester_counts_the_same():
    # T1: six 8s in Mitarbeit, T2: one 5 - year M1 is 6.5, not (6*8 + 5) / 7 = 7.57
    rows = [_row("mini_test", 8, date(2026, 10, d)) for d in range(1, 7)] + [_row("oral", 5, date(2027, 1, 10))]
    report = ns.subject_report(rows, T)
    assert report["components"]["M1"]["raw"] == 6.5
    assert report["components"]["M1"]["n_marks"] == 7          # counts still from all marks
    assert report["current"]["raw"] == 6.5 and report["current"]["rounded"] == 6


def test_without_trimesters_the_year_is_one_block():
    rows = [_row("mini_test", 8, date(2026, 10, d)) for d in range(1, 7)] + [_row("oral", 5, date(2027, 1, 10))]
    assert ns.subject_report(rows)["components"]["M1"]["raw"] == 7.57