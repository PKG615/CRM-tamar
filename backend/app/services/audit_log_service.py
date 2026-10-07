from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    organization_id: str,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    changes: dict | None = None,
) -> AuditLog:
    """
    requirement #27: an immutable trail of sensitive actions (lead
    reassignment, deal won/lost, settings changes, stage deletion).
    Never edited or deleted after being written — this is the compliance
    record, separate from the sales-facing Activity timeline.
    """
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
    )
    db.add(entry)
    db.flush()
    return entry
