"""Tests Notenstatistiken (GET /statistics/student/{id}), Version 2.
Seed: tschueler (id 3) hat in Mathe 4A (class_subject 1) eine Note: Mini-Test 9 am 21.09.2026.
Die Hilfsfunktionen werden mit eigenen Daten geprueft, damit kein anderer Test
durch zusaetzliche Noten in der Datenbank beeinflusst wird."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.routers.statistics import _notices, _progression, _recent_overall


def _grade(id, cs, category, value, day, weight=1):
    return SimpleNamespace(id=id, class_subject_id=cs, category=category,
                           value=Decimal(str(value)), weight=Decimal(str(weight)), date=day)


# ---------------------------------------------------------------- Endpunkt

def test_eigene_statistik_mit_neuen_feldern(client, student):
    """Andere Tests tragen weitere Noten ein - deshalb hier nur Aufbau und der
    aelteste Punkt (die Seed-Note), keine genauen Anzahlen."""
    r = client.get("/statistics/student/3", headers=student)
    assert r.status_code == 200, r.text
    s = r.json()
    assert {"notices", "recent_overall", "insights"} <= s.keys()
    assert s["insights"] == []                      # Tabelle gibt es im Test nicht -> leere Liste
    recent = s["recent_overall"]
    assert 1 <= len(recent) <= 6
    assert [x["date"] for x in recent] == sorted((x["date"] for x in recent), reverse=True)
    assert all({"effect", "is_new", "subject_name"} <= x.keys() for x in recent)
    mathe = next(x for x in s["subjects"] if x["class_subject_id"] == 1)
    assert mathe["progression"][0]["date"] == "2026-09-21"
    assert isinstance(mathe["secured"], bool)
    possible = mathe["possible"]
    assert 4 <= possible["low"] <= possible["high"] <= 10
    assert possible["status"] in ("secured_pass", "undecided", "fail_unavoidable")
    assert len(mathe["marks"]) == mathe["n_marks"]                         # Punkte der Zeitleiste


def test_fremde_statistik_verboten(client, student):
    assert client.get("/statistics/student/1", headers=student).status_code == 403


# ---------------------------------------------------------------- Hilfsfunktionen

def test_wirkung_einer_note_auf_den_schnitt():
    rows = [_grade(1, 7, "mini_test", 8, date(2026, 10, 1)),
            _grade(2, 7, "mini_test", 6, date(2026, 10, 8))]
    newest, older = _recent_overall(rows, {7: {"subject_name": "Physik"}}, date(2026, 10, 10), {7: []})
    assert newest["subject_name"] == "Physik" and newest["value"] == 6
    assert newest["effect"] == -1.0                  # Schnitt 8 -> 7
    assert newest["is_new"] is True                  # 2 Tage alt
    assert older["effect"] == 1.0 and older["is_new"] is False


def test_verlauf_ein_punkt_pro_notentag():
    rows = [_grade(1, 7, "mini_test", 8, date(2026, 10, 1)),
            _grade(2, 7, "oral", 6, date(2026, 10, 1)),
            _grade(3, 7, "mini_test", 10, date(2026, 10, 8))]
    assert _progression(rows, []) == [{"date": "2026-10-01", "raw": 7.0},
                                      {"date": "2026-10-08", "raw": 8.0}]


def test_verlauf_jedes_trimester_zaehlt_gleich():
    tris = [(date(2026, 9, 7), date(2026, 12, 4)), (date(2026, 12, 7), date(2027, 3, 19))]
    rows = [_grade(1, 7, "mini_test", 8, date(2026, 10, 1)),
            _grade(2, 7, "mini_test", 8, date(2026, 10, 8)),
            _grade(3, 7, "mini_test", 5, date(2027, 1, 10))]
    assert _progression(rows, tris)[-1] == {"date": "2027-01-10", "raw": 6.5}   # (8 + 5) / 2


def _subject(cs, standing, raw, needed, reachable=True, secured=False):
    return {"class_subject_id": cs, "subject_name": f"Fach {cs}", "standing": standing,
            "current": {"raw": raw}, "required_remaining_avg": needed,
            "reachable": reachable, "secured": secured}


def test_hinweise_wichtigstes_zuerst():
    notices = _notices([
        _subject(1, "ok", 8.0, None),
        _subject(2, "fragile", 5.2, 4.1),
        _subject(3, "failing", 4.2, 7.5),
        _subject(4, "failing", 4.0, 11.0, reachable=False),
        _subject(5, "fragile", 5.0, 3.0, secured=True),
    ])
    assert [(n["class_subject_id"], n["kind"]) for n in notices] == [
        (4, "unreachable"), (3, "failing"), (5, "fragile"), (2, "fragile")]
    assert notices[2]["secured"] is True


# ---------------------------------------------------------------- Ergebnisse des naechtlichen Laufs

def test_forecast_likely_range_and_probability_by_role():
    """risk_assessments / grade_forecasts / pipeline_runs haben kein ORM-Modell; im Test
    nur mit den Spalten, die _forecasts liest. Eigener Schueler 9001, beeinflusst nichts."""
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.routers.statistics import _forecasts

    db = SessionLocal()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS pipeline_runs (run_id INTEGER PRIMARY KEY, status TEXT, "
                        "finished_at TIMESTAMP)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS risk_assessments (id INTEGER PRIMARY KEY, student_id INT, "
                        "class_subject_id INT, status TEXT, predicted_final NUMERIC, predicted_low NUMERIC, "
                        "predicted_high NUMERIC, fail_probability NUMERIC, computed_at TIMESTAMP, model_version TEXT)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS grade_forecasts (id INTEGER PRIMARY KEY, run_id INT, "
                        "student_id INT, class_subject_id INT, predicted_grade NUMERIC, predicted_low NUMERIC, "
                        "predicted_high NUMERIC, model_version TEXT)"))
        db.execute(text("INSERT INTO pipeline_runs VALUES (901, 'success', '2026-11-14 02:31:00'), "
                        "(902, 'success', '2026-11-15 02:31:00'), (903, 'failed', '2026-11-15 07:00:00')"))
        db.execute(text("INSERT INTO risk_assessments (student_id, class_subject_id, status, predicted_final, "
                        "predicted_low, predicted_high, fail_probability, computed_at, model_version) VALUES "
                        "(9001, 7, 'undecided', 5.1, 4.3, 8.4, 0.41, '2026-11-15 02:31:00', 'v')"))
        db.execute(text("INSERT INTO grade_forecasts (run_id, student_id, class_subject_id, predicted_grade, "
                        "predicted_low, predicted_high, model_version) VALUES "
                        "(901, 9001, 7, 6.0, 5.0, 7.0, 'old'), (902, 9001, 7, 5.4, 4.6, 6.5, 'p')"))
        teacher = _forecasts(db, 9001, show_probability=True)[7]
        student = _forecasts(db, 9001, show_probability=False)[7]
    finally:
        db.rollback()
        db.close()
    assert teacher["fail_probability"] == 0.41 and "fail_probability" not in student
    assert student["likely"] == {"predicted": 5.4, "low": 4.6, "high": 6.5, "model_version": "p"}  # Lauf 902