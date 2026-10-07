import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, declared_attr

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


class UUIDPKMixin:
    """Every table uses a UUID primary key (safe for multi-tenant, non-guessable)."""

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)


class TenantMixin:
    """
    Every tenant-owned table gets organization_id.
    All queries MUST filter by organization_id — enforced at the
    service layer (see app/core/tenancy.py) not just at the DB layer,
    because Postgres RLS alone is easy to forget in ad-hoc queries.
    """

    @declared_attr
    def organization_id(cls):
        return Column(
            UUID(as_uuid=False),
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
