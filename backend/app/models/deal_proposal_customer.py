import enum

from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, Text, Date, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class DealStage(str, enum.Enum):
    """Mirrors pipeline stages (requirement #12: 'Deal stages should map to the CRM pipeline')."""
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class Deal(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    __tablename__ = "deals"

    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=True)
    stage = Column(Enum(DealStage), default=DealStage.NEW, nullable=False, index=True)
    probability = Column(Integer, default=0)  # 0-100
    expected_close_date = Column(Date, nullable=True)
    sales_owner = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="deals")
    proposals = relationship("Proposal", back_populates="deal", cascade="all, delete-orphan")


class ProposalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Proposal(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    __tablename__ = "proposals"

    deal_id = Column(UUID(as_uuid=False), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id"), nullable=False, index=True)
    proposal_number = Column(String(50), unique=True, nullable=False)
    line_items = Column(JSON, nullable=False)  # [{service, qty, unit_price, discount, tax}]
    subtotal = Column(Numeric(12, 2), nullable=False)
    grand_total = Column(Numeric(12, 2), nullable=False)
    terms = Column(Text, nullable=True)
    validity_days = Column(Integer, default=30)
    payment_terms = Column(String(255), nullable=True)
    status = Column(Enum(ProposalStatus), default=ProposalStatus.DRAFT, nullable=False, index=True)
    pdf_path = Column(String(500), nullable=True)

    deal = relationship("Deal", back_populates="proposals")


class Customer(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    Created on lead-to-customer conversion. The lead row is NEVER deleted
    (requirement #14) — this table just links to it.
    """

    __tablename__ = "customers"

    source_lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id"), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
