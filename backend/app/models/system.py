import enum

from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, Text, Boolean, Enum, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class NotificationType(str, enum.Enum):
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    FOLLOWUP_OVERDUE = "FOLLOWUP_OVERDUE"
    MEETING_APPROACHING = "MEETING_APPROACHING"
    PROPOSAL_ACCEPTED = "PROPOSAL_ACCEPTED"
    DEAL_WON = "DEAL_WON"
    DEAL_LOST = "DEAL_LOST"


class Notification(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    link = Column(String(500), nullable=True)  # e.g. /crm/leads/:id


class Settings(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    Per-organization key/value config. Holds things the spec explicitly says
    must NOT be hard-coded: lead-scoring weights, opportunity value ranges,
    pipeline stage list, etc.

    Example rows:
      key="lead_scoring_weights"
      value={"website_unavailable": 20, "poor_website": 15, "phone_available": 10,
             "whatsapp_reply": 25, "interested": 20}

      key="opportunity_value_ranges"
      value={"LOW": [10000, 50000], "MEDIUM": [50000, 150000], "HIGH": [150000, 500000]}
    """

    __tablename__ = "settings"

    key = Column(String(150), nullable=False, index=True)
    value = Column(JSON, nullable=False)

    __table_args__ = ()


class AuditLog(Base, UUIDPKMixin, TenantMixin):
    """Immutable log of sensitive actions (requirement #27). Append-only."""

    __tablename__ = "audit_logs"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String(150), nullable=False, index=True)  # e.g. "LEAD_ASSIGNED", "DEAL_UPDATED"
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=False), nullable=True)
    changes = Column(JSON, nullable=True)  # {"field": {"old": ..., "new": ...}}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
