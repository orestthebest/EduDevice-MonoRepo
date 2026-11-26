"""
Zentrale Konfiguration. Alle Werte kommen aus Umgebungsvariablen
(am Server aus /home/student/edudevice-backend/api.env, per systemd geladen).
Passwoerter stehen NIE im Code und NIE auf GitHub.
"""

import os
from pathlib import Path

# mysql+pymysql://BENUTZER:PASSWORT@localhost:3306/edudevice_db
DB_URL = os.getenv("EDUDEVICE_DB_URL")

# Schluessel fuer die JWT-Signatur (am Server lang und zufaellig!)
SECRET_KEY = os.getenv("EDUDEVICE_SECRET_KEY", "edudevice-dev-secret-change-on-server")
TOKEN_MINUTES = int(os.getenv("EDUDEVICE_TOKEN_MINUTES", "60"))

# Komma-getrennte Liste erlaubter Browser-Origins, z. B. http://172.20.1.115:3000
CORS_ORIGINS = [o.strip() for o in os.getenv("EDUDEVICE_CORS_ORIGINS", "*").split(",") if o.strip()]

# Upload-Ordner fuer Lernmaterialien (liegt bewusst ausserhalb des Web-Ordners)
UPLOAD_DIR = Path(os.getenv("EDUDEVICE_UPLOAD_DIR", "/srv/edudevice/uploads"))
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
                      "txt", "png", "jpg", "jpeg", "mp4", "zip"}
MAX_UPLOAD_MB = int(os.getenv("EDUDEVICE_MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Rate-Limits
LOGIN_LIMIT = "10/minute"
REGISTER_LIMIT = "5/minute"

# Profilbilder (V4.5): Unterordner im Upload-Ordner, max. 2 MB, gespeichert als 256x256 WebP
AVATAR_DIR = UPLOAD_DIR / "avatars"
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_SIZE = 256

# Anhaenge zu Entschuldigungen (V4.9): eigener Ordner, max. 5 MB, max. 3 pro Entschuldigung
EXCUSE_DIR = UPLOAD_DIR / "excuses"
EXCUSE_MAX_BYTES = 5 * 1024 * 1024
EXCUSE_MAX_FILES = 3

# Stundenraster der Schule (V4.11): Periode -> (Beginn, Ende). Stundenplan-Eintraege bekommen
# ihre Uhrzeiten immer aus diesem Raster (eine Zeile pro Periode, Doppelstunde = 2 Zeilen).
from datetime import time as _t  # noqa: E402
PERIODS = {
    1: (_t(7, 45), _t(8, 30)),   2: (_t(8, 35), _t(9, 20)),   3: (_t(9, 35), _t(10, 20)),
    4: (_t(10, 25), _t(11, 10)), 5: (_t(11, 20), _t(12, 5)),  6: (_t(12, 10), _t(12, 55)),
    7: (_t(13, 0), _t(13, 45)),  8: (_t(13, 50), _t(14, 35)), 9: (_t(14, 40), _t(15, 25)),
    10: (_t(15, 30), _t(16, 15)), 11: (_t(16, 20), _t(17, 5)),
}

# E-Mail (V4.12, Ziel-M-1): die API gibt Mails an den lokalen Postfix (localhost:25) weiter,
# Postfix signiert sie mit DKIM (OpenDKIM) und stellt sie selbst zu.
# MAIL_ENABLED=0 (Standard, Tests/Entwicklung): nichts wird verschickt, Mails landen nur in mailer.OUTBOX.
MAIL_ENABLED = os.getenv("EDUDEVICE_MAIL_ENABLED", "0") == "1"
MAIL_FROM = os.getenv("EDUDEVICE_MAIL_FROM", "EduDevice <noreply@edudevice.htl-cloud.com>")
SMTP_HOST = os.getenv("EDUDEVICE_SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("EDUDEVICE_SMTP_PORT", "25"))
# Nur an diese Domains wird wirklich verschickt (Komma-Liste, leer = alle). Schutz davor,
# dass Mails an erfundene Test-Adressen wie admin@edudevice.at bei fremden Leuten landen.
MAIL_ALLOWED_DOMAINS = {d.strip().lower() for d in os.getenv("EDUDEVICE_MAIL_ALLOWED_DOMAINS", "").split(",")
                        if d.strip()}
# Adresse der WebApp, fuer Links in Mails (z. B. Passwort zuruecksetzen)
FRONTEND_URL = os.getenv("EDUDEVICE_FRONTEND_URL", "https://edudevice.htl-cloud.com").rstrip("/")

# Passwort zuruecksetzen (V4.12)
RESET_LIMIT = "3/minute"          # pro IP
RESET_TOKEN_MINUTES = 30          # so lange gilt ein Link
RESET_MAX_PER_HOUR = 3            # pro Benutzer, danach werden keine Mails mehr verschickt
