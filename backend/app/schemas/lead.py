from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    category: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    lead_score: int
    website_score: Optional[int] = None
    opportunity_level: Optional[str] = None
    estimated_deal_value_min: Optional[Decimal] = None
    estimated_deal_value_max: Optional[Decimal] = None

    status: str
    assigned_to: Optional[str] = None
    next_followup_date: Optional[date] = None
    created_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    next_followup_date: Optional[date] = None
    lead_score: Optional[int] = None


class LeadCreate(BaseModel):
    """Used by the Google-Maps ingestion job / manual entry."""

    business_name: str
    category: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    google_place_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class BulkAssignRequest(BaseModel):
    lead_ids: list[str]
    assigned_to: str


class BulkStatusUpdateRequest(BaseModel):
    lead_ids: list[str]
    status: str
