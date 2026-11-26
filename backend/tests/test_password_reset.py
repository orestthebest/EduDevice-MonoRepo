"""Tests Passwort zuruecksetzen per Mail (V4.12, Ziel-M-1)."""

import re
from datetime import timedelta

import pytest

from app import models as m
from app.core import config
from app.core.database import SessionLocal
from app.core.security import limiter
from app.services import mailer

EMAIL = "reset.test@schule.at"


@pytest.fixture(autouse=True)
def frisch():
    limiter.reset()                 # Rate-Limits der anderen Tests nicht mitzaehlen
    mailer.OUTBOX.clear()
    db = SessionLocal()
    db.query(m.PasswordReset).delete()
    db.commit()
    db.close()
    yield
    limiter.reset()


@pytest.fixture(scope="module")
def konto(client, admin):
    r = client.post("/users", headers=admin, json={
        "first_name": "Rita", "last_name": "Reset", "username": "rreset", "email": EMAIL,
        "password": "altesPasswort1", "role": "schueler"})
    assert r.status_code == 201, r.text
    return r.json()


def _anfordern(client, email=EMAIL):
    return client.post("/auth/password-reset/request", json={"email": email})


def _token_aus_mail():
    text = mailer.OUTBOX[-1].get_content()
    return re.search(r"#token=([A-Za-z0-9_\-]+)", text).group(1)


def _login(client, pw):
    return client.post("/auth/login", data={"username": "rreset", "password": pw}).status_code


def test_unbekannte_adresse_gleiche_antwort(client, konto):
    a = _anfordern(client, "gibtsnicht@schule.at")
    b = _anfordern(client)
    assert a.status_code == b.status_code == 202
    assert a.json() == b.json()                     # man sieht nicht, ob es das Konto gibt
    assert len(mailer.OUTBOX) == 1                  # nur fuer das echte Konto eine Mail


def test_mail_inhalt(client, konto):
    _anfordern(client, "  Reset.Test@Schule.AT ")   # Gross/Klein und Leerzeichen egal
    msg = mailer.OUTBOX[-1]
    assert msg["To"] == EMAIL
    assert msg["From"] == "EduDevice <noreply@edudevice.htl-cloud.com>"
    assert "zurücksetzen" in msg["Subject"]
    assert f"{config.FRONTEND_URL}/reset-password#token=" in msg.get_content()


def test_token_nur_als_hash_gespeichert(client, konto):
    _anfordern(client)
    token = _token_aus_mail()
    db = SessionLocal()
    row = db.query(m.PasswordReset).one()
    db.close()
    assert token not in row.token_hash and len(row.token_hash) == 64


def test_zuruecksetzen_ablauf(client, konto):
    _anfordern(client)
    token = _token_aus_mail()
    r = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "neuesPasswort1"})
    assert r.status_code == 204, r.text
    assert _login(client, "neuesPasswort1") == 200
    assert _login(client, "altesPasswort1") == 401
    assert "geändert" in mailer.OUTBOX[-1]["Subject"]          # Hinweis-Mail
    # derselbe Link geht nur einmal
    r = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "nochmalAnders1"})
    assert r.status_code == 400


def test_neues_passwort_verbraucht_alte_links(client, konto):
    _anfordern(client)
    alt = _token_aus_mail()
    _anfordern(client)
    neu = _token_aus_mail()
    assert client.post("/auth/password-reset/confirm",
                       json={"token": neu, "new_password": "passwortZwei2"}).status_code == 204
    assert client.post("/auth/password-reset/confirm",
                       json={"token": alt, "new_password": "passwortDrei3"}).status_code == 400


def test_abgelaufener_link(client, konto):
    _anfordern(client)
    token = _token_aus_mail()
    db = SessionLocal()
    row = db.query(m.PasswordReset).one()
    row.expires_at = row.created_at - timedelta(minutes=1)
    db.commit()
    db.close()
    r = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "zuSpaet1234"})
    assert r.status_code == 400


def test_falscher_token_und_zu_kurzes_passwort(client, konto):
    assert client.post("/auth/password-reset/confirm",
                       json={"token": "x" * 43, "new_password": "irgendwas123"}).status_code == 400
    _anfordern(client)
    r = client.post("/auth/password-reset/confirm", json={"token": _token_aus_mail(), "new_password": "kurz"})
    assert r.status_code == 422


def test_hoechstens_drei_mails_pro_stunde(client, konto):
    for _ in range(3):
        assert _anfordern(client).status_code == 202
    limiter.reset()                                  # IP-Limit ausschalten, nur das Benutzer-Limit testen
    assert _anfordern(client).status_code == 202
    assert len(mailer.OUTBOX) == 3


def test_ip_limit(client, konto):
    codes = [_anfordern(client, f"x{i}@schule.at").status_code for i in range(4)]
    assert codes == [202, 202, 202, 429]


def test_erlaubte_domains(client, konto, monkeypatch):
    monkeypatch.setattr(config, "MAIL_ALLOWED_DOMAINS", {"gmail.com"})
    _anfordern(client)
    assert mailer.OUTBOX == []                       # schule.at nicht erlaubt -> keine Mail


def test_passwort_aendern_schickt_hinweis(client, konto):
    _anfordern(client)
    pw = "passwortVier4"
    assert client.post("/auth/password-reset/confirm",
                       json={"token": _token_aus_mail(), "new_password": pw}).status_code == 204
    token = client.post("/auth/login", data={"username": "rreset", "password": pw}).json()["access_token"]
    mailer.OUTBOX.clear()
    r = client.post("/users/me/password", headers={"Authorization": f"Bearer {token}"},
                    json={"current_password": pw, "new_password": "passwortFuenf5"})
    assert r.status_code == 204
    assert len(mailer.OUTBOX) == 1 and mailer.OUTBOX[0]["To"] == EMAIL
