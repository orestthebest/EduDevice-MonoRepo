"""Tests V4.8: versaeumte Minuten, Schulkalender und Stunden-Generator.
Seed: Mathe 4A (class_subject 1) Montag 08:00-08:50, tschueler (id 3), Schuljahr '2026/27' (id 1).
Benutzt nur Daten, die kein anderer Test verwendet (14.09. und 16.-27.11.2026)."""

from datetime import date

from app import models as m
from app.core.database import SessionLocal
from scripts.generate_lessons import generate

URL = "/attendance?class_subject_id=1&date={d}&start_time=08:00"


def _save(client, teacher, entry, day="2026-09-14"):
    body = {"class_subject_id": 1, "date": day, "start_time": "08:00", "entries": [entry]}
    return client.put("/attendance", json=body, headers=teacher)


def _minutes(response):
    return next(s for s in response.json()["students"] if s["student_id"] == 3)["minutes_missed"]


def test_minuten_je_status(client, teacher):
    r = _save(client, teacher, {"student_id": 3, "status": "verspaetet", "minutes_missed": 7})
    assert r.status_code == 200, r.text
    assert _minutes(r) == 7                                         # tatsaechliche Minuten

    r = _save(client, teacher, {"student_id": 3, "status": "abwesend", "minutes_missed": 7})
    assert _minutes(r) == 50                                        # ganze Stunde, Angabe ignoriert

    r = _save(client, teacher, {"student_id": 3, "status": "anwesend"})
    assert _minutes(r) == 0

    r = _save(client, teacher, {"student_id": 3, "status": "verspaetet"})
    assert r.status_code == 200 and _minutes(r) is None             # ohne Angabe: unbekannt (altes Frontend)


def test_verspaetung_zu_lang_oder_ungueltig(client, teacher):
    assert _save(client, teacher, {"student_id": 3, "status": "verspaetet", "minutes_missed": 50}).status_code == 400
    assert _save(client, teacher, {"student_id": 3, "status": "verspaetet", "minutes_missed": 0}).status_code == 422


def test_seed_hat_minuten(client, teacher):
    assert _minutes(client.get(URL.format(d="2026-10-05"), headers=teacher)) == 50
    assert _minutes(client.get(URL.format(d="2026-10-12"), headers=teacher)) == 10


def _kalender():
    with SessionLocal() as db:
        if db.get(m.SchoolCalendarDay, date(2026, 11, 23)) is None:
            db.add(m.SchoolCalendarDay(date=date(2026, 11, 23), school_year_id=1, day_type="holiday",
                                       has_lessons=False, note="Feiertag/Ersatztag"))
            db.add(m.SchoolCalendarDay(date=date(2026, 11, 24), school_year_id=1, day_type="swapped_timetable",
                                       has_lessons=True, timetable_weekday="Mo", note="Montagsstundenplan"))
        year = db.get(m.SchoolYear, 1)
        year.first_lesson_day, year.last_lesson_day = date(2026, 9, 3), date(2027, 6, 25)
        db.commit()


def test_kalender_feiertag_und_getauschter_tag(client, teacher):
    _kalender()
    r = client.get("/attendance/slots?class_subject_id=1&date=2026-11-23", headers=teacher)
    assert r.status_code == 400 and "kein Unterricht" in r.json()["detail"]
    # Dienstag 24.11. laeuft nach Montagsplan -> die Montagsstunde ist da
    slots = client.get("/attendance/slots?class_subject_id=1&date=2026-11-24", headers=teacher).json()
    assert [s["start_time"] for s in slots] == ["08:00:00"]
    assert client.get(URL.format(d="2026-11-24"), headers=teacher).status_code == 200
    # ein normaler Dienstag hat weiterhin keine Mathestunde
    assert client.get("/attendance/slots?class_subject_id=1&date=2026-11-17", headers=teacher).json() == []


def test_generator_legt_an_und_ist_wiederholbar():
    _kalender()
    args = dict(start=date(2026, 11, 16), end=date(2026, 11, 27), classes=["4A"])
    probe = generate(dry_run=True, **args)
    assert probe["days"] == 9                                       # 10 Wochentage minus Feiertag 23.11.
    assert probe["created"] == {"4A": 2}                            # Mo 16.11. und Di 24.11. (Montagsplan)
    with SessionLocal() as db:
        assert db.query(m.Lesson).filter(m.Lesson.date.in_([date(2026, 11, 16), date(2026, 11, 24)])).count() == 0

    first = generate(**args)
    assert first["created"] == {"4A": 2}
    again = generate(**args)
    assert again["created"] == {} and again["skipped"] == {"4A": 2}
