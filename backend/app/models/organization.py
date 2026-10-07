import enum

from sqlalchemy import Column, String, Enum, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin


class Organization(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """A tenant. Every company using the SaaS is one row here."""

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    plan = Column(String(50), default="trial", nullable=False)  # trial/pro/enterprise
    is_active = Column(Boolean, default=True, nullable=False)

    # Per-org configurable settings live in Settings table (key/value),
    # not hard-coded here — see models/settings.py

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SALES_MANAGER = "SALES_MANAGER"
    SALES_EXECUTIVE = "SALES_EXECUTIVE"
    VIEWER = "VIEWER"


class User(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.SALES_EXECUTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    phone = Column(String(50), nullable=True)

    organization = relationship("Organization", back_populates="users")

    __table_args__ = (
        # email unique PER organization, not globally — two orgs can each have admin@x.com
        UniqueConstraint("organization_id", "email", name="uq_user_org_email"),
    )
