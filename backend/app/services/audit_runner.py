"""
"Audit one lead" as a single unit, shared by the [Run audit] button and the
bulk-audit background job so both behave identically.
"""
from sqlalchemy.orm import Session

from app.models import ActivityType, Lead, WebsiteAudit
from app.services import scoring_service
from app.services.activity_service import log_activity
from app.services.audit_service import AuditError, run_website_audit


def perform_audit(db: Session, lead: Lead, user_id: str | None) -> WebsiteAudit:
    """
    Runs the audit, stores it, logs the timeline event and recalculates the
    lead's score. Flushes but does NOT commit — the caller owns the
    transaction. An unreachable site isn't an error: it's stored as a
    zero-score audit, because "website unavailable" is itself a scoring signal.
    """
    try:
        report = run_website_audit(lead.website)
    except AuditError as e:
        report = {
            "overall_score": 0, "performance_score": None, "seo_score": None,
            "mobile_score": None, "security_score": None, "content_score": None,
            "recommendations": [f"Website could not be reached: {e}"],
            "raw_report": {"error": str(e)},
        }

    audit = WebsiteAudit(organization_id=lead.organization_id, lead_id=lead.id, **report)
    db.add(audit)
    db.flush()

    log_activity(db, lead.organization_id, lead.id, ActivityType.AUDIT_COMPLETED,
                 description=f"Website audit completed — overall score {audit.overall_score}", user_id=user_id)
    scoring_service.recalculate_lead(db, lead)
    return audit
