from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Followup, FollowupStatus, Lead, User, ActivityType
from app.core.tenancy import get_org_lead, ensure_org_user
from app.schemas.crm import FollowupCreate, FollowupComplete, FollowupReschedule
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/followups", tags=["followups"])


def _refresh_next_followup(db: Session, lead_id: str) -> None:
    """Keep Lead.next_followup_date (shown in the leads table and Kanban
    cards) equal to the earliest PENDING follow-up, or NULL if none."""
    db.flush()
    earliest = (
        db.query(func.min(Followup.due_date))
        .filter(Followup.lead_id == lead_id, Followup.status == FollowupStatus.PENDING)
        .scalar()
    )
    db.query(Lead).filter(Lead.id == lead_id).update({"next_followup_date": earliest})


@router.get("")
def list_followups(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Grouped into overdue / due today / upcoming (requirement #11)."""
    today = date.today()
    base = db.query(Followup).filter(
        Followup.organization_id == user.organization_id,
        Followup.status == FollowupStatus.PENDING,
    )
    overdue = base.filter(Followup.due_date < today).order_by(Followup.due_date).all()
    due_today = base.filter(Followup.due_date == today).order_by(Followup.due_time).all()
    upcoming = base.filter(Followup.due_date > today).order_by(Followup.due_date).all()

    return {"overdue": overdue, "due_today": due_today, "upcoming": upcoming}


@router.post("")
def create_followup(payload: FollowupCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    get_org_lead(db, user.organization_id, payload.lead_id)
    ensure_org_user(db, user.organization_id, payload.assigned_to)
    followup = Followup(organization_id=user.organization_id, **payload.model_dump())
    db.add(followup)
    _refresh_next_followup(db, payload.lead_id)
    log_activity(db, user.organization_id, payload.lead_id, ActivityType.FOLLOW_UP,
                 description=f"Follow-up scheduled for {payload.due_date}", user_id=user.id)
    db.commit()
    db.refresh(followup)
    return followup


def _get_owned_followup(db: Session, followup_id: str, user: User) -> Followup:
    f = db.query(Followup).filter(
        Followup.id == followup_id, Followup.organization_id == user.organization_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return f


@router.post("/{followup_id}/complete")
def complete_followup(followup_id: str, payload: FollowupComplete, db: Session = Depends(get_db),
                       user: User = Depends(require_writer)):
    f = _get_owned_followup(db, followup_id, user)
    f.status = FollowupStatus.COMPLETED
    if payload.notes:
        f.notes = (f.notes or "") + f"\n[Completed] {payload.notes}"
    _refresh_next_followup(db, f.lead_id)
    # requirement #11: completing a follow-up auto-creates an activity
    log_activity(db, user.organization_id, f.lead_id, ActivityType.FOLLOW_UP,
                 description="Follow-up completed", user_id=user.id)
    db.commit()
    db.refresh(f)
    return f


@router.post("/{followup_id}/reschedule")
def reschedule_followup(followup_id: str, payload: FollowupReschedule, db: Session = Depends(get_db),
                         user: User = Depends(require_writer)):
    f = _get_owned_followup(db, followup_id, user)
    f.status = FollowupStatus.RESCHEDULED
    old_date = f.due_date
    f.due_date = payload.new_due_date
    f.due_time = payload.new_due_time
    f.status = FollowupStatus.PENDING  # rescheduled follow-up is pending again at the new time
    _refresh_next_followup(db, f.lead_id)
    log_activity(db, user.organization_id, f.lead_id, ActivityType.FOLLOW_UP,
                 description=f"Rescheduled from {old_date} to {payload.new_due_date}", user_id=user.id)
    db.commit()
    db.refresh(f)
    return f
