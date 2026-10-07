from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Lead, User, LeadStatus, NotificationType, ActivityType
from app.services.notification_service import notify
from app.services.audit_log_service import record as audit_record
from app.services.activity_service import log_activity
from app.core.tenancy import ensure_org_user

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[LeadStatus] = Query(None, alias="status"),
    city: Optional[str] = None,
    assigned_to: Optional[str] = None,
    min_lead_score: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Every query is scoped to user.organization_id first — this is the
    tenant-isolation rule, applied at the query builder, not left to the
    caller to remember. Server-side filtering + pagination (requirement
    #22/#23: never load full datasets into the browser).
    """
    q = db.query(Lead).filter(
        Lead.organization_id == user.organization_id,
        Lead.is_deleted.is_(False),
    )

    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                Lead.business_name.ilike(like),
                Lead.phone.ilike(like),
                Lead.email.ilike(like),
                Lead.website.ilike(like),
                Lead.city.ilike(like),
                Lead.category.ilike(like),
            )
        )
    if status_filter:
        q = q.filter(Lead.status == status_filter)
    if city:
        q = q.filter(Lead.city == city)
    if assigned_to:
        q = q.filter(Lead.assigned_to == assigned_to)
    if min_lead_score is not None:
        q = q.filter(Lead.lead_score >= min_lead_score)

    total = q.count()
    items = (
        q.order_by(Lead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{lead_id}")
def get_lead(lead_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.organization_id == user.organization_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


class LeadAssignRequest(BaseModel):
    assigned_to: str


@router.put("/{lead_id}/assign")
def assign_lead(
    lead_id: str,
    payload: LeadAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    """
    Reassigning ownership of a lead is a manager-level action (role-gated),
    logged twice: once on the sales timeline (visible to the team) and once
    in the compliance audit log (requirement #27 — who reassigned what,
    and from whom to whom).
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == user.organization_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    ensure_org_user(db, user.organization_id, payload.assigned_to)

    old_owner = lead.assigned_to
    lead.assigned_to = payload.assigned_to
    db.flush()

    log_activity(db, user.organization_id, lead_id, ActivityType.STATUS_CHANGED,
                 description=f"Lead reassigned to a new owner", user_id=user.id)
    audit_record(db, user.organization_id, user.id, "LEAD_REASSIGNED", "Lead", lead_id,
                 changes={"assigned_to": {"old": old_owner, "new": payload.assigned_to}})
    notify(db, user.organization_id, payload.assigned_to, NotificationType.LEAD_ASSIGNED,
           f"You were assigned to {lead.business_name}", link=f"/leads/{lead_id}")

    db.commit()
    db.refresh(lead)
    return lead


class BulkAssignRequest(BaseModel):
    lead_ids: list[str]
    assigned_to: str


@router.post("/bulk-assign")
def bulk_assign(
    payload: BulkAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    ensure_org_user(db, user.organization_id, payload.assigned_to)
    leads = db.query(Lead).filter(
        Lead.id.in_(payload.lead_ids), Lead.organization_id == user.organization_id
    ).all()
    for lead in leads:
        lead.assigned_to = payload.assigned_to
    db.flush()
    audit_record(db, user.organization_id, user.id, "LEAD_BULK_REASSIGNED", "Lead",
                 changes={"lead_ids": payload.lead_ids, "assigned_to": payload.assigned_to})
    notify(db, user.organization_id, payload.assigned_to, NotificationType.LEAD_ASSIGNED,
           f"You were assigned {len(leads)} lead(s)")
    db.commit()
    return {"updated": len(leads)}
