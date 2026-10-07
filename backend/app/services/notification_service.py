from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Followup, FollowupStatus, Lead, Notification, NotificationType


def notify(
    db: Session,
    organization_id: str,
    user_id: str,
    notif_type: NotificationType,
    message: str,
    link: str | None = None,
) -> Notification:
    """
    Every place that should alert a user creates the row here instead of
    ad hoc — keeps the notification list's shape consistent and makes it
    easy to later fan this out to email/push without touching callers.
    """
    n = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=notif_type,
        message=message,
        link=link,
    )
    db.add(n)
    db.flush()
    return n


def sweep_followups(db: Session, today: date | None = None, now: datetime | None = None) -> dict:
    """
    Notifies each assignee about every PENDING follow-up that is due today or
    overdue, across all organizations. Idempotent: a follow-up gets at most one
    notification of a given type per ~20 hours, so running the sweep twice (two
    workers, a restart, a cron misfire) never double-notifies.
    """
    today = today or date.today()
    now = now or datetime.utcnow()
    since = now - timedelta(hours=20)

    rows = (
        db.query(Followup, Lead.business_name)
        .join(Lead, Lead.id == Followup.lead_id)
        .filter(Followup.status == FollowupStatus.PENDING, Followup.due_date <= today)
        .all()
    )
    sent = 0
    for f, business in rows:
        overdue = f.due_date < today
        notif_type = NotificationType.FOLLOWUP_OVERDUE if overdue else NotificationType.FOLLOWUP_DUE
        link = f"/followups#{f.id}"
        already = db.query(Notification.id).filter(
            Notification.organization_id == f.organization_id,
            Notification.user_id == f.assigned_to,
            Notification.type == notif_type,
            Notification.link == link,
            Notification.created_at >= since,
        ).first()
        if already:
            continue
        label = "overdue" if overdue else "due today"
        notify(db, f.organization_id, f.assigned_to, notif_type,
               f"Follow-up {label}: {business}" + (f" — {f.notes}" if f.notes else ""), link=link)
        sent += 1
    db.commit()
    return {"checked": len(rows), "notifications_sent": sent}
