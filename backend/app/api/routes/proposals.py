from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Proposal, ProposalStatus, User, ActivityType, Deal, NotificationType, Lead, Organization
from app.schemas.crm import ProposalCreate
from app.services.activity_service import log_activity
from app.services.notification_service import notify
from app.services.pdf_service import generate_proposal_pdf

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _next_proposal_number(db: Session, organization_id: str) -> str:
    year = datetime.utcnow().year
    count = db.query(func.count(Proposal.id)).filter(
        Proposal.organization_id == organization_id
    ).scalar() or 0
    return f"PROP-{year}-{count + 1:05d}"


@router.get("")
def list_proposals(deal_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Proposal).filter(Proposal.organization_id == user.organization_id)
    if deal_id:
        q = q.filter(Proposal.deal_id == deal_id)
    return q.order_by(Proposal.created_at.desc()).all()


@router.post("")
def create_proposal(payload: ProposalCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    deal = db.query(Deal).filter(Deal.id == payload.deal_id, Deal.organization_id == user.organization_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    if payload.lead_id != deal.lead_id:
        raise HTTPException(status_code=400, detail="lead_id does not match the deal's lead")

    subtotal = Decimal("0")
    line_items_dicts = []
    for item in payload.line_items:
        line_total = (Decimal(str(item.quantity)) * item.unit_price) - item.discount
        subtotal += line_total
        line_items_dicts.append({**item.model_dump(mode="json"), "line_total": str(line_total)})

    # Tax applied on subtotal using the (assumed uniform) tax_percent of the first line,
    # or per-line if you need mixed tax rates — kept simple for V1 per "don't overbuild".
    tax_percent = payload.line_items[0].tax_percent if payload.line_items else Decimal("0")
    grand_total = subtotal + (subtotal * tax_percent / Decimal("100"))

    proposal = Proposal(
        organization_id=user.organization_id,
        deal_id=payload.deal_id,
        lead_id=payload.lead_id,
        proposal_number=_next_proposal_number(db, user.organization_id),
        line_items=line_items_dicts,
        subtotal=subtotal,
        grand_total=grand_total,
        terms=payload.terms,
        validity_days=payload.validity_days,
        payment_terms=payload.payment_terms,
        status=ProposalStatus.DRAFT,
    )
    db.add(proposal)
    db.flush()

    log_activity(db, user.organization_id, payload.lead_id, ActivityType.PROPOSAL_CREATED,
                 description=f"Proposal {proposal.proposal_number} created", user_id=user.id)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/{proposal_id}/send")
def send_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    proposal = db.query(Proposal).filter(
        Proposal.id == proposal_id, Proposal.organization_id == user.organization_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    proposal.status = ProposalStatus.SENT
    db.flush()
    log_activity(db, user.organization_id, proposal.lead_id, ActivityType.PROPOSAL_SENT,
                 description=f"Proposal {proposal.proposal_number} sent", user_id=user.id)
    db.commit()
    db.refresh(proposal)
    return proposal


def _get_proposal_or_404(db: Session, proposal_id: str, user: User) -> Proposal:
    proposal = db.query(Proposal).filter(
        Proposal.id == proposal_id, Proposal.organization_id == user.organization_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/{proposal_id}/accept")
def accept_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """
    Marks a client's acceptance (recorded by whoever on the team heard
    back from the client — there's no client-facing portal yet). Notifies
    the deal's sales owner so they know to move the deal forward.
    """
    proposal = _get_proposal_or_404(db, proposal_id, user)
    proposal.status = ProposalStatus.ACCEPTED
    db.flush()

    deal = db.query(Deal).filter(Deal.id == proposal.deal_id).first()
    if deal and deal.sales_owner:
        notify(db, user.organization_id, deal.sales_owner, NotificationType.PROPOSAL_ACCEPTED,
               f"Proposal {proposal.proposal_number} was accepted", link=f"/leads/{proposal.lead_id}")

    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/{proposal_id}/reject")
def reject_proposal(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    proposal = _get_proposal_or_404(db, proposal_id, user)
    proposal.status = ProposalStatus.REJECTED
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/{proposal_id}/pdf")
def download_proposal_pdf(proposal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Generated on-demand from the stored Proposal row — no PDF is kept on
    disk, so an edited/re-priced proposal always downloads correctly
    without a stale cached file lying around.
    """
    proposal = _get_proposal_or_404(db, proposal_id, user)

    lead = db.query(Lead).filter(Lead.id == proposal.lead_id, Lead.organization_id == user.organization_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead for this proposal not found")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    pdf_bytes = generate_proposal_pdf(proposal, lead, org)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{proposal.proposal_number}.pdf"'},
    )
