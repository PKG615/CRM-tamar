"""
DB-backed job queue. Postgres is the queue: workers claim a QUEUED row with
SELECT ... FOR UPDATE SKIP LOCKED, so several workers can run side by side
without two of them ever taking the same job.
"""
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    BackgroundJob, JobStatus, JobType, Lead, WebsiteAudit,
    Campaign, CampaignChannel, CampaignRecipient, CampaignStatus, RecipientStatus,
)
from app.services.audit_runner import perform_audit
from app.services.campaign_service import render_message
from app.services import email_service, sms_service

log = logging.getLogger("worker")

STALE_AFTER = timedelta(minutes=10)
MAX_RECORDED_ERRORS = 5


class JobError(Exception):
    """A request the caller can fix (surfaced to the API user as a 4xx)."""


# ---------------------------------------------------------------- enqueue

def enqueue_bulk_audit(
    db: Session, organization_id: str, user_id: str | None,
    lead_ids: list[str] | None = None, only_unaudited: bool = True,
) -> BackgroundJob:
    """
    Resolves the lead list NOW (capped) and stores it in the payload, so the job
    is deterministic and resumable. Leads outside the org are silently ignored
    because the query is org-scoped.
    """
    active = db.query(BackgroundJob.id).filter(
        BackgroundJob.organization_id == organization_id,
        BackgroundJob.type == JobType.BULK_AUDIT,
        BackgroundJob.status.in_(JobStatus.ACTIVE),
    ).first()
    if active:
        raise JobError("A bulk audit is already queued or running for your organization")

    q = db.query(Lead.id).filter(
        Lead.organization_id == organization_id,
        Lead.is_deleted.is_(False),
        Lead.website.isnot(None),
        Lead.website != "",
    )
    if lead_ids:
        q = q.filter(Lead.id.in_(lead_ids))
    elif only_unaudited:
        q = q.filter(~exists().where(WebsiteAudit.lead_id == Lead.id))
    ids = [r[0] for r in q.order_by(Lead.created_at).limit(settings.BULK_AUDIT_MAX_LEADS).all()]
    if not ids:
        raise JobError("No matching leads with a website to audit")

    job = BackgroundJob(
        organization_id=organization_id, created_by=user_id, type=JobType.BULK_AUDIT,
        status=JobStatus.QUEUED, payload={"lead_ids": ids}, total=len(ids),
    )
    db.add(job)
    db.flush()
    return job


# ---------------------------------------------------------------- claim / recover

def claim_next_job(db: Session) -> BackgroundJob | None:
    job = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.status == JobStatus.QUEUED)
        .order_by(BackgroundJob.created_at)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not job:
        db.rollback()  # release the (empty) transaction
        return None
    job.status = JobStatus.RUNNING
    job.started_at = job.started_at or datetime.utcnow()
    db.commit()
    return job


def requeue_stale_jobs(db: Session) -> int:
    """A worker that died mid-job leaves it RUNNING forever. Jobs whose progress
    hasn't moved for STALE_AFTER go back to QUEUED and resume where they stopped
    (`processed` is the resume index)."""
    cutoff = datetime.utcnow() - STALE_AFTER
    n = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.status == JobStatus.RUNNING, BackgroundJob.updated_at < cutoff)
        .update({"status": JobStatus.QUEUED}, synchronize_session=False)
    )
    db.commit()
    return n


# ---------------------------------------------------------------- run

def run_job(db: Session, job: BackgroundJob, sleep=time.sleep) -> None:
    try:
        if job.type == JobType.BULK_AUDIT:
            _run_bulk_audit(db, job, sleep)
        elif job.type == JobType.CAMPAIGN_SEND:
            _run_campaign_send(db, job, sleep)
        else:
            raise JobError(f"Unknown job type: {job.type}")
    except Exception as e:  # noqa: BLE001 - a job must never take the worker down
        log.exception("job %s failed", job.id)
        db.rollback()
        db.refresh(job)
        job.status = JobStatus.FAILED
        job.error = str(e)[:1000]
        job.finished_at = datetime.utcnow()
        db.commit()


def _run_bulk_audit(db: Session, job: BackgroundJob, sleep) -> None:
    lead_ids: list[str] = job.payload.get("lead_ids", [])
    succeeded, failed = job.succeeded, job.failed
    errors: list[str] = [job.error] if job.error else []

    for i in range(job.processed, len(lead_ids)):
        db.refresh(job)
        if job.status != JobStatus.RUNNING:  # cancelled from the API
            return

        lead = db.query(Lead).filter(
            Lead.id == lead_ids[i], Lead.organization_id == job.organization_id, Lead.is_deleted.is_(False)
        ).first()
        try:
            if not lead or not lead.website:
                raise JobError("lead no longer exists or has no website")
            perform_audit(db, lead, job.created_by)
            db.commit()
            succeeded += 1
        except Exception as e:  # noqa: BLE001 - one bad site must not stop the batch
            db.rollback()
            failed += 1
            if len(errors) < MAX_RECORDED_ERRORS:
                errors.append(f"{lead.business_name if lead else lead_ids[i]}: {e}"[:200])

        job = db.merge(job)
        job.processed = i + 1
        job.succeeded, job.failed = succeeded, failed
        job.error = "\n".join(errors) or None
        db.commit()

        if i + 1 < len(lead_ids):
            sleep(settings.AUDIT_DELAY_SECONDS)  # be polite to the sites being audited

    db.refresh(job)
    if job.status == JobStatus.RUNNING:
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.utcnow()
        db.commit()


def _run_campaign_send(db: Session, job: BackgroundJob, sleep) -> None:
    campaign_id = job.payload.get("campaign_id")
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise JobError(f"campaign {campaign_id} no longer exists")

    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = campaign.started_at or datetime.utcnow()
    db.commit()

    recipients = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id, CampaignRecipient.status == RecipientStatus.PENDING)
        .order_by(CampaignRecipient.id)
        .all()
    )
    errors: list[str] = [job.error] if job.error else []

    for i, recipient in enumerate(recipients):
        db.refresh(job)
        if job.status != JobStatus.RUNNING:  # cancelled from the API
            db.refresh(campaign)
            campaign.status = CampaignStatus.CANCELLED
            campaign.finished_at = datetime.utcnow()
            db.commit()
            return

        lead = db.query(Lead).filter(Lead.id == recipient.lead_id, Lead.is_deleted.is_(False)).first()
        try:
            if not lead:
                raise JobError("lead no longer exists")
            text = render_message(campaign.message, lead)
            if campaign.channel == CampaignChannel.EMAIL:
                subject = render_message(campaign.subject, lead) if campaign.subject else campaign.subject
                ok = email_service.send_email(lead.email, subject, text.replace("\n", "<br/>"), text)
                if not ok:
                    raise JobError("email delivery failed")
            else:
                sms_service.send_sms(lead.phone, text)

            recipient.status = RecipientStatus.SENT
            recipient.sent_at = datetime.utcnow()
            campaign.sent += 1
        except Exception as e:  # noqa: BLE001 - one bad recipient must not stop the batch
            recipient.status = RecipientStatus.FAILED
            recipient.error = str(e)[:500]
            campaign.failed += 1
            if len(errors) < MAX_RECORDED_ERRORS:
                errors.append(f"{lead.business_name if lead else recipient.lead_id}: {e}"[:200])

        job = db.merge(job)
        job.processed += 1
        job.succeeded, job.failed = campaign.sent, campaign.failed
        job.error = "\n".join(errors) or None
        campaign.error = job.error
        db.commit()

        if i + 1 < len(recipients):
            sleep(settings.CAMPAIGN_DELAY_SECONDS)  # be polite to the mail/SMS provider

    db.refresh(job)
    db.refresh(campaign)
    if job.status == JobStatus.RUNNING:
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.utcnow()
        campaign.status = CampaignStatus.COMPLETED
        campaign.finished_at = datetime.utcnow()
        db.commit()
