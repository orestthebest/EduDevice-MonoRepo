"""Auth: Login (Ziel-M-4), Registrieren, eigener Benutzer, Passwort zuruecksetzen per Mail (V4.12)."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import (FRONTEND_URL, LOGIN_LIMIT, REGISTER_LIMIT, RESET_LIMIT,
                             RESET_MAX_PER_HOUR, RESET_TOKEN_MINUTES)
from app.core.database import get_db
from app.core.security import (create_access_token, get_current_user, hash_password,
                               limiter, role_of, verify_password)
from app.schemas import PasswordResetConfirmIn, PasswordResetRequestIn, RegisterIn, TokenOut, UserOut
from app.services.mailer import send_mail

router = APIRouter(prefix="/auth", tags=["Auth"])


def user_out(u: m.User) -> UserOut:
    return UserOut(id=u.id, username=u.username, first_name=u.first_name,
                   last_name=u.last_name, email=u.email, role=role_of(u),
                   profile_image=u.profile_image)


@router.post("/login", response_model=TokenOut)
@limiter.limit(LOGIN_LIMIT)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login mit Username (laut Ziel-M-4) oder E-Mail. Max. 10 Versuche pro Minute."""
    name = form.username.strip()
    user = db.query(m.User).filter(or_(m.User.username == name, m.User.email == name)).first()
    # gleiche Meldung fuer "gibt es nicht" und "falsches Passwort" -> keine Usernamen erraten
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Falscher Username oder falsches Passwort")
    return TokenOut(access_token=create_access_token(user), role=role_of(user), user_id=user.id,
                    username=user.username, first_name=user.first_name, last_name=user.last_name)


def create_user(db: Session, data: RegisterIn, role: str) -> m.User:
    """Legt einen Benutzer an (Register und POST /users). 409 bei doppeltem Username/E-Mail."""
    user = m.User(first_name=data.first_name.strip(), last_name=data.last_name.strip(),
                  username=data.username.strip(), email=data.email.strip().lower(),
                  role=role, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        msg = str(e.orig).lower()
        raise HTTPException(status_code=409, detail="E-Mail ist bereits registriert" if "email" in msg
                            else "Username ist bereits vergeben")
    db.refresh(user)
    return user


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(REGISTER_LIMIT)
def register(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    """Neues Konto, nur fuer SchuelerInnen. Lehrkraft-Konten legt der Admin an (POST /users),
    sonst koennte sich jeder Lehrer-Rechte geben."""
    if data.role != "schueler":
        raise HTTPException(status_code=403, detail="Lehrkraft-Konten werden vom Admin angelegt")
    return user_out(create_user(db, data, "schueler"))


@router.get("/me", response_model=UserOut)
def me(current: m.User = Depends(get_current_user)):
    """Wer bin ich? (ersetzt validateSession im Frontend)"""
    return user_out(current)


# ---------------- Passwort zuruecksetzen (V4.12, Ziel-M-1) ----------------
RESET_SENT = {"detail": "Wenn es ein Konto mit dieser E-Mail-Adresse gibt, wurde ein Link verschickt."}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)      # wie DATETIME in MySQL: UTC, ohne Zone


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_changed_mail(user: m.User) -> tuple[str, str, str]:
    """Hinweis-Mail nach jeder Passwortaenderung: falls es nicht der Benutzer selbst war, merkt er es."""
    return (user.email, "EduDevice: Dein Passwort wurde geändert",
            f"Hallo {user.first_name},\n\n"
            "das Passwort deines EduDevice-Kontos wurde gerade geändert.\n\n"
            "Warst du das nicht? Dann melde dich bitte sofort bei deinem Klassenvorstand "
            "oder beim Administrator.\n\n"
            "Diese Mail wurde automatisch verschickt, bitte nicht antworten.\n")


@router.post("/password-reset/request", status_code=202)
@limiter.limit(RESET_LIMIT)
def request_password_reset(request: Request, data: PasswordResetRequestIn, background: BackgroundTasks,
                           db: Session = Depends(get_db)):
    """Schickt einen Link zum Zuruecksetzen an die E-Mail-Adresse des Kontos.
    Antwortet IMMER gleich (202), auch wenn es die Adresse nicht gibt -> man kann nicht
    herausfinden, welche Adressen registriert sind. Der Link gilt 30 Minuten und nur einmal."""
    user = db.query(m.User).filter(m.User.email == data.email.strip().lower()).first()
    if user is None:
        return RESET_SENT
    now = _now()
    recent = (db.query(func.count(m.PasswordReset.id))
              .filter(m.PasswordReset.user_id == user.id,
                      m.PasswordReset.created_at >= now - timedelta(hours=1)).scalar())
    if recent >= RESET_MAX_PER_HOUR:              # niemand soll ein Postfach mit Mails fluten koennen
        return RESET_SENT
    token = secrets.token_urlsafe(32)              # 256 Bit Zufall
    db.add(m.PasswordReset(user_id=user.id, token_hash=_token_hash(token), created_at=now,
                           expires_at=now + timedelta(minutes=RESET_TOKEN_MINUTES)))
    db.commit()
    # Token nach '#': der Teil nach '#' wird vom Browser nie an einen Server geschickt
    # und landet so in keinem Log.
    link = f"{FRONTEND_URL}/reset-password#token={token}"
    background.add_task(send_mail, user.email, "EduDevice: Passwort zurücksetzen",
                        f"Hallo {user.first_name},\n\n"
                        "für dein EduDevice-Konto wurde ein neues Passwort angefordert.\n"
                        f"Über diesen Link kannst du es in den nächsten {RESET_TOKEN_MINUTES} Minuten setzen:\n\n"
                        f"{link}\n\n"
                        "Hast du das nicht angefordert? Dann ignoriere diese Mail einfach, "
                        "dein Passwort bleibt gleich.\n\n"
                        "Diese Mail wurde automatisch verschickt, bitte nicht antworten.\n")
    return RESET_SENT


@router.post("/password-reset/confirm", status_code=204)
@limiter.limit(LOGIN_LIMIT)
def confirm_password_reset(request: Request, data: PasswordResetConfirmIn, background: BackgroundTasks,
                           db: Session = Depends(get_db)):
    """Setzt das neue Passwort. 400 wenn der Link ungueltig, abgelaufen oder schon benutzt ist."""
    now = _now()
    row = db.query(m.PasswordReset).filter(m.PasswordReset.token_hash == _token_hash(data.token)).first()
    if row is None or row.used_at is not None or row.expires_at < now:
        raise HTTPException(status_code=400, detail="Link ist ungültig oder abgelaufen")
    user = db.get(m.User, row.user_id)
    user.password_hash = hash_password(data.new_password)
    # alle offenen Links dieses Benutzers sind damit verbraucht, auch aeltere
    (db.query(m.PasswordReset)
       .filter(m.PasswordReset.user_id == user.id, m.PasswordReset.used_at.is_(None))
       .update({m.PasswordReset.used_at: now}, synchronize_session=False))
    db.commit()
    background.add_task(send_mail, *password_changed_mail(user))
    return Response(status_code=204)
