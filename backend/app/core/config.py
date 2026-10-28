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
