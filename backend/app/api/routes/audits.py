from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import WebsiteAudit, User
from app.services.audit_runner import perform_audit
from app.core.tenancy import get_org_lead

router = APIRouter(prefix="/api/leads", tags=["audits"])


@router.get("/{lead_id}/audits")
def list_audits(lead_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(WebsiteAudit)
        .filter(WebsiteAudit.organization_id == user.organization_id, WebsiteAudit.lead_id == lead_id)
        .order_by(WebsiteAudit.created_at.desc())
        .all()
    )


@router.post("/{lead_id}/audit")
def run_audit(lead_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """[Run audit] on one lead — synchronous, fine for a single click. For many
    leads use POST /api/leads/bulk-audit, which runs in the background worker."""
    lead = get_org_lead(db, user.organization_id, lead_id)
    if not lead.website:
        raise HTTPException(status_code=400, detail="This lead has no website to audit")

    audit = perform_audit(db, lead, user.id)
    db.commit()
    db.refresh(audit)
    return audit
