from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    # Direct bcrypt (passlib is unmaintained and breaks on bcrypt>=4.1/5.x).
    # Callers cap passwords at 72 bytes in the request schemas.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:  # over-long password or malformed hash: treat as a failed login, not a 500
        return False


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Decodes the JWT (contains user_id + organization_id), loads the user,
    and hard-asserts the token's org matches the user's stored org — this
    is the single choke point every protected route goes through, so a
    tenant can never see another tenant's data by forging a request.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        org_id: str = payload.get("org_id")
        if user_id is None or org_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if user is None or str(user.organization_id) != str(org_id):
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    return user


def require_roles(*allowed_roles: str):
    """Route dependency factory: Depends(require_roles('ADMIN', 'SALES_MANAGER'))"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


def require_not_viewer(user: User = Depends(get_current_user)) -> User:
    """
    Shorthand for "any real sales role, just not read-only VIEWER" — the
    default guard for write routes that don't need a specific role, just
    to exclude the Viewer role from mutating anything.
    """
    if user.role.value == "VIEWER":
        raise HTTPException(status_code=403, detail="Viewers cannot perform this action")
    return user


# Role model:
#   ADMIN            everything, including user management
#   SALES_MANAGER    everything except user management (settings, reassignment)
#   SALES_EXECUTIVE  day-to-day selling: create/edit leads' deals, proposals, pitches...
#   VIEWER           read-only
WRITER_ROLES = ("ADMIN", "SALES_MANAGER", "SALES_EXECUTIVE")
MANAGER_ROLES = ("ADMIN", "SALES_MANAGER")

require_writer = require_roles(*WRITER_ROLES)
require_manager = require_roles(*MANAGER_ROLES)
require_admin = require_roles("ADMIN")


# ---------------------------------------------------------------- action tokens
# Used for "set your password" links (both new-user invites and forgot-password
# resets) — a single-purpose, short-lived JWT rather than a new DB table.
#
# `pwv` is a short fingerprint of the user's CURRENT hashed password at the
# moment the token was issued. If the password changes for any reason before
# the link is used (a second reset request, an admin-triggered reset), the
# fingerprint no longer matches and the old link stops working on its own —
# no revocation list needed.

import hashlib  # noqa: E402


def _password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_action_token(purpose: str, user, expires_minutes: int) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "org_id": str(user.organization_id),
            "purpose": purpose,
            "pwv": _password_fingerprint(user.hashed_password),
        },
        expires_minutes=expires_minutes,
    )


class ActionTokenError(Exception):
    pass


def decode_action_token(token: str, expected_purpose: str, db: Session) -> User:
    """Returns the target User if the token is valid, unexpired, for the right
    purpose, and the user's password hasn't changed since it was issued."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise ActionTokenError("This link is invalid or has expired")

    if payload.get("purpose") != expected_purpose:
        raise ActionTokenError("This link is invalid or has expired")

    user = db.query(User).filter(User.id == payload.get("sub"), User.is_deleted.is_(False)).first()
    if not user or str(user.organization_id) != str(payload.get("org_id")):
        raise ActionTokenError("This link is invalid or has expired")

    if _password_fingerprint(user.hashed_password) != payload.get("pwv"):
        raise ActionTokenError("This link has already been used")

    return user
