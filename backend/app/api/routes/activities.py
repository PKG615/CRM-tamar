from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Activity, ActivityType, User
from app.schemas.crm import ActivityCreate
from app.services.activity_service import log_activity
from app.core.tenancy import get_org_lead

router = APIRouter(prefix="/api/leads", tags=["activities"])


@router.get("/{lead_id}/activities")
def list_activities(lead_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Chronological timeline (requirement #9) — oldest first."""
    return (
        db.query(Activity)
        .filter(Activity.organization_id == user.organization_id, Activity.lead_id == lead_id)
        .order_by(Activity.created_at.asc())
        .all()
    )


@router.post("/{lead_id}/activities")
def create_activity(lead_id: str, payload: ActivityCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    get_org_lead(db, user.organization_id, lead_id)
    activity = log_activity(
        db, user.organization_id, lead_id, payload.type,
        description=payload.description, user_id=user.id,
    )
    db.commit()
    db.refresh(activity)
    return activity
