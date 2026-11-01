"""Tests Rollen-Absicherung bei der Registrierung (V2.7):
nur SchuelerInnen duerfen sich selbst registrieren, Lehrkraefte legt der Admin an."""


def _daten(username, role=None):
    d = {"first_name": "Max", "last_name": "Muster", "username": username,
         "email": f"{username}@edudevice.at", "password": "geheim123"}
    if role:
        d["role"] = role
    return d


def test_selbst_als_lehrkraft_registrieren_403(client):
    r = client.post("/auth/register", json=_daten("fakelehrer", "lehrkraft"))
    assert r.status_code == 403
    # Konto wurde NICHT angelegt
    assert client.post("/auth/login", data={"username": "fakelehrer", "password": "geheim123"}).status_code == 401


def test_registrieren_ohne_rolle_ist_schueler(client):
    r = client.post("/auth/register", json=_daten("ohnerolle"))
    assert r.status_code == 201 and r.json()["role"] == "schueler"


def test_admin_legt_lehrkraft_an(client, admin):
    r = client.post("/users", json=_daten("neulehrer", "lehrkraft"), headers=admin)
    assert r.status_code == 201 and r.json()["role"] == "lehrkraft"
    login = client.post("/auth/login", data={"username": "neulehrer", "password": "geheim123"})
    assert login.status_code == 200 and login.json()["role"] == "lehrkraft"
    # doppelt -> 409
    assert client.post("/users", json=_daten("neulehrer", "lehrkraft"), headers=admin).status_code == 409


def test_nur_admin_darf_konten_anlegen(client, teacher, student, admin):
    assert client.post("/users", json=_daten("x1", "lehrkraft"), headers=teacher).status_code == 403
    assert client.post("/users", json=_daten("x2", "lehrkraft"), headers=student).status_code == 403
    assert client.post("/users", json=_daten("x3", "lehrkraft")).status_code == 401
    # auch der Admin kann keine weiteren Admins ueber die API anlegen
    assert client.post("/users", json=_daten("x4", "admin"), headers=admin).status_code == 422
