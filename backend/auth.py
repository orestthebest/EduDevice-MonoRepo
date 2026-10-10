"""
EduDevice REST-API - Authentifizierung & Sicherheit
- Passwort-Hashing (bcrypt)
- JWT-Token erstellen und pruefen
- Rollenbasierte Zugriffskontrolle (schueler / lehrkraft / admin)
"""

import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User

# Geheimer Schluessel fuer die JWT-Signatur. Auf dem Server per
# Umgebungsvariable setzen; der Standardwert ist nur fuer die Entwicklung.
SECRET_KEY = os.getenv("EDUDEVICE_SECRET_KEY", "edudevice-dev-secret-change-on-server")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def role_of(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user.id), "role": role_of(user), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Liest den JWT, prueft ihn und liefert den zugehoerigen Benutzer."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungueltige Anmeldedaten",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*allowed_roles: str):
    """Erlaubt nur Benutzer mit einer der genannten Rollen."""
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if role_of(current_user) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Keine Berechtigung fuer diese Aktion",
            )
        return current_user
    return checker
