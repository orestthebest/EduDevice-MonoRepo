"""Tests Entwicklung je Fach (services/trend_stats.py)."""

from datetime import date, timedelta

from app.services.trend_stats import growth

START = date(2026, 9, 14)


def series(*values, every=7):
    return [(START + timedelta(days=i * every), v) for i, v in enumerate(values)]


def test_zu_wenige_noten():
    assert growth(series(6, 7, 8))["label"] == "too_early"
    same_day = [(START, 5), (START, 6), (START, 7), (START, 8)]
    assert growth(same_day)["label"] == "too_early"          # vier Noten, aber ein Tag


def test_richtung_nur_mit_klarem_trend():
    assert growth(series(5, 5.5, 6, 6.5, 7, 7.5))["label"] == "rising"
    assert growth(series(8, 7.5, 7, 6.5, 6, 5.5))["label"] == "falling"
    assert growth(series(7, 7, 7, 7, 7, 7))["label"] == "steady"


def test_ein_ausreisser_macht_keinen_trend():
    assert growth(series(8, 8, 8, 4, 8, 8))["label"] == "steady"   # Theil-Sen ist robust


def test_stark_schwankend_ohne_richtung():
    assert growth(series(4, 9, 5, 10, 4, 9, 5))["label"] == "up_and_down"
