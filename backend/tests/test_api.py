"""
Automatische Tests der REST-API.  Ausfuehren im backend-Ordner:  python -m pytest -v
Testdaten aus scripts/seed.py: admin=1, alehrer=2, tschueler=3, Klasse 4A=1, Mathe 4A=class_subject 1
"""


# ---------------- Auth ----------------
def test_login_falsches_passwort(client):
    assert client.post("/auth/login", data={"username": "admin", "password": "falsch"}).status_code == 401


def test_login_mit_email(client):
    assert client.post("/auth/login", data={"username": "admin@edudevice.at", "password": "admin123"}).status_code == 200


def test_ohne_token_401(client):
    assert client.get("/subjects").status_code == 401


def test_me(client, student):
    r = client.get("/auth/me", headers=student)
    assert r.status_code == 200 and r.json()["role"] == "schueler"
    assert "password_hash" not in r.json()


def test_register_und_duplikat(client):
    data = {"first_name": "Neu", "last_name": "Schueler", "username": "nschueler",
            "email": "neu@edudevice.at", "password": "geheim123", "role": "schueler"}
    assert client.post("/auth/register", json=data).status_code == 201
    assert client.post("/auth/register", json=data).status_code == 409


def test_register_admin_verboten(client):
    data = {"first_name": "a", "last_name": "b", "username": "hacker", "email": "h@x.at",
            "password": "geheim123", "role": "admin"}
    assert client.post("/auth/register", json=data).status_code == 422


# ---------------- Ziel-M-4 Endpunkte ----------------
def test_noten_schueler_nur_eigene(client, student):
    assert client.get("/grades/3", headers=student).status_code == 200
    assert client.get("/grades/1", headers=student).status_code == 403


def test_note_eintragen_nur_lehrkraft(client, teacher, student):
    note = {"student_id": 3, "class_subject_id": 1, "category": "oral", "value": 8}
    assert client.post("/grades", json=note, headers=student).status_code == 403
    assert client.post("/grades", json=note, headers=teacher).status_code == 201
    assert client.post("/grades", json={**note, "value": 11}, headers=teacher).status_code == 422


def test_stundenplan_hausaufgaben_anwesenheit_quiz(client, teacher, student):
    assert len(client.get("/timetable/3", headers=student).json()) == 1
    assert client.get("/homework/1", headers=student).status_code == 200
    assert client.post("/homework/confirm", json={"homework_id": 1}, headers=student).status_code == 200
    r = client.post("/attendance", json={"student_id": 3, "lesson_id": 1, "status": "anwesend"}, headers=teacher)
    assert r.status_code == 200
    assert client.post("/quiz/submit", json={"quiz_id": 1, "score": 7}, headers=student).status_code == 201
    assert client.post("/quiz/submit", json={"quiz_id": 1, "score": 7}, headers=student).status_code == 409


# ---------------- Klassen (Admin) ----------------
def test_klassen_rechte(client, admin, teacher, student):
    assert client.get("/classes", headers=teacher).status_code == 200
    assert client.get("/classes", headers=student).status_code == 403
    assert client.get("/classes/1/students", headers=teacher).status_code == 403
    assert client.get("/classes/1", headers=admin).json()["school_year"] == "2026/27"


def test_schueler_zuweisen_und_entfernen(client, admin):
    ids = [s["id"] for s in client.get("/classes/1/assignable-students", headers=admin).json()]
    assert 4 in ids                                            # nschueler aus dem Register-Test
    assert client.post("/classes/1/students", json={"student_id": 4}, headers=admin).status_code == 201
    assert client.post("/classes/1/students", json={"student_id": 4}, headers=admin).status_code == 400
    assert client.delete("/classes/1/students/4", headers=admin).status_code == 200


# ---------------- Faecher + Materialien ----------------
def test_fach_anlegen_upload_download_loeschen(client, teacher, student):
    r = client.post("/subjects", json={"class_id": 1, "name": "Physik"}, headers=teacher)
    assert r.status_code == 201
    cs_id = r.json()["id"]
    assert r.json()["student_count"] == 1                      # tschueler automatisch eingetragen
    assert client.post("/subjects", json={"class_id": 1, "name": "Physik"}, headers=teacher).status_code == 409
    assert "Physik" in client.get("/subjects/names", headers=teacher).json()

    # Upload: erlaubt / verbotener Typ / SchuelerIn darf nicht
    up = client.post(f"/subjects/{cs_id}/materials", data={"title": "SQL Joins"},
                     files={"file": ("SQL Joins.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=teacher)
    assert up.status_code == 201 and up.json()["ext"] == "pdf"
    assert client.post(f"/subjects/{cs_id}/materials", data={"title": "x"},
                       files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
                       headers=teacher).status_code == 400
    assert client.post(f"/subjects/{cs_id}/materials", data={"title": "x"},
                       files={"file": ("a.pdf", b"x", "application/pdf")}, headers=student).status_code == 403

    # SchuelerIn sieht und laedt herunter
    mid = up.json()["id"]
    assert len(client.get(f"/subjects/{cs_id}/materials", headers=student).json()) == 1
    assert client.get("/materials/recent", headers=student).json()[0]["subject_name"] == "Physik"
    d = client.get(f"/materials/{mid}/download", headers=student)
    assert d.status_code == 200 and d.content == b"%PDF-1.4 test"
    assert "attachment" in d.headers["content-disposition"]

    # SchuelerIn entfernen -> sieht das Fach nicht mehr (404, nicht 403)
    assert client.delete(f"/subjects/{cs_id}/students/3", headers=teacher).status_code == 200
    assert client.get(f"/subjects/{cs_id}", headers=student).status_code == 404
    assert client.get(f"/materials/{mid}/download", headers=student).status_code == 404
    assert client.post(f"/subjects/{cs_id}/students", json={"student_id": 3}, headers=teacher).status_code == 201

    # Fach loeschen loescht auch die Datei
    r = client.delete(f"/subjects/{cs_id}", headers=teacher)
    assert r.status_code == 200 and r.json()["deleted_files"] == 1


def test_fach_mit_noten_nicht_loeschbar(client, teacher):
    assert client.delete("/subjects/1", headers=teacher).status_code == 409


def test_upload_config(client, teacher):
    r = client.get("/materials/config", headers=teacher).json()
    assert "pdf" in r["allowed_extensions"] and r["max_size_mb"] == 50


# ---------------- Sicherheit ----------------
def test_rate_limit_ip_aus_header_nur_von_localhost():
    from app.core.security import client_ip

    class Req:
        def __init__(self, host, xff=None):
            self.client = type("C", (), {"host": host})
            self.headers = {"x-forwarded-for": xff} if xff else {}

    assert client_ip(Req("127.0.0.1", "10.0.0.5")) == "10.0.0.5"     # WebApp leitet echte IP weiter
    assert client_ip(Req("172.20.9.9", "1.2.3.4")) == "172.20.9.9"   # von aussen: Header ignoriert
