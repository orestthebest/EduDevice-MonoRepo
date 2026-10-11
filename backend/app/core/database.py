"""Datenbankverbindung (SQLAlchemy). Die URL kommt aus config.DB_URL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DB_URL

if not DB_URL:
    raise RuntimeError(
        "Umgebungsvariable EDUDEVICE_DB_URL ist nicht gesetzt.\n"
        "Windows (cmd):  set EDUDEVICE_DB_URL=mysql+pymysql://root:PASSWORT@localhost:3306/edudevice_db\n"
        "Server:         steht in api.env und wird von systemd geladen"
    )

engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Pro Anfrage eine DB-Session, danach immer schliessen."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
