from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Activity, ActivityType


def log_activity(
    db: Session,
    organization_id: str,
    lead_id: str,
    activity_type: ActivityType,
    description: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Activity:
    """
    Single choke point for writing to the timeline (requirement #9).
    Call this from every place that changes lead state — status change,
    pitch generated, follow-up completed, deal won, etc. — instead of
    letting each router write its own Activity row ad hoc.
    """
    activity = Activity(
        organization_id=organization_id,
        lead_id=lead_id,
        user_id=user_id,
        type=activity_type,
        description=description,
        created_at=datetime.utcnow(),
    )
    db.add(activity)
    db.flush()
    return activity
