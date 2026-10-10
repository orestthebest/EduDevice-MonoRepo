"""
EduDevice REST-API - Datenbankverbindung
Die Verbindungsdaten stehen NICHT im Code (sonst landet das Passwort auf GitHub),
sondern in der Umgebungsvariable EDUDEVICE_DB_URL.

Beispiel Windows (cmd):
  set EDUDEVICE_DB_URL=mysql+pymysql://root:PASSWORT@localhost:3306/edudevice_db
Beispiel Linux (Server):
  export EDUDEVICE_DB_URL="mysql+pymysql://root:PASSWORT@localhost:3306/edudevice_db"
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_URL = os.getenv("EDUDEVICE_DB_URL")
if not DB_URL:
    raise RuntimeError(
        "Umgebungsvariable EDUDEVICE_DB_URL ist nicht gesetzt. "
        "Siehe Kommentar oben in database.py."
    )

engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Liefert pro Anfrage eine DB-Session und schliesst sie danach wieder."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
