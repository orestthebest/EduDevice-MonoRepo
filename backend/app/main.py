"""
EduDevice REST-API (Ziel-M-4), Schema V4.3
Start:  uvicorn app.main:app --host 0.0.0.0 --port 8000
Doku:   http://<server>:8000/docs  (Swagger)

Aufbau:
  core/      Konfiguration, Datenbank, Sicherheit (JWT, bcrypt, Rate-Limit)
  models.py  Tabellen (SQLAlchemy ORM)
  schemas.py Ein-/Ausgabeformate (Pydantic)
  services/  gemeinsame Logik (Zugriffsregeln, Datei-Upload)
  routers/   Endpunkte, eine Datei pro Bereich
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import CORS_ORIGINS
from app.core.security import limiter
from app.routers import (attendance, auth, classes, grades, homework, materials,
                         quiz, subjects, timetable)

app = FastAPI(title="EduDevice REST-API", version="2.3 (Schema V4.3)")

# Rate-Limiting (Login 10/min, Register 5/min)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: welche Browser-Seiten die API direkt aufrufen duerfen
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

# Endpunkte laut Ziel-Dokument (M-4)
app.include_router(auth.router)
app.include_router(grades.router)
app.include_router(homework.router)
app.include_router(attendance.router)
app.include_router(timetable.router)
app.include_router(quiz.router)
# Endpunkte fuer die WebApp (ersetzen das direkte SQL im Frontend, Ziel-M-2)
app.include_router(classes.router)
app.include_router(subjects.router)
app.include_router(materials.router)


@app.get("/", tags=["Info"])
def root():
    return {"message": "EduDevice REST-API laeuft. Doku unter /docs", "version": app.version}


@app.get("/health", tags=["Info"])
def health():
    """Fuer Monitoring: prueft, ob die API UND die Datenbank antworten."""
    from sqlalchemy import text
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}
