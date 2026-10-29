"""Tests Entschuldigungssystem (O-3, V4.6).
Seed: Klassenvorstand 4A = alehrer, tschueler hat 3 Fehlstunden (05.10. abwesend, 12.10. verspaetet, 19.10. abwesend)."""

from app import models as m
from app.core.database import SessionLocal
from app.core.security import hash_password


def _ids(client, headers, unexcused=True):
    r = client.get(f"/attendance/me?unexcused={'true' if unexcused else 'false'}", headers=headers)
    assert r.status_code == 200, r.text
    return [a["attendance_id"] for a in r.json()]


def _fremde_lehrkraft(client):
    """Lehrkraft, die NICHT Klassenvorstand der 4A ist."""
    with SessionLocal() as db:
        if not db.query(m.User).filter_by(username="blehrer").first():
            db.add(m.User(first_name="Bernd", last_name="Lehrer", username="blehrer", role="lehrkraft",
                          email="blehrer@edudevice.at", password_hash=hash_password("lehrer123")))
            db.commit()
    r = client.post("/auth/login", data={"username": "blehrer", "password": "lehrer123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_entschuldigung_ganzer_ablauf(client, student, teacher, admin):
    # 1. offene Fehlstunden
    r = client.get("/attendance/me?unexcused=true", headers=student)
    abs_ = r.json()
    assert len(abs_) == 3 and abs_[0]["date"] == "2026-10-19"          # neueste zuerst
    assert {"attendance_id", "date", "start_time", "subject_name", "status"} <= abs_[0].keys()
    assert abs_[0]["subject_name"] == "Mathematik"
    ids = _ids(client, student)

    # 2. zwei davon entschuldigen
    erste = sorted(ids)[:2]
    r = client.post("/excuses", json={"reason": "Krank (Arztbesuch)", "attendance_ids": erste}, headers=student)
    assert r.status_code == 201, r.text
    exc = r.json()
    assert exc["status"] == "pending" and len(exc["absences"]) == 2
    assert exc["date_from"] == "2026-10-05" and exc["date_to"] == "2026-10-12"
    assert len(_ids(client, student)) == 1
    # alle Fehlstunden (unexcused=false) zeigen den Status der Entschuldigung
    alle = client.get("/attendance/me", headers=student).json()
    assert sorted(a["excuse_status"] or "-" for a in alle) == ["-", "pending", "pending"]

    # gleiche Stunden nochmal -> 400
    assert client.post("/excuses", json={"reason": "x", "attendance_ids": erste}, headers=student).status_code == 400

    # 3. eigene Liste
    mine = client.get("/excuses/me", headers=student).json()
    assert [e["id"] for e in mine] == [exc["id"]]

    # 4. Klassenvorstand sieht sie, fremde Lehrkraft nicht
    fremd = _fremde_lehrkraft(client)
    liste = client.get("/excuses/class-teacher?status=pending", headers=teacher).json()
    assert [e["id"] for e in liste] == [exc["id"]]
    assert liste[0]["class_name"] == "4A" and liste[0]["student_name"] == "Test Schueler"
    assert client.get("/excuses/class-teacher", headers=fremd).json() == []
    assert client.get("/excuses/class-teacher?status=accepted", headers=teacher).json() == []
    assert len(client.get("/excuses/class-teacher", headers=admin).json()) >= 1

    # 5. pruefen
    body = {"status": "rejected", "teacher_comment": "  Bitte Arztbestaetigung nachreichen "}
    assert client.patch(f"/excuses/{exc['id']}", json=body, headers=fremd).status_code == 404
    assert client.patch(f"/excuses/{exc['id']}", json=body, headers=student).status_code == 403
    r = client.patch(f"/excuses/{exc['id']}", json=body, headers=teacher)
    assert r.status_code == 200, r.text
    geprueft = r.json()
    assert geprueft["status"] == "rejected" and geprueft["teacher_comment"] == "Bitte Arztbestaetigung nachreichen"
    assert geprueft["reviewed_by"] == 2 and geprueft["reviewed_by_name"] == "Anna Lehrer" and geprueft["reviewed_at"]
    assert client.patch(f"/excuses/{exc['id']}", json={"status": "accepted"}, headers=teacher).status_code == 409

    # 6. abgelehnt -> wieder offen, neu einreichen und annehmen
    assert len(_ids(client, student)) == 3
    r = client.post("/excuses", json={"reason": "Arztbestaetigung liegt bei", "attendance_ids": erste[:1]},
                    headers=student)
    assert r.status_code == 201
    neu = r.json()
    r = client.patch(f"/excuses/{neu['id']}", json={"status": "accepted"}, headers=teacher)
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["teacher_comment"] is None
    mine = client.get("/excuses/me", headers=student).json()
    assert [e["status"] for e in mine] == ["accepted", "rejected"]
    assert len(mine[1]["absences"]) == 1      # eine Stunde ist zur neuen Entschuldigung gewandert
    assert len(_ids(client, student)) == 2


def test_entschuldigung_fremde_stunden_400(client, student):
    with SessionLocal() as db:
        andere = db.query(m.Attendance).filter(m.Attendance.student_id != 3).first()
        andere_id = andere.id if andere else 999999
    assert client.post("/excuses", json={"reason": "x", "attendance_ids": [andere_id]},
                       headers=student).status_code == 400
    assert client.post("/excuses", json={"reason": "x", "attendance_ids": [999999]}, headers=student).status_code == 400


def test_entschuldigung_eingaben_422(client, student, teacher):
    assert client.post("/excuses", json={"reason": "x", "attendance_ids": []}, headers=student).status_code == 422
    assert client.post("/excuses", json={"reason": "", "attendance_ids": [1]}, headers=student).status_code == 422
    assert client.get("/excuses/class-teacher?status=kaputt", headers=teacher).status_code == 422
    assert client.patch("/excuses/1", json={"status": "pending"}, headers=teacher).status_code == 422


def test_entschuldigung_rollen(client, student, teacher):
    assert client.get("/attendance/me", headers=teacher).status_code == 403
    assert client.post("/excuses", json={"reason": "x", "attendance_ids": [1]}, headers=teacher).status_code == 403
    assert client.get("/excuses/me", headers=teacher).status_code == 403
    assert client.get("/excuses/class-teacher", headers=student).status_code == 403
    assert client.patch("/excuses/999999", json={"status": "accepted"}, headers=teacher).status_code == 404
    assert client.get("/excuses/me").status_code == 401
