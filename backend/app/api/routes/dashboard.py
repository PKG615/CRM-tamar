from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Lead, LeadStatus, Deal, DealStage, Followup, FollowupStatus, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    All the cards from requirement 'A. CRM Dashboard'. Kept as a handful of
    aggregate queries (COUNT/SUM with GROUP BY), not a full table scan into
    Python — this is the endpoint to cache (requirement #23) once traffic
    justifies it, since these numbers don't need to be real-time-exact.
    """
    org_id = user.organization_id
    base = db.query(Lead).filter(Lead.organization_id == org_id, Lead.is_deleted.is_(False))

    status_counts = dict(
        base.with_entities(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    )
    status_counts = {k.value: v for k, v in status_counts.items()}

    deals_q = db.query(Deal).filter(Deal.organization_id == org_id)
    pipeline_value = deals_q.filter(Deal.stage.notin_([DealStage.WON, DealStage.LOST])).with_entities(
        func.coalesce(func.sum(Deal.amount), 0)
    ).scalar()
    won_revenue = deals_q.filter(Deal.stage == DealStage.WON).with_entities(
        func.coalesce(func.sum(Deal.amount), 0)
    ).scalar()
    won_count = deals_q.filter(Deal.stage == DealStage.WON).count()
    lost_count = deals_q.filter(Deal.stage == DealStage.LOST).count()

    today = date.today()
    followups_q = db.query(Followup).filter(
        Followup.organization_id == org_id, Followup.status == FollowupStatus.PENDING
    )
    pending_followups = followups_q.count()
    overdue_followups = followups_q.filter(Followup.due_date < today).count()

    return {
        "total_leads": base.count(),
        "new_leads": status_counts.get("NEW", 0),
        "contacted_leads": status_counts.get("CONTACTED", 0),
        "replied_leads": status_counts.get("REPLIED", 0),
        "interested_leads": status_counts.get("INTERESTED", 0),
        "meetings": status_counts.get("MEETING", 0),
        "proposals": status_counts.get("PROPOSAL", 0),
        "won_deals": won_count,
        "lost_deals": lost_count,
        "pipeline_value": float(pipeline_value or 0),
        "won_revenue": float(won_revenue or 0),
        "pending_followups": pending_followups,
        "overdue_followups": overdue_followups,
        "lead_conversion_funnel": status_counts,
    }
