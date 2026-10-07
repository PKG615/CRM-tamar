import enum

from sqlalchemy import Column, String, Integer, Numeric, Enum, ForeignKey, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class PipelineStage(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    Configurable per-organization (requirement #10: 'Pipeline stages should
    be configurable from Settings'). Seeded with LeadStatus defaults on
    org creation, but an org can rename/reorder/add stages.
    """

    __tablename__ = "pipeline_stages"

    name = Column(String(100), nullable=False)
    order = Column(Integer, nullable=False)
    is_won_stage = Column(Integer, default=0)   # 0/1 flag, kept simple
    is_lost_stage = Column(Integer, default=0)


class Lead(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """
    THE core table. Google-Maps-sourced lead-gen data AND CRM fields live
    on the same row — CRM never duplicates lead data (requirement #17).
    """

    __tablename__ = "leads"

    # --- Lead-gen / discovery fields ---
    business_name = Column(String(255), nullable=False, index=True)
    category = Column(String(150), index=True)
    phone = Column(String(50), index=True)
    email = Column(String(255), nullable=True)
    website = Column(String(500), nullable=True)
    google_maps_url = Column(String(1000), nullable=True)
    google_place_id = Column(String(255), nullable=True, index=True)
    address = Column(Text, nullable=True)
    city = Column(String(150), index=True)
    state = Column(String(150), index=True)
    country = Column(String(150), nullable=True)

    # --- Lead intelligence (computed, never hard-coded — see services/scoring.py) ---
    lead_score = Column(Integer, default=0, index=True)
    website_score = Column(Integer, nullable=True)
    opportunity_level = Column(String(50), nullable=True)  # LOW/MEDIUM/HIGH
    estimated_deal_value_min = Column(Numeric(12, 2), nullable=True)
    estimated_deal_value_max = Column(Numeric(12, 2), nullable=True)

    # --- CRM fields ---
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    next_followup_date = Column(Date, nullable=True, index=True)

    # relationships
    audits = relationship("WebsiteAudit", back_populates="lead", cascade="all, delete-orphan")
    pitches = relationship("Pitch", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="lead", cascade="all, delete-orphan")
    followups = relationship("Followup", back_populates="lead", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="lead", cascade="all, delete-orphan")
    assignee = relationship("User", foreign_keys=[assigned_to])
