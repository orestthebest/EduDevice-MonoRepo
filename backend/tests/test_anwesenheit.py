"""Tests Anwesenheit pro Stunde (V2.8).
Seed: Mathe 4A (class_subject 1) hat laut Stundenplan Montag 08:00-08:50, Lehrkraft alehrer (id 2),
tschueler (id 3) ist eingetragen. Erfasst: 05.10. abwesend, 12.10. verspaetet, 19.10. abwesend,
26.10. und 02.11. anwesend.
Achtung: die drei Fehlstunden des Seeds hier NICHT aendern (test_excuses braucht sie)."""

from datetime import date, timedelta

from app import models as m
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password

URL = "/attendance?class_subject_id=1&date={d}&start_time=08:00"


def _user(username, role, enroll=False):
    """Legt einen Benutzer direkt in der DB an und gibt (id, Auth-Header) zurueck (ohne Login -> kein Rate-Limit)."""
    with SessionLocal() as db:
        u = db.query(m.User).filter_by(username=username).first()
        if u is None:
            u = m.User(first_name=username.capitalize(), last_name="Test", username=username, role=role,
                       email=f"{username}@edudevice.at", password_hash=hash_password("geheim123"))
            db.add(u)
            db.flush()
            if enroll:
                db.add(m.ClassSubjectStudent(class_subject_id=1, student_id=u.id))
            db.commit()
        return u.id, {"Authorization": f"Bearer {create_access_token(u)}"}


def test_slots_und_stunde_lesen(client, teacher):
    slots = client.get("/attendance/slots?class_subject_id=1&date=2026-10-05", headers=teacher).json()
    assert [(s["start_time"], s["end_time"]) for s in slots] == [("08:00:00", "08:50:00")]
    assert client.get("/attendance/slots?class_subject_id=1&date=2026-10-06", headers=teacher).json() == []

    r = client.get(URL.format(d="2026-10-05"), headers=teacher)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["lesson_id"] and data["end_time"] == "08:50:00"
    ts = next(s for s in data["students"] if s["student_id"] == 3)
    assert ts["status"] == "abwesend" and ts["first_name"] == "Test"


def test_stunde_ohne_eintraege_status_null(client, teacher):
    data = client.get(URL.format(d="2026-09-21"), headers=teacher).json()
    assert data["lesson_id"] is None
    assert all(s["status"] is None for s in data["students"])


def test_falscher_tag_oder_zeit(client, teacher):
    assert client.get(URL.format(d="2026-10-06"), headers=teacher).status_code == 404     # Dienstag
    assert client.get(URL.format(d="2026-10-10"), headers=teacher).status_code == 400     # Samstag
    assert client.get("/attendance?class_subject_id=1&date=2026-10-05&start_time=09:00",
                      headers=teacher).status_code == 404
    assert client.get("/attendance?class_subject_id=999&date=2026-10-05&start_time=08:00",
                      headers=teacher).status_code == 404


def test_speichern_korrigieren_und_verlauf(client, teacher):
    body = {"class_subject_id": 1, "date": "2026-09-21", "start_time": "08:00",
            "entries": [{"student_id": 3, "status": "abwesend"}]}
    r = client.put("/attendance", json=body, headers=teacher)
    assert r.status_code == 200, r.text
    assert next(s for s in r.json()["students"] if s["student_id"] == 3)["status"] == "abwesend"
    lesson_id = r.json()["lesson_id"]

    # nochmal speichern = korrigieren, keine doppelte Zeile
    body["entries"][0]["status"] = "anwesend"
    r = client.put("/attendance", json=body, headers=teacher)
    assert r.json()["lesson_id"] == lesson_id
    with SessionLocal() as db:
        assert db.query(m.Attendance).filter_by(lesson_id=lesson_id, student_id=3).count() == 1

    hist = client.get("/attendance/history?class_subject_id=1", headers=teacher).json()
    tage = [h["date"] for h in hist]
    assert tage == sorted(tage, reverse=True)                       # neueste zuerst
    eintrag = next(h for h in hist if h["date"] == "2026-09-21")
    assert (eintrag["present_count"], eintrag["absent_count"], eintrag["late_count"]) == (1, 0, 0)
    okt12 = next(h for h in hist if h["date"] == "2026-10-12")
    assert okt12["late_count"] == 1


def test_anwesend_loest_entschuldigung(client, teacher):
    sid, _ = _user("aschueler", "schueler", enroll=True)
    body = {"class_subject_id": 1, "date": "2026-09-14", "start_time": "08:00",
            "entries": [{"student_id": sid, "status": "abwesend"}]}
    lesson_id = client.put("/attendance", json=body, headers=teacher).json()["lesson_id"]
    with SessionLocal() as db:
        exc = m.Excuse(student_id=sid, date_from=date(2026, 9, 14), date_to=date(2026, 9, 14),
                       reason="krank", status="pending")
        db.add(exc)
        db.flush()
        db.query(m.Attendance).filter_by(lesson_id=lesson_id, student_id=sid).update({"excuse_id": exc.id})
        db.commit()
    body["entries"][0]["status"] = "anwesend"
    r = client.put("/attendance", json=body, headers=teacher)
    s = next(x for x in r.json()["students"] if x["student_id"] == sid)
    assert s["status"] == "anwesend" and s["excuse_id"] is None


def test_speichern_fehler(client, teacher, admin):
    base = {"class_subject_id": 1, "start_time": "08:00"}
    zukunft = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)   # naechster Montag
    assert client.put("/attendance", json={**base, "date": zukunft.isoformat(),
                                           "entries": [{"student_id": 3, "status": "anwesend"}]},
                      headers=teacher).status_code == 400
    # admin (id 1) ist nicht im Fach
    assert client.put("/attendance", json={**base, "date": "2026-09-21",
                                           "entries": [{"student_id": 1, "status": "anwesend"}]},
                      headers=teacher).status_code == 400
    # doppelt
    assert client.put("/attendance", json={**base, "date": "2026-09-21",
                                           "entries": [{"student_id": 3, "status": "anwesend"},
                                                       {"student_id": 3, "status": "abwesend"}]},
                      headers=teacher).status_code == 400
    # falscher Status / leere Liste
    assert client.put("/attendance", json={**base, "date": "2026-09-21",
                                           "entries": [{"student_id": 3, "status": "krank"}]},
                      headers=teacher).status_code == 422
    assert client.put("/attendance", json={**base, "date": "2026-09-21", "entries": []},
                      headers=teacher).status_code == 422
    # Admin darf (wie bei allen Lehrkraft-Endpunkten)
    assert client.get(URL.format(d="2026-10-05"), headers=admin).status_code == 200


def test_rechte(client, student):
    _, fremd = _user("clehrer", "lehrkraft")
    assert client.get(URL.format(d="2026-10-05"), headers=fremd).status_code == 403
    assert client.get("/attendance/history?class_subject_id=1", headers=fremd).status_code == 403
    assert client.put("/attendance", json={"class_subject_id": 1, "date": "2026-09-21", "start_time": "08:00",
                                           "entries": [{"student_id": 3, "status": "anwesend"}]},
                      headers=fremd).status_code == 403
    assert client.get(URL.format(d="2026-10-05"), headers=student).status_code == 403
    assert client.get(URL.format(d="2026-10-05")).status_code == 401
