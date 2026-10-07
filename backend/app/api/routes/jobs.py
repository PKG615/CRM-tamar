from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import BackgroundJob, JobStatus, User
from app.services.job_service import JobError, enqueue_bulk_audit

router = APIRouter(prefix="/api", tags=["jobs"])


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class BulkAuditRequest(BaseModel):
    # Omit lead_ids to audit every lead that has a website and no audit yet.
    lead_ids: Optional[list[str]] = Field(default=None, max_length=500)
    only_unaudited: bool = True


@router.post("/leads/bulk-audit", response_model=JobOut, status_code=202)
def bulk_audit(payload: BulkAuditRequest, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """Queues the audits for the background worker and returns immediately;
    poll GET /api/jobs/{id} for progress."""
    try:
        job = enqueue_bulk_audit(db, user.organization_id, user.id, payload.lead_ids, payload.only_unaudited)
    except JobError as e:
        raise HTTPException(status_code=409 if "already" in str(e) else 400, detail=str(e))
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(BackgroundJob)
        .filter(BackgroundJob.organization_id == user.organization_id)
        .order_by(BackgroundJob.created_at.desc())
        .limit(20)
        .all()
    )


def _org_job_or_404(db: Session, user: User, job_id: str) -> BackgroundJob:
    job = db.query(BackgroundJob).filter(
        BackgroundJob.id == job_id, BackgroundJob.organization_id == user.organization_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _org_job_or_404(db, user, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """Stops a queued/running job. Audits already finished are kept; the worker
    notices between leads, so the one in flight completes first."""
    job = _org_job_or_404(db, user, job_id)
    if job.status in JobStatus.ACTIVE:
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job
