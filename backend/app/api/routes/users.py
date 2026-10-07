import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    get_current_user, hash_password, verify_password, require_admin, require_manager,
    create_action_token,
)
from app.models import User, UserRole
from app.schemas.auth import (
    UserOut, UserDirectoryEntry, UserCreate, UserCreateResult, UserUpdate, PasswordReset, PasswordChange,
)
from app.services.audit_log_service import record as audit_record
from app.services.email_service import is_configured as email_configured, send_invite_email

router = APIRouter(prefix="/api/users", tags=["users"])


def _org_user_or_404(db: Session, organization_id: str, user_id: str) -> User:
    target = db.query(User).filter(
        User.id == user_id, User.organization_id == organization_id, User.is_deleted.is_(False)
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return target


def _active_admin_count(db: Session, organization_id: str) -> int:
    return db.query(func.count(User.id)).filter(
        User.organization_id == organization_id,
        User.role == UserRole.ADMIN,
        User.is_active.is_(True),
        User.is_deleted.is_(False),
    ).scalar() or 0


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/directory", response_model=list[UserDirectoryEntry])
def directory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Names + roles of active teammates — any member may see this (assignee dropdowns)."""
    return (
        db.query(User)
        .filter(User.organization_id == user.organization_id, User.is_active.is_(True), User.is_deleted.is_(False))
        .order_by(User.name)
        .all()
    )


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_manager)):
    return (
        db.query(User)
        .filter(User.organization_id == user.organization_id, User.is_deleted.is_(False))
        .order_by(User.created_at)
        .all()
    )


@router.post("", response_model=UserCreateResult, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """
    If `password` is given, the admin sets it directly (fastest for a quick
    setup or a demo). If omitted: with SMTP configured, the user is emailed
    a "set your password" link; without SMTP, a temporary password is
    generated and returned once in the response for the admin to share
    directly — either way, an account is created with a real, usable
    password from the start rather than a null/placeholder one.
    """
    exists = db.query(User.id).filter(
        User.organization_id == admin.organization_id, User.email == payload.email
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="A user with this email already exists in your organization")

    invited_by_email = False
    temporary_password = None
    initial_password = payload.password or secrets.token_urlsafe(18)

    new_user = User(
        organization_id=admin.organization_id,
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(initial_password),
        role=payload.role,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A user with this email already exists in your organization")

    if payload.password is None:
        if email_configured():
            token = create_action_token("invite", new_user, expires_minutes=60 * 24 * 7)
            url = f"{settings.FRONTEND_URL}/set-password?token={token}&mode=invite"
            invited_by_email = send_invite_email(new_user.email, new_user.name, admin.organization.name, url)
        if not invited_by_email:
            temporary_password = initial_password  # email failed or isn't configured — surface it once

    audit_record(db, admin.organization_id, admin.id, "USER_CREATED", "User", new_user.id,
                 changes={"email": payload.email, "role": payload.role.value, "invited_by_email": invited_by_email})
    db.commit()
    db.refresh(new_user)
    return UserCreateResult(
        id=new_user.id, name=new_user.name, email=new_user.email, role=new_user.role,
        is_active=new_user.is_active, invited_by_email=invited_by_email, temporary_password=temporary_password,
    )


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = _org_user_or_404(db, admin.organization_id, user_id)
    changes = payload.model_dump(exclude_unset=True)

    if target.id == admin.id and (
        ("role" in changes and changes["role"] != target.role)
        or changes.get("is_active") is False
    ):
        raise HTTPException(status_code=400, detail="You can't change your own role or deactivate yourself")

    removing_admin = target.role == UserRole.ADMIN and target.is_active and (
        ("role" in changes and changes["role"] != UserRole.ADMIN) or changes.get("is_active") is False
    )
    if removing_admin and _active_admin_count(db, admin.organization_id) <= 1:
        raise HTTPException(status_code=400, detail="The organization needs at least one active admin")

    diff = {}
    for field, value in changes.items():
        old = getattr(target, field)
        if old != value:
            diff[field] = {"old": getattr(old, "value", old), "new": getattr(value, "value", value)}
            setattr(target, field, value)
    if diff:
        audit_record(db, admin.organization_id, admin.id, "USER_UPDATED", "User", target.id, changes=diff)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, payload: PasswordReset, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = _org_user_or_404(db, admin.organization_id, user_id)
    target.hashed_password = hash_password(payload.new_password)
    audit_record(db, admin.organization_id, admin.id, "USER_PASSWORD_RESET", "User", target.id)
    db.commit()
    return {"ok": True}


@router.post("/me/password")
def change_own_password(payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    audit_record(db, user.organization_id, user.id, "PASSWORD_CHANGED", "User", user.id)
    db.commit()
    return {"ok": True}
