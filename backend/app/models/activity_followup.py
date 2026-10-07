import enum

from sqlalchemy import Column, String, ForeignKey, Text, DateTime, Enum, Date, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class ActivityType(str, enum.Enum):
    LEAD_CREATED = "LEAD_CREATED"
    AUDIT_COMPLETED = "AUDIT_COMPLETED"
    PITCH_GENERATED = "PITCH_GENERATED"
    WHATSAPP_SENT = "WHATSAPP_SENT"
    WHATSAPP_REPLY = "WHATSAPP_REPLY"
    CALL = "CALL"
    EMAIL = "EMAIL"
    NOTE = "NOTE"
    MEETING = "MEETING"
    FOLLOW_UP = "FOLLOW_UP"
    STATUS_CHANGED = "STATUS_CHANGED"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    DEAL_CREATED = "DEAL_CREATED"
    DEAL_WON = "DEAL_WON"
    DEAL_LOST = "DEAL_LOST"


class Activity(Base, UUIDPKMixin, TenantMixin):
    """Append-only timeline. Never edited/deleted — that's the audit trail."""

    __tablename__ = "activities"

    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    type = Column(Enum(ActivityType), nullable=False, index=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON string: extra context per activity type
    created_at = Column(DateTime, nullable=False, index=True)

    lead = relationship("Lead", back_populates="activities")


class FollowupStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class FollowupPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Followup(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    __tablename__ = "followups"

    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    due_time = Column(Time, nullable=True)
    priority = Column(Enum(FollowupPriority), default=FollowupPriority.MEDIUM, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(Enum(FollowupStatus), default=FollowupStatus.PENDING, nullable=False, index=True)

    lead = relationship("Lead", back_populates="followups")
