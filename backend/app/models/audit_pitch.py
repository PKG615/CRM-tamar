import enum

from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class WebsiteAudit(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """Existing audit engine's results — CRM only reads this, never recomputes it."""

    __tablename__ = "audits"

    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_score = Column(Integer, nullable=False)
    performance_score = Column(Integer, nullable=True)
    seo_score = Column(Integer, nullable=True)
    mobile_score = Column(Integer, nullable=True)
    content_score = Column(Integer, nullable=True)
    security_score = Column(Integer, nullable=True)
    recommendations = Column(JSON, nullable=True)  # list[str] from the audit engine
    raw_report = Column(JSON, nullable=True)        # full engine output, for "View Full Audit"

    lead = relationship("Lead", back_populates="audits")


class PitchChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class PitchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    REPLIED = "REPLIED"
    FAILED = "FAILED"


class Pitch(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    Every AI-generated pitch is stored (requirement #8), regardless of
    whether it was ever sent — needed for the activity timeline and for
    letting a rep edit before sending.
    """

    __tablename__ = "pitches"

    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    generated_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    channel = Column(Enum(PitchChannel), default=PitchChannel.WHATSAPP, nullable=False)
    status = Column(Enum(PitchStatus), default=PitchStatus.DRAFT, nullable=False)
    sent_at = Column(DateTime, nullable=True)

    lead = relationship("Lead", back_populates="pitches")
