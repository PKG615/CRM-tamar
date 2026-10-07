from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDPKMixin, TimestampMixin, TenantMixin


class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    ACTIVE = (QUEUED, RUNNING)
    TERMINAL = (COMPLETED, FAILED, CANCELLED)


class JobType:
    BULK_AUDIT = "BULK_AUDIT"
    CAMPAIGN_SEND = "CAMPAIGN_SEND"


class BackgroundJob(Base, UUIDPKMixin, TimestampMixin, TenantMixin):
    """
    A unit of work picked up by `python -m app.worker`. Postgres is the queue
    (SELECT ... FOR UPDATE SKIP LOCKED), so there's no Redis/Celery to run.
    Type and status are plain strings on purpose: adding a job type later
    needs no enum migration.
    """

    __tablename__ = "background_jobs"

    type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=JobStatus.QUEUED, index=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)  # e.g. {"lead_ids": [...]}
    total = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    succeeded = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
