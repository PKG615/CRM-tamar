import hmac

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Notification, User
from app.services.notification_service import notify, sweep_followups
from app.models import NotificationType, Followup, FollowupStatus

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Notification).filter(
        Notification.organization_id == user.organization_id,
        Notification.user_id == user.id,
    )
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    items = q.order_by(Notification.created_at.desc()).limit(50).all()
    unread_count = db.query(Notification).filter(
        Notification.organization_id == user.organization_id,
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    ).count()
    return {"items": items, "unread_count": unread_count}


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(
        Notification.id == notification_id, Notification.user_id == user.id,
        Notification.organization_id == user.organization_id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/mark-all-read")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(
        Notification.organization_id == user.organization_id,
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/system/check-followups")
def check_followups(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """
    Meant to be called by an external scheduler (cron, a Vercel/Render
    cron job, etc.) once a day — NOT by the frontend. Sweeps every
    tenant's PENDING follow-ups and notifies the assigned rep once per
    day for anything overdue or due today.

    Not user-scoped (it has to see every org), so it's protected by a
    shared secret instead of the normal per-org JWT. If CRON_SECRET isn't
    set, the endpoint refuses to run rather than silently being open.
    """
    from app.core.config import settings as app_settings

    if not app_settings.CRON_SECRET or not hmac.compare_digest(x_cron_secret, app_settings.CRON_SECRET):
        raise HTTPException(status_code=403, detail="Invalid or missing cron secret")

    return sweep_followups(db)
