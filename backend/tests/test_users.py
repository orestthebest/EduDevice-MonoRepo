"""Tests Benutzerprofil (V4.5): PATCH /users/me, Profilbild hochladen/loeschen/anzeigen."""

import io

from PIL import Image

from app.core.config import AVATAR_DIR


def _bild(fmt="PNG", size=(400, 300), farbe=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, farbe).save(buf, fmt)
    return buf.getvalue()


def _upload(client, headers, data, name="bild.png", mime="image/png"):
    return client.post("/users/me/avatar", files={"file": (name, data, mime)}, headers=headers)


# ---------------- E-Mail ----------------
def test_email_aendern(client, teacher):
    r = client.patch("/users/me", json={"email": "Neu.Lehrer@EduDevice.at"}, headers=teacher)
    assert r.status_code == 200 and r.json()["email"] == "neu.lehrer@edudevice.at"
    assert client.get("/auth/me", headers=teacher).json()["email"] == "neu.lehrer@edudevice.at"
    # eigene E-Mail nochmal setzen ist kein Konflikt
    assert client.patch("/users/me", json={"email": "neu.lehrer@edudevice.at"}, headers=teacher).status_code == 200


def test_email_vergeben_409(client, teacher):
    assert client.patch("/users/me", json={"email": "admin@edudevice.at"}, headers=teacher).status_code == 409


def test_email_ungueltig_422(client, teacher):
    assert client.patch("/users/me", json={"email": "keine-email"}, headers=teacher).status_code == 422
    assert client.patch("/users/me", json={}, headers=teacher).status_code == 422


def test_nur_email_wird_geaendert(client, student):
    r = client.patch("/users/me", json={"email": "ts@edudevice.at", "role": "admin", "username": "x"},
                     headers=student)
    assert r.status_code == 200
    assert r.json()["role"] == "schueler" and r.json()["username"] == "tschueler"


def test_profil_ohne_login_401(client):
    assert client.patch("/users/me", json={"email": "a@b.at"}).status_code == 401
    assert _upload(client, {}, _bild()).status_code == 401
    assert client.get("/users/avatar/1-1.webp").status_code == 401


# ---------------- Profilbild ----------------
def test_avatar_hochladen_anzeigen_ersetzen_loeschen(client, student, teacher):
    assert client.get("/auth/me", headers=student).json()["profile_image"] is None

    r = _upload(client, student, _bild("JPEG", (800, 400)), "foto.jpg", "image/jpeg")
    assert r.status_code == 200, r.text
    erstes = r.json()["profile_image"]
    assert erstes.startswith("3-") and erstes.endswith(".webp")
    assert client.get("/auth/me", headers=student).json()["profile_image"] == erstes

    # andere eingeloggte Benutzer duerfen das Bild sehen
    r = client.get(f"/users/avatar/{erstes}", headers=teacher)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    bild = Image.open(io.BytesIO(r.content))
    assert bild.format == "WEBP" and bild.size == (256, 256)

    # neues Bild -> altes wird geloescht
    zweites = _upload(client, student, _bild("WEBP"), "b.webp", "image/webp").json()["profile_image"]
    assert zweites != erstes
    assert not (AVATAR_DIR / erstes).exists() and (AVATAR_DIR / zweites).exists()
    assert client.get(f"/users/avatar/{erstes}", headers=student).status_code == 404

    # loeschen
    assert client.delete("/users/me/avatar", headers=student).status_code == 204
    assert not (AVATAR_DIR / zweites).exists()
    assert client.get("/auth/me", headers=student).json()["profile_image"] is None
    assert client.delete("/users/me/avatar", headers=student).status_code == 204   # nochmal: kein Fehler


def test_avatar_falscher_typ_400(client, student):
    buf = io.BytesIO()
    Image.new("RGB", (50, 50)).save(buf, "GIF")
    assert _upload(client, student, buf.getvalue(), "a.gif", "image/gif").status_code == 400
    assert _upload(client, student, b"%PDF-1.4 kein bild", "a.png").status_code == 400


def test_avatar_kaputtes_bild_400(client, student):
    kaputt = _bild("PNG")[:200]          # abgeschnittenes PNG
    assert _upload(client, student, kaputt).status_code == 400


def test_avatar_zu_gross_413(client, student):
    assert _upload(client, student, b"\0" * (2 * 1024 * 1024 + 1)).status_code == 413


def test_avatar_pfad_tricks_404(client, student):
    assert client.get("/users/avatar/..%2F..%2Fapi.env", headers=student).status_code == 404
    assert client.get("/users/avatar/gibtsnicht.webp", headers=student).status_code == 404
    assert client.get("/users/avatar/1-123.webp", headers=student).status_code == 404
