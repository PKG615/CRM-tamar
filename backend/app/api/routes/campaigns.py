from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Campaign, CampaignRecipient, CampaignStatus, Lead, User
from app.services.campaign_service import CampaignError, enqueue_campaign, matching_leads_query

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignFilters(BaseModel):
    status_in: Optional[list[str]] = None
    city: Optional[str] = None
    min_score: Optional[int] = None


class CampaignCreate(BaseModel):
    name: str
    channel: str  # EMAIL | SMS
    subject: Optional[str] = None
    message: str
    filters: CampaignFilters = Field(default_factory=CampaignFilters)


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    channel: str
    subject: Optional[str] = None
    message: str
    status: str
    total: int
    sent: int
    failed: int
    error: Optional[str] = None


class RecipientPreview(BaseModel):
    count: int


@router.post("/preview", response_model=RecipientPreview)
def preview_recipients(payload: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lets the UI show 'this will reach N leads' before actually sending."""
    try:
        count = matching_leads_query(db, user.organization_id, payload.filters.model_dump(exclude_none=True), payload.channel).count()
    except CampaignError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RecipientPreview(count=count)


@router.post("", response_model=CampaignOut, status_code=202)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    try:
        campaign = enqueue_campaign(
            db, user.organization_id, user.id,
            name=payload.name, channel=payload.channel, message=payload.message,
            subject=payload.subject, filters=payload.filters.model_dump(exclude_none=True),
        )
    except CampaignError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Campaign)
        .filter(Campaign.organization_id == user.organization_id)
        .order_by(Campaign.created_at.desc())
        .limit(50)
        .all()
    )


def _org_campaign_or_404(db: Session, user: User, campaign_id: str) -> Campaign:
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id, Campaign.organization_id == user.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _org_campaign_or_404(db, user, campaign_id)


class RecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lead_id: str
    status: str
    error: Optional[str] = None


@router.get("/{campaign_id}/recipients", response_model=list[RecipientOut])
def list_recipients(campaign_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _org_campaign_or_404(db, user, campaign_id)
    return (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.id)
        .limit(500)
        .all()
    )


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
def cancel_campaign(campaign_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """
    Cancels via the underlying BackgroundJob too (not just the Campaign
    row) — otherwise a worker mid-send would keep going since job_service
    checks job.status, not campaign.status, between sends.
    """
    from app.models import BackgroundJob, JobStatus, JobType
    from datetime import datetime

    campaign = _org_campaign_or_404(db, user, campaign_id)
    if campaign.status not in CampaignStatus.ACTIVE:
        return campaign

    # Filtered in Python, not with a JSON-path DB operator: SQLite (used in
    # tests) and Postgres don't agree on JSON query syntax, and there's at
    # most a handful of active campaign jobs per org to scan.
    active_jobs = db.query(BackgroundJob).filter(
        BackgroundJob.organization_id == user.organization_id,
        BackgroundJob.type == JobType.CAMPAIGN_SEND,
        BackgroundJob.status.in_(JobStatus.ACTIVE),
    ).all()
    job = next((j for j in active_jobs if j.payload.get("campaign_id") == campaign_id), None)
    if job:
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.utcnow()

    campaign.status = CampaignStatus.CANCELLED
    campaign.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return campaign
