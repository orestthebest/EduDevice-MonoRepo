"""Auth: Login (Ziel-M-4), Registrieren und eigener Benutzer."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import LOGIN_LIMIT, REGISTER_LIMIT
from app.core.database import get_db
from app.core.security import (create_access_token, get_current_user, hash_password,
                               limiter, role_of, verify_password)
from app.schemas import RegisterIn, TokenOut, UserOut

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


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(REGISTER_LIMIT)
def register(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    """Neues Konto (schueler oder lehrkraft). Admin kann man sich nicht selbst geben."""
    user = m.User(first_name=data.first_name.strip(), last_name=data.last_name.strip(),
                  username=data.username.strip(), email=data.email.strip().lower(),
                  role=data.role, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        msg = str(e.orig).lower()
        raise HTTPException(status_code=409, detail="E-Mail ist bereits registriert" if "email" in msg
                            else "Username ist bereits vergeben")
    db.refresh(user)
    return user_out(user)


@router.get("/me", response_model=UserOut)
def me(current: m.User = Depends(get_current_user)):
    """Wer bin ich? (ersetzt validateSession im Frontend)"""
    return user_out(current)
