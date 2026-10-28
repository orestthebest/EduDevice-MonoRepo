"""Benutzerprofil (V4.5): E-Mail aendern, Profilbild hochladen/loeschen/anzeigen.
Die User-ID kommt IMMER aus dem JWT (get_current_user), nie aus dem Request."""

import io
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import AVATAR_DIR, AVATAR_MAX_BYTES, AVATAR_SIZE
from app.core.database import get_db
from app.core.security import get_current_user
from app.routers.auth import user_out
from app.schemas import AvatarOut, ProfileUpdateIn, UserOut

router = APIRouter(prefix="/users", tags=["Benutzerprofil"])

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}          # echtes Format laut Pillow, nicht die Endung
AVATAR_NAME = re.compile(r"^\d+-\d+\.webp$")       # nur Namen, die die API selbst erzeugt
MAX_PIXELS = 40_000_000                            # Schutz gegen "Dekompressionsbomben"


def avatar_path(filename: str) -> Path:
    # .name entfernt "../" -> niemand kommt aus dem Avatar-Ordner heraus
    return AVATAR_DIR / Path(filename).name


def delete_avatar_file(filename: str | None) -> None:
    if not filename:
        return
    try:
        avatar_path(filename).unlink()
    except FileNotFoundError:
        pass


def make_avatar(data: bytes) -> Image.Image:
    """Prueft das Bild und schneidet es quadratisch (mittig) auf 256x256 zu."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise HTTPException(status_code=400, detail="Nur JPG, PNG oder WebP erlaubt")
        if img.width * img.height > MAX_PIXELS:
            raise HTTPException(status_code=400, detail="Bild hat zu viele Pixel")
        img.load()                                  # liest das ganze Bild -> kaputte Dateien fallen hier auf
        img = ImageOps.exif_transpose(img)          # Handy-Fotos richtig drehen
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Datei ist kein gueltiges Bild")
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    return ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), method=Image.LANCZOS, centering=(0.5, 0.5))


@router.patch("/me", response_model=UserOut)
def update_me(data: ProfileUpdateIn, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    """Eigene E-Mail aendern (sonst nichts). 409 wenn die E-Mail schon jemand anderer hat."""
    email = data.email.strip().lower()
    taken = db.query(m.User).filter(m.User.email == email, m.User.id != current.id).first()
    if taken:
        raise HTTPException(status_code=409, detail="E-Mail ist bereits vergeben")
    current.email = email
    try:
        db.commit()
    except IntegrityError:                          # gleichzeitige Anfrage mit derselben E-Mail
        db.rollback()
        raise HTTPException(status_code=409, detail="E-Mail ist bereits vergeben")
    db.refresh(current)
    return user_out(current)


@router.post("/me/avatar", response_model=AvatarOut)
def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db),
                  current: m.User = Depends(get_current_user)):
    """Profilbild hochladen: JPG/PNG/WebP, max. 2 MB -> 256x256 WebP. Altes Bild wird geloescht."""
    data = file.file.read(AVATAR_MAX_BYTES + 1)     # nie mehr als 2 MB + 1 Byte in den Speicher
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Bild ist zu gross (max. 2 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Bitte ein Bild auswaehlen")
    avatar = make_avatar(data)

    filename = f"{current.id}-{time.time_ns() // 1_000_000}.webp"
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    avatar.save(avatar_path(filename), "WEBP", quality=85)

    old = current.profile_image
    current.profile_image = filename
    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_avatar_file(filename)                # neue Datei wieder weg, altes Bild bleibt
        raise
    delete_avatar_file(old)                         # erst NACH dem Speichern in der DB
    return AvatarOut(profile_image=filename)


@router.delete("/me/avatar", status_code=204)
def delete_avatar(db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    """Profilbild loeschen (auch wenn keins da ist -> 204)."""
    old = current.profile_image
    current.profile_image = None
    db.commit()
    delete_avatar_file(old)
    return Response(status_code=204)


@router.get("/avatar/{filename}")
def get_avatar(filename: str, current: m.User = Depends(get_current_user)):
    """Profilbild ausliefern, nur fuer eingeloggte Benutzer."""
    name = Path(filename).name
    path = avatar_path(name)
    if not AVATAR_NAME.match(name) or not path.is_file():
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    return FileResponse(path, media_type="image/webp")
