from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActivityType, DealStage, FollowupPriority


# ---------- Followup ----------
class FollowupCreate(BaseModel):
    lead_id: str
    assigned_to: str
    due_date: date
    due_time: Optional[time] = None
    priority: FollowupPriority = FollowupPriority.MEDIUM
    notes: Optional[str] = None


class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lead_id: str
    assigned_to: str
    due_date: date
    due_time: Optional[time] = None
    priority: str
    notes: Optional[str] = None
    status: str


class FollowupComplete(BaseModel):
    notes: Optional[str] = None


class FollowupReschedule(BaseModel):
    new_due_date: date
    new_due_time: Optional[time] = None


# ---------- Activity ----------
class ActivityCreate(BaseModel):
    lead_id: str
    type: ActivityType
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lead_id: str
    user_id: Optional[str] = None
    type: str
    description: Optional[str] = None
    created_at: datetime


# ---------- Deal ----------
class DealCreate(BaseModel):
    lead_id: str
    name: str = Field(min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, ge=0)
    stage: DealStage = DealStage.NEW
    probability: int = Field(default=0, ge=0, le=100)
    expected_close_date: Optional[date] = None
    sales_owner: Optional[str] = None
    notes: Optional[str] = None


class DealUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, ge=0)
    stage: Optional[DealStage] = None
    probability: Optional[int] = Field(default=None, ge=0, le=100)
    expected_close_date: Optional[date] = None
    sales_owner: Optional[str] = None
    notes: Optional[str] = None


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lead_id: str
    name: str
    amount: Optional[Decimal] = None
    stage: str
    probability: int
    expected_close_date: Optional[date] = None
    sales_owner: Optional[str] = None


# ---------- Proposal ----------
class ProposalLineItem(BaseModel):
    service: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class ProposalCreate(BaseModel):
    deal_id: str
    lead_id: str
    line_items: list[ProposalLineItem] = Field(min_length=1)
    terms: Optional[str] = None
    validity_days: int = 30
    payment_terms: Optional[str] = None


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_id: str
    lead_id: str
    proposal_number: str
    subtotal: Decimal
    grand_total: Decimal
    status: str


# ---------- Customer ----------
class CustomerConvertRequest(BaseModel):
    lead_id: str
    deal_id: Optional[str] = None
    company_name: Optional[str] = None  # defaults to lead.business_name
    contact_person: Optional[str] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_lead_id: str
    company_name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
