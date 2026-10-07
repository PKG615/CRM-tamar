"""
Ownership checks for IDs that arrive in request bodies.

Every table is tenant-scoped, but a *foreign key* in a payload (lead_id,
assigned_to, sales_owner...) is just a string the client chose. Without a
check, a user could attach records to another organization's lead or
assign work to another organization's user. These helpers make the check
one line at each call site.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Lead, User


def get_org_lead(db: Session, organization_id: str, lead_id: str) -> Lead:
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == organization_id,
        Lead.is_deleted.is_(False),
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def ensure_org_user(db: Session, organization_id: str, user_id: str | None, *, active_only: bool = True) -> None:
    """Raise 400 unless user_id is a (by default active) member of this organization."""
    if user_id is None:
        return
    q = db.query(User.id).filter(
        User.id == user_id,
        User.organization_id == organization_id,
        User.is_deleted.is_(False),
    )
    if active_only:
        q = q.filter(User.is_active.is_(True))
    if not q.first():
        raise HTTPException(status_code=400, detail="That user does not belong to your organization")
