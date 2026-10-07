from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_not_viewer, require_writer
from app.models import Lead, LeadStatus, User, ActivityType, PipelineStage, NotificationType
from app.services.activity_service import log_activity
from app.services.notification_service import notify

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("")
def get_pipeline(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Returns leads grouped by stage for the Kanban board. Card fields kept
    minimal (requirement #10: business name, lead score, deal value,
    assignee, next follow-up, last activity) — full detail is a separate
    call to GET /api/leads/{id}.
    """
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.organization_id == user.organization_id)
        .order_by(PipelineStage.order)
        .all()
    )

    leads = (
        db.query(Lead)
        .filter(Lead.organization_id == user.organization_id, Lead.is_deleted.is_(False))
        .all()
    )

    by_stage: dict[str, list] = {s.name: [] for s in stages}
    for lead in leads:
        by_stage.setdefault(lead.status.value, []).append({
            "id": lead.id,
            "business_name": lead.business_name,
            "lead_score": lead.lead_score,
            "assigned_to": lead.assigned_to,
            "next_followup_date": lead.next_followup_date,
        })

    return {
        "stages": [{"name": s.name, "order": s.order} for s in stages],
        "columns": by_stage,
    }


class MoveCardRequest(BaseModel):
    new_status: str


@router.put("/{lead_id}")
def move_card(
    lead_id: str,
    payload: MoveCardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.organization_id == user.organization_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        new_status = LeadStatus(payload.new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline stage")

    old_status = lead.status
    lead.status = new_status
    db.flush()

    log_activity(
        db, user.organization_id, lead.id, ActivityType.STATUS_CHANGED,
        description=f"Status changed from {old_status.value} to {new_status.value}",
        user_id=user.id,
    )
    if new_status == LeadStatus.WON:
        log_activity(db, user.organization_id, lead.id, ActivityType.DEAL_WON, user_id=user.id)
        if lead.assigned_to:
            notify(db, user.organization_id, lead.assigned_to, NotificationType.DEAL_WON,
                   f"{lead.business_name} moved to Won 🎉", link=f"/leads/{lead.id}")
    elif new_status == LeadStatus.LOST:
        log_activity(db, user.organization_id, lead.id, ActivityType.DEAL_LOST, user_id=user.id)
        if lead.assigned_to:
            notify(db, user.organization_id, lead.assigned_to, NotificationType.DEAL_LOST,
                   f"{lead.business_name} moved to Lost", link=f"/leads/{lead.id}")

    db.commit()
    db.refresh(lead)
    return lead
