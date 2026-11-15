"""Tests Jahresnote nach Trimestern und noch moeglicher Bereich (services/final_range.py).
M1/M2: je Trimester gemittelt, dann Mittel der Trimester; M3 einmal im Jahr.
Offen: kommende Trimester, der Rest des laufenden (bisheriges Tempo, mindestens
noch eine Note), das Projekt bis es benotet ist."""

from datetime import date
from decimal import Decimal as D

from app.services.final_range import clip_to, final_range, trimester_of, year_components

T = [(date(2026, 9, 7), date(2026, 12, 4)), (date(2026, 12, 7), date(2027, 3, 19)),
     (date(2027, 3, 22), date(2027, 7, 2))]


def test_trimester_of_and_clip():
    assert trimester_of(date(2026, 10, 1), T) == 0
    assert trimester_of(date(2026, 12, 5), T) == 0                  # Ferien: zum zuletzt begonnenen
    assert trimester_of(date(2027, 4, 1), T) == 2
    assert clip_to(T, date(2027, 4, 30))[-1] == (date(2027, 3, 22), date(2027, 4, 30))   # 5. Klassen


def test_each_trimester_counts_the_same():
    # T1: sechs 8er in der Mitarbeit, T2: eine 5 - Jahres-M1 ist 6.5, nicht (6*8+5)/7
    marks = [("M1", 8, 1, date(2026, 10, d)) for d in range(1, 7)] + [("M1", 5, 1, date(2027, 1, 10))]
    assert year_components(marks, T)["M1"] == D("6.5")
    assert year_components(marks, T)["M3"] is None


def test_november_is_not_secured_yet():
    # je eine Note in M1, M2, M3 im ersten Trimester - frueher "sicher bestanden" (4,8)
    marks = [("M1", 5, 1, date(2026, 10, 1)), ("M2", 4, 2, date(2026, 10, 8)),
             ("M3", 5, 1, date(2026, 10, 20))]
    r = final_range(marks, T, date(2026, 11, 15))
    assert r.low < D("4.6") < r.high and r.status == "undecided"
    assert r.high - r.low > 3                    # T2 und T3 ganz offen, T1 zum Teil


def test_strong_student_with_project_can_be_safe_early():
    marks = [("M1", 9, 1, date(2026, 10, 1)), ("M2", 9, 2, date(2026, 10, 8)),
             ("M1", 9, 1, date(2027, 1, 10)), ("M2", 9, 2, date(2027, 1, 20)),
             ("M3", 10, 1, date(2026, 11, 1))]
    r = final_range(marks, T, date(2027, 3, 20))                    # T1 und T2 vorbei, T3 offen
    # M1 und M2: (9 + 9 + 4) / 3 = 7.33, Projekt 10 -> 0.8 * 7.33 + 2 = 7.87
    assert r.status == "secured_pass" and r.low > D("7.8") and r.required < 4


def test_end_of_year_only_missing_parts_are_open():
    marks = [("M1", 6, 1, date(2026, 10, 1)), ("M2", 5, 2, date(2027, 1, 20))]
    r = final_range(marks, T, date(2027, 7, 3))
    assert r.low == D("0.4") * 6 + D("0.4") * 5 + D("0.2") * 4      # 5.2 - nur das Projekt offen
    assert r.high == D("0.4") * 6 + D("0.4") * 5 + D("0.2") * 10    # 6.4
    done = final_range(marks + [("M3", 7, 1, date(2027, 5, 1))], T, date(2027, 7, 3))
    assert done.low == done.high and done.required is None


def test_unavoidable_only_when_even_10s_fail():
    fours = [("M1", 4, 1, date(2026, 10, 1)), ("M2", 4, 2, date(2026, 10, 8)), ("M3", 4, 1, date(2026, 11, 1))]
    assert final_range(fours, T, date(2027, 7, 3)).status == "fail_unavoidable"
    assert final_range(fours, T, date(2026, 11, 15)).status == "undecided"   # zwei Trimester kommen noch