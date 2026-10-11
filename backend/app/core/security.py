"""
Sicherheit:
- Passwort-Hashing (bcrypt)
- JWT erstellen und pruefen
- Rollenpruefung (schueler / lehrkraft / admin)
- Rate-Limiter (Schutz gegen Passwort-Raten)
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import SECRET_KEY, TOKEN_MINUTES
from app.core.database import get_db
from app.models import User

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ---------------- Rate-Limit ----------------
def client_ip(request: Request) -> str:
    """IP fuer das Rate-Limit.
    Die WebApp laeuft am selben Server und ruft die API ueber 127.0.0.1 auf -
    dann wuerden sich alle Benutzer EIN Limit teilen. Deshalb schickt die WebApp
    die echte IP im Header X-Forwarded-For mit. Diesem Header wird NUR geglaubt,
    wenn die Anfrage von localhost kommt (sonst koennte ihn jeder faelschen)."""
    ip = get_remote_address(request)
    if ip in ("127.0.0.1", "::1"):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return ip


limiter = Limiter(key_func=client_ip)


# ---------------- Passwoerter ----------------
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------- JWT ----------------
def role_of(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {"sub": str(user.id), "role": role_of(user), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Liest den JWT aus dem Header 'Authorization: Bearer ...' und liefert den Benutzer."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Ungueltige Anmeldedaten",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise invalid
    except JWTError:
        raise invalid
    user = db.get(User, int(user_id))
    if user is None:
        raise invalid
    return user


def require_roles(*allowed: str):
    """Dependency: nur Benutzer mit einer dieser Rollen duerfen weiter."""
    def checker(current: User = Depends(get_current_user)) -> User:
        if role_of(current) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Keine Berechtigung fuer diese Aktion")
        return current
    return checker
