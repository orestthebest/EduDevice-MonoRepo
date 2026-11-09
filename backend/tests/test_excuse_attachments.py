"""Tests Anhaenge zu Entschuldigungen (V4.9).
Eigene Klasse 4B mit eigenem Klassenvorstand und eigener SchuelerIn, damit test_excuses
(Klasse 4A, alehrer) unberuehrt bleibt. Benutzer bekommen Tokens direkt (kein Login -> kein Rate-Limit)."""

import io
from datetime import date

from PIL import Image

from app import models as m
from app.core.config import EXCUSE_DIR
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 120, 200)).save(buf, "PNG")
    return buf.getvalue()


def _token(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def _setup():
    """4B: Klassenvorstand kv4b, SchuelerIn s4b mit einer Fehlstunde; dazu fremde SchuelerIn und Lehrkraft."""
    with SessionLocal() as db:
        if db.query(m.User).filter_by(username="kv4b").first() is None:
            def user(name, role):
                u = m.User(first_name=name, last_name="Test", username=name, role=role,
                           email=f"{name}@edudevice.at", password_hash=hash_password("geheim123"))
                db.add(u)
                return u
            kv, s, fremd_s, fremd_l = (user("kv4b", "lehrkraft"), user("s4b", "schueler"),
                                       user("s4bfremd", "schueler"), user("l4bfremd", "lehrkraft"))
            db.flush()
            k = m.SchoolClass(school_year_id=1, name="4B", class_teacher_id=kv.id)
            db.add(k)
            db.flush()
            db.add(m.StudentClass(student_id=s.id, class_id=k.id))
            db.add(m.Attendance(student_id=s.id, lesson_id=1, status="abwesend", minutes_missed=50))
            db.commit()
        get = lambda n: db.query(m.User).filter_by(username=n).one()
        return {n: _token(get(n)) for n in ("kv4b", "s4b", "s4bfremd", "l4bfremd")}


def _excuse(client, h):
    att_id = client.get("/attendance/me?unexcused=true", headers=h).json()[0]["attendance_id"]
    r = client.post("/excuses", json={"reason": "Arzttermin", "attendance_ids": [att_id]}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _up(client, h, eid, data, name="bestaetigung.pdf", mime="application/pdf"):
    return client.post(f"/excuses/{eid}/attachments", files={"file": (name, data, mime)}, headers=h)


def test_anhang_ablauf(client, admin):
    t = _setup()
    eid = _excuse(client, t["s4b"])

    r = _up(client, t["s4b"], eid, PDF)
    assert r.status_code == 201, r.text
    a1 = r.json()
    assert a1["original_name"] == "bestaetigung.pdf" and a1["size_bytes"] == len(PDF)
    assert _up(client, t["s4b"], eid, _png(), "foto.png", "image/png").status_code == 201

    # in ExcuseOut sichtbar (SchuelerIn und Klassenvorstand)
    mine = next(e for e in client.get("/excuses/me", headers=t["s4b"]).json() if e["id"] == eid)
    assert [a["original_name"] for a in mine["attachments"]] == ["bestaetigung.pdf", "foto.png"]
    kv = client.get("/excuses/class-teacher?status=pending", headers=t["kv4b"]).json()
    assert len(next(e for e in kv if e["id"] == eid)["attachments"]) == 2

    # Download: SchuelerIn, Klassenvorstand, Admin ja - andere nein (404)
    url = f"/excuses/{eid}/attachments/{a1['id']}/download"
    for who in (t["s4b"], t["kv4b"], admin):
        r = client.get(url, headers=who)
        assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert client.get(url, headers=t["s4bfremd"]).status_code == 404
    assert client.get(url, headers=t["l4bfremd"]).status_code == 404
    assert client.get(url).status_code == 401
    assert client.get(f"/excuses/{eid}/attachments/999999/download", headers=t["s4b"]).status_code == 404

    # max. 3
    assert _up(client, t["s4b"], eid, PDF, "b.pdf").status_code == 201
    assert _up(client, t["s4b"], eid, PDF, "c.pdf").status_code == 409

    # loeschen (nur eigene, nur offen) -> Datei weg, dann wieder Platz
    att = client.get("/excuses/me", headers=t["s4b"]).json()
    att = next(e for e in att if e["id"] == eid)["attachments"][-1]
    stored = None
    with SessionLocal() as db:
        stored = db.get(m.ExcuseAttachment, att["id"]).stored_name
    assert client.delete(f"/excuses/{eid}/attachments/{att['id']}", headers=t["s4bfremd"]).status_code == 404
    assert client.delete(f"/excuses/{eid}/attachments/{att['id']}", headers=t["s4b"]).status_code == 204
    assert not (EXCUSE_DIR / stored).exists()
    assert _up(client, t["s4b"], eid, PDF, "d.pdf").status_code == 201

    # nach der Entscheidung: kein Upload/Loeschen mehr (409), Download geht weiter
    assert client.patch(f"/excuses/{eid}", json={"status": "accepted"}, headers=t["kv4b"]).status_code == 200
    assert _up(client, t["s4b"], eid, PDF, "e.pdf").status_code == 409
    assert client.delete(f"/excuses/{eid}/attachments/{a1['id']}", headers=t["s4b"]).status_code == 409
    assert client.get(url, headers=t["kv4b"]).status_code == 200


def test_anhang_falsche_dateien(client):
    t = _setup()
    with SessionLocal() as db:   # neue Fehlstunde, damit eine neue Entschuldigung moeglich ist
        s = db.query(m.User).filter_by(username="s4b").one()
        lesson = m.Lesson(timetable_id=1, date=date(2026, 8, 31), cancelled=False)
        db.add(lesson)
        db.flush()
        db.add(m.Attendance(student_id=s.id, lesson_id=lesson.id, status="abwesend", minutes_missed=50))
        db.commit()
    eid = _excuse(client, t["s4b"])
    h = t["s4b"]
    assert _up(client, h, eid, b"<html>boese</html>", "x.html", "text/html").status_code == 400      # Endung
    assert _up(client, h, eid, b"MZ\x90\x00 exe", "fake.pdf").status_code == 400                     # Inhalt
    assert _up(client, h, eid, _png(), "bild.jpg", "image/jpeg").status_code == 400                  # PNG als .jpg
    assert _up(client, h, eid, b"", "leer.pdf").status_code == 400
    assert _up(client, h, eid, PDF + b"0" * (5 * 1024 * 1024), "gross.pdf").status_code == 413
    # fremde Entschuldigung / Lehrkraft darf nicht hochladen
    assert _up(client, t["s4bfremd"], eid, PDF).status_code == 404
    assert _up(client, t["kv4b"], eid, PDF).status_code == 403
