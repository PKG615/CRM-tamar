"""
Bulk outreach campaigns. Enqueuing resolves the recipient list NOW (same
reasoning as enqueue_bulk_audit) and freezes it as CampaignRecipient rows,
so the send is deterministic and resumable by the worker.
"""
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    BackgroundJob, JobStatus, JobType, Lead, LeadStatus,
    Campaign, CampaignChannel, CampaignRecipient, CampaignStatus, RecipientStatus,
)


class CampaignError(Exception):
    """A request the caller can fix (surfaced to the API user as a 4xx)."""


PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_message(template: str, lead: Lead) -> str:
    """Fills {{business_name}}, {{city}}, {{contact_name}}, {{category}}.
    An unknown placeholder is left as-is rather than raising, so a typo in
    one campaign's template doesn't block sending to every recipient."""
    values = {
        "business_name": lead.business_name or "",
        "city": lead.city or "",
        "contact_name": lead.business_name or "there",  # leads don't have a separate contact-person field yet
        "category": lead.category or "",
    }

    def replace(match):
        key = match.group(1)
        return values.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(replace, template)


def matching_leads_query(db: Session, organization_id: str, filters: dict, channel: str):
    q = db.query(Lead).filter(Lead.organization_id == organization_id, Lead.is_deleted.is_(False))

    status_in = filters.get("status_in")
    if status_in:
        try:
            statuses = [LeadStatus(s) for s in status_in]
        except ValueError as e:
            raise CampaignError(f"Invalid lead status in filter: {e}")
        q = q.filter(Lead.status.in_(statuses))

    if filters.get("city"):
        q = q.filter(Lead.city == filters["city"])

    if filters.get("min_score") is not None:
        q = q.filter(Lead.lead_score >= filters["min_score"])

    if channel == CampaignChannel.EMAIL:
        q = q.filter(Lead.email.isnot(None), Lead.email != "")
    else:
        q = q.filter(Lead.phone.isnot(None), Lead.phone != "")

    return q


def enqueue_campaign(
    db: Session, organization_id: str, user_id: str | None,
    name: str, channel: str, message: str, subject: str | None = None, filters: dict | None = None,
) -> Campaign:
    if channel not in (CampaignChannel.EMAIL, CampaignChannel.SMS):
        raise CampaignError(f"Unknown channel: {channel}")
    if channel == CampaignChannel.EMAIL and not subject:
        raise CampaignError("Email campaigns need a subject line")

    filters = filters or {}
    leads = (
        matching_leads_query(db, organization_id, filters, channel)
        .order_by(Lead.created_at)
        .limit(settings.CAMPAIGN_MAX_RECIPIENTS)
        .all()
    )
    if not leads:
        reachability = "an email address" if channel == CampaignChannel.EMAIL else "a phone number"
        raise CampaignError(f"No leads match these filters with {reachability} on file")

    campaign = Campaign(
        organization_id=organization_id, created_by=user_id, name=name, channel=channel,
        subject=subject, message=message, filters=filters,
        status=CampaignStatus.QUEUED, total=len(leads),
    )
    db.add(campaign)
    db.flush()

    for lead in leads:
        db.add(CampaignRecipient(
            organization_id=organization_id, campaign_id=campaign.id, lead_id=lead.id,
            status=RecipientStatus.PENDING,
        ))

    db.add(BackgroundJob(
        organization_id=organization_id, created_by=user_id, type=JobType.CAMPAIGN_SEND,
        status=JobStatus.QUEUED, payload={"campaign_id": campaign.id}, total=len(leads),
    ))
    db.flush()
    return campaign
