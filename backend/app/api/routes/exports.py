import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Lead, LeadStatus, Deal, User

router = APIRouter(prefix="/api", tags=["exports"])


def _csv_response(rows: list[list], header: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/export.csv")
def export_leads(
    search: Optional[str] = None,
    status: Optional[LeadStatus] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Same filters as GET /api/leads, so 'export what I'm looking at' works."""
    q = db.query(Lead).filter(Lead.organization_id == user.organization_id, Lead.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        q = q.filter(Lead.business_name.ilike(like) | Lead.phone.ilike(like) | Lead.email.ilike(like) | Lead.city.ilike(like))
    if status:
        q = q.filter(Lead.status == status)
    if city:
        q = q.filter(Lead.city == city)

    leads = q.order_by(Lead.created_at.desc()).all()
    header = [
        "Business Name", "Category", "Phone", "Email", "Website", "City", "State", "Country",
        "Status", "Lead Score", "Opportunity Level", "Website Score", "Next Follow-up", "Created At",
    ]
    rows = [[
        l.business_name, l.category, l.phone, l.email, l.website, l.city, l.state, l.country,
        l.status.value, l.lead_score, l.opportunity_level, l.website_score, l.next_followup_date, l.created_at,
    ] for l in leads]
    return _csv_response(rows, header, "leads.csv")


@router.get("/deals/export.csv")
def export_deals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    deals = (
        db.query(Deal)
        .filter(Deal.organization_id == user.organization_id)
        .order_by(Deal.created_at.desc())
        .all()
    )
    header = ["Deal Name", "Lead ID", "Amount", "Stage", "Probability %", "Expected Close Date", "Created At"]
    rows = [[
        d.name, d.lead_id, d.amount, d.stage.value, d.probability, d.expected_close_date, d.created_at,
    ] for d in deals]
    return _csv_response(rows, header, "deals.csv")
