from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class CampaignChannel:
    EMAIL = "EMAIL"
    SMS = "SMS"


class CampaignStatus:
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    ACTIVE = (QUEUED, RUNNING)


class RecipientStatus:
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"  # e.g. lead has no email/phone for this channel


class Campaign(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    A bulk outreach blast (email or SMS) to a filtered slice of leads.
    Mirrors the BackgroundJob/worker pattern used for bulk audits — sending
    runs in `app/worker.py` via JobType.CAMPAIGN_SEND, not inline in the
    request, so a 500-lead campaign doesn't hold an HTTP connection open.
    `total`/`sent`/`failed` are denormalized onto the campaign (in addition
    to the per-recipient rows) purely so the list view doesn't need to
    COUNT() over campaign_recipients for every row.
    """

    __tablename__ = "campaigns"

    name = Column(String(255), nullable=False)
    channel = Column(String(20), nullable=False)  # CampaignChannel
    subject = Column(String(255), nullable=True)  # email only
    message = Column(Text, nullable=False)  # may contain {{business_name}}, {{city}}, {{contact_name}}
    filters = Column(JSON, nullable=False, default=dict)  # {"status_in": [...], "city": "...", "min_score": 0}
    status = Column(String(20), nullable=False, default=CampaignStatus.DRAFT)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    total = Column(Integer, nullable=False, default=0)
    sent = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class CampaignRecipient(Base, UUIDPKMixin, TenantMixin):
    """
    One row per lead targeted by a campaign, resolved and frozen at enqueue
    time (so the campaign is deterministic and resumable, same reasoning
    as BackgroundJob.payload["lead_ids"] for bulk audits). Per-recipient
    status lets the detail view show exactly who bounced vs. who got it.
    """

    __tablename__ = "campaign_recipients"

    campaign_id = Column(UUID(as_uuid=False), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=RecipientStatus.PENDING, index=True)
    error = Column(String(500), nullable=True)
    sent_at = Column(DateTime, nullable=True)
