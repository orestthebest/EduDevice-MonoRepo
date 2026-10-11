# EduDevice REST-API (Backend)

FastAPI-Backend für EduDevice (Ziel-M-4). Architektur: siehe [ARCHITEKTUR.md](ARCHITEKTUR.md).
Für das Frontend: [docs/API_FUER_OREST.md](docs/API_FUER_OREST.md).

## Ordner

```
backend/
├── app/
│   ├── main.py              App starten, Router einbinden, CORS, Rate-Limit
│   ├── models.py            Tabellen (SQLAlchemy ORM)
│   ├── schemas.py           Ein-/Ausgabeformate (Pydantic)
│   ├── core/                config.py · database.py · security.py
│   ├── services/            access.py (Zugriffsregeln) · files.py (Uploads)
│   └── routers/             auth · grades · homework · attendance · timetable · quiz
│                            classes · subjects · materials
├── sql/                     schema_v4_2.sql · migration_v4_3.sql
├── scripts/seed.py          Testdaten
├── tests/                   automatische Tests (pytest)
├── postman/                 Postman-Collections + Anleitung (POSTMAN.md)
├── deploy/                  systemd-Service + Vorlage für api.env
├── docs/                    Anleitung + Beispielcode für die WebApp
├── requirements.txt
└── requirements-dev.txt     nur für Tests
```

## Lokal starten (Windows, cmd)

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set EDUDEVICE_DB_URL=mysql+pymysql://root:PASSWORT@localhost:3306/edudevice_db
set EDUDEVICE_UPLOAD_DIR=uploads
python -m scripts.seed
uvicorn app.main:app --reload
```
Dann: http://127.0.0.1:8000/docs

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -v
```
Die Tests benutzen eine eigene SQLite-Datei, die echte Datenbank wird nicht verändert.

Zusätzlich gibt es Postman-Tests (66 Requests, 162 Prüfungen): siehe [postman/POSTMAN.md](postman/POSTMAN.md).

## Server

- Ordner: `/home/student/edudevice-backend` (Inhalt von `backend/`)
- Service: `deploy/edudevice-api.service` → `/etc/systemd/system/`
- Einstellungen: `api.env` (Vorlage `deploy/api.env.example`, `chmod 600`, nie ins Git)

```
sudo systemctl restart edudevice-api
sudo systemctl status edudevice-api
journalctl -u edudevice-api -n 50
curl http://127.0.0.1:8000/health
```

## Datenbank

Neue Installation: `sql/schema_v4_2.sql`, danach `sql/migration_v4_3.sql`.
Bestehende V4.2-Datenbank: nur `sql/migration_v4_3.sql`.
