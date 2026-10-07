import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_action_token, decode_action_token, ActionTokenError,
)
from app.models import Organization, User, UserRole, PipelineStage
from app.schemas.auth import (
    OrgRegisterRequest, LoginRequest, TokenResponse, ForgotPasswordRequest, SetPasswordRequest,
)
from app.services.email_service import is_configured as email_configured, send_password_reset_email
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_STAGES = [
    "NEW", "CONTACTED", "REPLIED", "INTERESTED", "MEETING",
    "PROPOSAL", "NEGOTIATION", "WON", "LOST",
]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.post("/register", response_model=TokenResponse)
def register_organization(payload: OrgRegisterRequest, db: Session = Depends(get_db)):
    """
    Onboards a brand-new tenant: creates the Organization, the first ADMIN
    user, and seeds the default 9 pipeline stages (requirement #10 — these
    are then editable per-org from Settings, not fixed in code).
    """
    slug = slugify(payload.organization_name)
    if not slug:
        raise HTTPException(status_code=400, detail="Organization name must contain letters or numbers")
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail="An organization with a similar name already exists")

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    db.flush()  # get org.id without committing yet

    admin = User(
        organization_id=org.id,
        name=payload.admin_name,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        role=UserRole.ADMIN,
    )
    db.add(admin)

    for i, stage_name in enumerate(DEFAULT_STAGES):
        db.add(PipelineStage(
            organization_id=org.id,
            name=stage_name,
            order=i,
            is_won_stage=1 if stage_name == "WON" else 0,
            is_lost_stage=1 if stage_name == "LOST" else 0,
        ))

    try:
        db.commit()
    except IntegrityError:  # two sign-ups racing for the same slug
        db.rollback()
        raise HTTPException(status_code=400, detail="An organization with a similar name already exists")
    db.refresh(admin)

    token = create_access_token({"sub": str(admin.id), "org_id": str(org.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.slug == payload.organization_slug).first()
    if not org:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = (
        db.query(User)
        .filter(User.organization_id == org.id, User.email == payload.email, User.is_deleted.is_(False))
        .first()
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    token = create_access_token({"sub": str(user.id), "org_id": str(org.id)})
    return TokenResponse(access_token=token)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Always returns the same generic response whether or not the account
    exists — an account-enumeration guard. If it does exist (and is
    active, and email is configured), a reset link is sent.
    """
    generic_response = {"message": "If an account exists for that email, a reset link has been sent."}

    org = db.query(Organization).filter(Organization.slug == payload.organization_slug).first()
    if not org:
        return generic_response

    user = db.query(User).filter(
        User.organization_id == org.id, User.email == payload.email,
        User.is_deleted.is_(False), User.is_active.is_(True),
    ).first()
    if not user:
        return generic_response

    if email_configured():
        token = create_action_token("pwd_reset", user, expires_minutes=60)
        url = f"{settings.FRONTEND_URL}/set-password?token={token}&mode=reset"
        send_password_reset_email(user.email, user.name, url)

    return generic_response


@router.post("/set-password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)):
    """Handles both invite-acceptance and forgot-password links — the token's
    `purpose` claim is checked against whichever one the caller expects."""
    user = None
    for purpose in ("invite", "pwd_reset"):
        try:
            user = decode_action_token(payload.token, purpose, db)
            break
        except ActionTokenError:
            continue
    if not user:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired")

    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    token = create_access_token({"sub": str(user.id), "org_id": str(user.organization_id)})
    return TokenResponse(access_token=token)
