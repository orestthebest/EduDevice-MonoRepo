"""Speichern und Loeschen von Upload-Dateien im Upload-Ordner."""

import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, UPLOAD_DIR


def ext_of(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def stored_path(stored_name: str) -> Path:
    # .name entfernt "../" -> niemand kommt aus dem Upload-Ordner heraus
    return UPLOAD_DIR / Path(stored_name).name


def delete_stored_file(stored_name: str) -> None:
    try:
        stored_path(stored_name).unlink()
    except FileNotFoundError:
        pass


async def save_upload(file: UploadFile) -> tuple[str, str, str, int]:
    """Prueft und speichert eine Datei.
    Rueckgabe: (original_name, stored_name, mime_type, size_bytes)."""
    original_name = Path(file.filename or "").name
    ext = ext_of(original_name)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Dieser Dateityp ist nicht erlaubt")

    # Zufaelliger Name (UUID): nichts wird ueberschrieben, niemand kann Namen erraten
    stored_name = f"{uuid.uuid4()}.{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with open(stored_path(stored_name), "wb") as out:
            # in 1-MB-Stuecken lesen -> grosse Dateien belegen nicht den ganzen RAM
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Datei ist zu gross (max. {MAX_UPLOAD_MB} MB)")
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Bitte eine Datei auswaehlen")
    except Exception:
        delete_stored_file(stored_name)
        raise

    # MIME-Typ aus der Endung, nicht blind dem Browser glauben
    mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    return original_name, stored_name, mime, size
