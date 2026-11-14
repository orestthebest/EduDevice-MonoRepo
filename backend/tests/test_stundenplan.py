"""Tests Stundenplan-Verwaltung (V2.12, Schema V4.11).
Eigene Klasse 7S mit Gruppen (zwei parallele Faecher), eigenen Lehrkraeften und SchuelerInnen.
Seed: Mathe 4A (alehrer) Montag 08:00-08:50 Raum A101 - wird fuer Lehrer-/Raum-Konflikte benutzt.
Tokens werden direkt erzeugt (kein Login -> kein Rate-Limit)."""

from datetime import date, timedelta

from app import models as m
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password


def _tok(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def _setup():
    """7S: Gruppe A (t7a: s7a, s7both), Gruppe B (t7b: s7b), Fach X (t7c: s7both)."""
    with SessionLocal() as db:
        if db.query(m.User).filter_by(username="t7a").first() is None:
            def user(name, role, first, last):
                u = m.User(first_name=first, last_name=last, username=name, role=role,
                           email=f"{name}@edudevice.at", password_hash=hash_password("geheim123"))
                db.add(u)
                return u
            t7a, t7b, t7c = (user("t7a", "lehrkraft", "Tina", "Alpha"), user("t7b", "lehrkraft", "Tom", "Beta"),
                             user("t7c", "lehrkraft", "Tara", "Gamma"))
            s7a, s7b, s7both = (user("s7a", "schueler", "Sara", "Eins"), user("s7b", "schueler", "Sven", "Zwei"),
                                user("s7both", "schueler", "Max", "Muster"))
            db.flush()
            k = m.SchoolClass(school_year_id=1, name="7S")
            db.add(k)
            sub = {n: m.Subject(name=n) for n in ("Gruppe A", "Gruppe B", "INSY 7S")}
            db.add_all(sub.values())
            db.flush()
            cs_a = m.ClassSubject(class_id=k.id, subject_id=sub["Gruppe A"].id, teacher_id=t7a.id)
            cs_b = m.ClassSubject(class_id=k.id, subject_id=sub["Gruppe B"].id, teacher_id=t7b.id)
            cs_x = m.ClassSubject(class_id=k.id, subject_id=sub["INSY 7S"].id, teacher_id=t7c.id)
            db.add_all([cs_a, cs_b, cs_x])
            db.flush()
            for cs, studs in ((cs_a, (s7a, s7both)), (cs_b, (s7b,)), (cs_x, (s7both,))):
                for s in studs:
                    db.add(m.ClassSubjectStudent(class_subject_id=cs.id, student_id=s.id))
            for s in (s7a, s7b, s7both):
                db.add(m.StudentClass(student_id=s.id, class_id=k.id))
            db.commit()
        u = {n: db.query(m.User).filter_by(username=n).one()
             for n in ("t7a", "t7b", "t7c", "s7a", "s7b", "s7both")}
        k = db.query(m.SchoolClass).filter_by(name="7S").one()
        cs = {n: db.query(m.ClassSubject).join(m.Subject).filter(m.Subject.name == n).one().id
              for n in ("Gruppe A", "Gruppe B", "INSY 7S")}
        return {"tok": {n: _tok(x) for n, x in u.items()}, "id": {n: x.id for n, x in u.items()},
                "class_id": k.id, "cs": cs}


def _block(client, admin, cs, weekday, p1, p2=None, room=None):
    return client.post("/timetable", json={"class_subject_id": cs, "weekday": weekday, "period_from": p1,
                                            "period_to": p2 or p1, "room": room}, headers=admin)


def test_raster(client, student):
    r = client.get("/timetable/periods", headers=student).json()
    assert len(r) == 11 and r[0] == {"period": 1, "start": "07:45", "end": "08:30"}
    assert r[10] == {"period": 11, "start": "16:20", "end": "17:05"}


def test_block_anlegen_und_konflikte(client, admin, teacher):
    t = _setup()
    cs = t["cs"]
    # Doppelstunde Gruppe A, Di 3-4
    r = _block(client, admin, cs["Gruppe A"], "Di", 3, 4, "K22")
    assert r.status_code == 201, r.text
    rows = r.json()
    assert [(x["period"], x["start_time"], x["end_time"]) for x in rows] == [(3, "09:35", "10:20"),
                                                                            (4, "10:25", "11:10")]
    assert rows[0]["teacher"] == "Alpha" and rows[0]["room"] == "K22"

    # Gruppe B parallel (andere Lehrkraft, andere SchuelerInnen, anderer Raum) -> erlaubt
    assert _block(client, admin, cs["Gruppe B"], "Di", 3, 4, "K23").status_code == 201

    # gleiches Fach nochmal
    r = _block(client, admin, cs["Gruppe A"], "Di", 4)
    assert r.status_code == 409 and r.json()["detail"] == "Gruppe A for class 7S already has a lesson on Di in period 4"
    # SchuelerIn in zwei Faechern gleichzeitig
    r = _block(client, admin, cs["INSY 7S"], "Di", 4)
    assert r.status_code == 409 and r.json()["detail"] == "Max Muster is already in Gruppe A in period 4"
    # Raum (gross/klein egal)
    r = _block(client, admin, cs["INSY 7S"], "Di", 5, room="k22")
    assert r.status_code == 201                       # Periode 5 ist frei
    r = _block(client, admin, cs["Gruppe B"], "Di", 5, room="K22")
    assert r.status_code == 409 and r.json()["detail"] == "Room k22 is already used by class 7S in period 5"

    # Konflikte mit alten Eintraegen ausserhalb des Rasters (Seed: alehrer Mo 08:00-08:50, Raum A101)
    with SessionLocal() as db:
        physik = m.Subject(name="Physik 7S")
        db.add(physik)
        db.flush()
        cs_alehrer = m.ClassSubject(class_id=t["class_id"], subject_id=physik.id, teacher_id=2)
        db.add(cs_alehrer)
        db.commit()
        cs_al = cs_alehrer.id
    r = _block(client, admin, cs_al, "Mo", 1)
    assert r.status_code == 409 and r.json()["detail"] == "alehrer already teaches class 4A in period 1"
    r = _block(client, admin, cs["Gruppe B"], "Mo", 2, room="a101")
    assert r.status_code == 409 and r.json()["detail"] == "Room A101 is already used by class 4A in period 2"

    # Klassenansicht (nur admin)
    rows = client.get(f"/timetable/class/{t['class_id']}", headers=admin).json()
    assert [(x["weekday"], x["period"], x["subject"]) for x in rows] == [
        ("Di", 3, "Gruppe A"), ("Di", 3, "Gruppe B"), ("Di", 4, "Gruppe A"), ("Di", 4, "Gruppe B"),
        ("Di", 5, "INSY 7S")]
    assert client.get(f"/timetable/class/{t['class_id']}", headers=teacher).status_code == 403
    assert client.get("/timetable/class/99999", headers=admin).status_code == 404


def test_eingaben_und_rechte(client, admin, teacher):
    t = _setup()
    cs = t["cs"]["INSY 7S"]
    assert _block(client, admin, cs, "Sa", 1).status_code == 422
    assert _block(client, admin, cs, "Mo", 3, 2).status_code == 422
    assert _block(client, admin, cs, "Mo", 12).status_code == 422
    assert _block(client, admin, 99999, "Mo", 9).status_code == 404
    assert _block(client, teacher, cs, "Mo", 9).status_code == 403
    assert client.delete("/timetable/99999", headers=admin).status_code == 404


def _naechster(wd: int) -> date:
    """Naechster Tag mit diesem Wochentag (0 = Mo), ab morgen, ohne Kalendereintrag."""
    with SessionLocal() as db:
        frei = {c.date for c in db.query(m.SchoolCalendarDay)}
    d = date.today() + timedelta(days=1)
    while d.weekday() != wd or d in frei:
        d += timedelta(days=1)
    return d


def test_stunden_woche_und_loeschen(client, admin):
    t = _setup()
    cs = t["cs"]
    r = _block(client, admin, cs["Gruppe B"], "Mi", 7, 8)
    assert r.status_code == 201
    e7, e8 = (x["id"] for x in r.json())
    tag = _naechster(2)                                         # naechster Mittwoch
    if tag > date(2027, 6, 30):                                  # Schuljahr vorbei -> keine Stunden mehr
        return

    with SessionLocal() as db:
        assert db.query(m.Lesson).filter_by(timetable_id=e7, date=tag).count() == 1

    # Woche: s7b (Gruppe B) sieht die Stunden, s7a (Gruppe A) nicht
    wk = client.get(f"/timetable/week?user_id={t['id']['s7b']}&date={tag}", headers=t["tok"]["s7b"]).json()
    assert wk["week_start"] == (tag - timedelta(days=2)).isoformat()
    meine = [x for x in wk["lessons"] if x["date"] == tag.isoformat() and x["subject"] == "Gruppe B"
             and x["period"] in (7, 8)]
    assert [(x["period"], x["start_time"], x["teacher"], x["class_name"]) for x in meine] == [
        (7, "13:00", "Beta", "7S"), (8, "13:50", "Beta", "7S")]
    wk_a = client.get(f"/timetable/week?user_id={t['id']['s7a']}&date={tag}", headers=t["tok"]["s7a"]).json()
    assert not [x for x in wk_a["lessons"] if x["subject"] == "Gruppe B"]
    # Lehrkraft sieht eigene Stunden
    wk_t = client.get(f"/timetable/week?user_id={t['id']['t7b']}&date={tag}", headers=t["tok"]["t7b"]).json()
    assert any(x["lesson_id"] == meine[0]["lesson_id"] for x in wk_t["lessons"])
    # fremde Woche nur fuer admin
    assert client.get(f"/timetable/week?user_id={t['id']['s7b']}&date={tag}",
                      headers=t["tok"]["s7a"]).status_code == 403
    assert client.get(f"/timetable/week?user_id={t['id']['s7b']}&date={tag}", headers=admin).status_code == 200

    # Anwesenheit in der Stunde von Periode 7 -> beim Loeschen bleibt die Geschichte
    with SessionLocal() as db:
        lesson = db.query(m.Lesson).filter_by(timetable_id=e7, date=tag).one()
        db.add(m.Attendance(student_id=t["id"]["s7b"], lesson_id=lesson.id, status="anwesend", minutes_missed=0))
        db.commit()
        lesson_id = lesson.id
    assert client.delete(f"/timetable/{e7}", headers=admin).status_code == 204
    assert client.delete(f"/timetable/{e8}", headers=admin).status_code == 204
    with SessionLocal() as db:
        e = db.get(m.TimetableEntry, e7)
        assert e is not None and e.valid_to == date.today() - timedelta(days=1)   # beendet, nicht geloescht
        assert db.get(m.Lesson, lesson_id) is not None                             # Stunde mit Anwesenheit bleibt
        assert db.query(m.Lesson).filter(m.Lesson.timetable_id == e7, m.Lesson.id != lesson_id).count() == 0
        assert db.get(m.TimetableEntry, e8) is None                                # ohne Anwesenheit: weg
        assert db.query(m.Lesson).filter_by(timetable_id=e8).count() == 0

    # beendeter Eintrag zaehlt nicht mehr: neuer Block an derselben Stelle geht, Klassenansicht ohne ihn
    assert _block(client, admin, cs["Gruppe B"], "Mi", 7).status_code == 201
    ids = [x["id"] for x in client.get(f"/timetable/class/{t['class_id']}", headers=admin).json()]
    assert e7 not in ids
    # GET /timetable/{user_id} zeigt nur gueltige Eintraege
    eigene = client.get(f"/timetable/{t['id']['t7b']}", headers=t["tok"]["t7b"]).json()
    assert e7 not in [x["id"] for x in eigene] and all("period" in x for x in eigene)


def test_woche_kalender(client, admin):
    t = _setup()
    with SessionLocal() as db:
        if db.get(m.SchoolCalendarDay, date(2027, 3, 1)) is None:
            db.add(m.SchoolCalendarDay(date=date(2027, 3, 1), school_year_id=1, day_type="info",
                                       has_lessons=True, note="Sprechtag"))
            db.add(m.SchoolCalendarDay(date=date(2027, 3, 3), school_year_id=1, day_type="swapped_timetable",
                                       has_lessons=True, timetable_weekday="Mo", note="Montagsstundenplan"))
            db.commit()
    wk = client.get(f"/timetable/week?user_id={t['id']['s7a']}&date=2027-03-04", headers=admin).json()
    assert wk["week_start"] == "2027-03-01"
    assert [(c["date"], c["day_type"], c["timetable_weekday"]) for c in wk["calendar"]] == [
        ("2027-03-01", "info", None), ("2027-03-03", "swapped_timetable", "Mo")]


def test_klassenvorstand_und_lehrerliste(client, admin, teacher):
    t = _setup()
    url = f"/classes/{t['class_id']}"
    r = client.patch(url, json={"class_teacher_id": t["id"]["t7a"]}, headers=admin)
    assert r.status_code == 200 and r.json()["class_teacher_name"] == "Tina Alpha"
    assert client.get(url, headers=admin).json()["class_teacher_id"] == t["id"]["t7a"]
    assert client.patch(url, json={"class_teacher_id": t["id"]["s7a"]}, headers=admin).status_code == 400
    assert client.patch(url, json={"class_teacher_id": 99999}, headers=admin).status_code == 400
    assert client.patch(url, json={}, headers=admin).status_code == 422
    assert client.patch(url, json={"class_teacher_id": 2}, headers=teacher).status_code == 403
    r = client.patch(url, json={"class_teacher_id": None}, headers=admin)
    assert r.status_code == 200 and r.json()["class_teacher_id"] is None and r.json()["class_teacher_name"] is None

    lehrer = client.get("/users?role=lehrkraft", headers=admin).json()
    names = [x["username"] for x in lehrer]
    assert "alehrer" in names and "t7a" in names and "s7a" not in names
    assert set(lehrer[0]) == {"id", "first_name", "last_name", "username"}
    assert client.get("/users?role=lehrkraft", headers=teacher).status_code == 403
    assert client.get("/users?role=chef", headers=admin).status_code == 422
