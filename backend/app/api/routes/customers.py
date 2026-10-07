from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Customer, Lead, LeadStatus, User
from app.schemas.crm import CustomerConvertRequest

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("")
def list_customers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Customer)
        .filter(Customer.organization_id == user.organization_id)
        .order_by(Customer.created_at.desc())
        .all()
    )


@router.post("/convert")
def convert_lead_to_customer(
    payload: CustomerConvertRequest, db: Session = Depends(get_db), user: User = Depends(require_writer)
):
    """
    requirement #14: "Do not delete the original lead. Maintain relationship
    Lead → Customer → Deal." We just create a Customer row pointing back
    at the lead; the lead itself is untouched except its status.
    """
    lead = db.query(Lead).filter(Lead.id == payload.lead_id, Lead.organization_id == user.organization_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    existing = db.query(Customer).filter(Customer.source_lead_id == lead.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="This lead has already been converted to a customer")

    customer = Customer(
        organization_id=user.organization_id,
        source_lead_id=lead.id,
        company_name=payload.company_name or lead.business_name,
        contact_person=payload.contact_person,
        phone=lead.phone,
        email=lead.email,
        address=lead.address,
        website=lead.website,
    )
    db.add(customer)

    if lead.status != LeadStatus.WON:
        lead.status = LeadStatus.WON

    db.commit()
    db.refresh(customer)
    return customer
