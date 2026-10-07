"""
Background worker:  python -m app.worker

Does three things in one loop:
  1. runs queued jobs (bulk website audits, campaign sends) from the
     background_jobs table
  2. once a day (after FOLLOWUP_SWEEP_HOUR, server-local time) sends the
     due/overdue follow-up notifications
  3. once a week (WEEKLY_REPORT_DAY/HOUR) emails each org's admins a
     digest

Safe to run several copies: job claiming uses SKIP LOCKED, the follow-up
sweep is idempotent, and the weekly digest's own date check keeps it to
once per day even with multiple workers (a duplicate digest in the rare
multi-worker race is a cosmetic annoyance, not a correctness bug).
"""
import logging
import signal
import time
from datetime import date, datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.job_service import claim_next_job, requeue_stale_jobs, run_job
from app.services.notification_service import sweep_followups
from app.services.report_service import send_weekly_digests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")

SWEEP_RETRY_SECONDS = 600


class Worker:
    def __init__(self) -> None:
        self.stop = False
        self.last_sweep_date: date | None = None
        self.next_sweep_attempt = 0.0
        self.last_report_date: date | None = None
        self.next_report_attempt = 0.0

    def request_stop(self, *_):
        log.info("shutdown requested — finishing current step")
        self.stop = True

    def maybe_sweep(self, db) -> None:
        now = datetime.now()
        if (
            self.last_sweep_date == now.date()
            or now.hour < settings.FOLLOWUP_SWEEP_HOUR
            or time.monotonic() < self.next_sweep_attempt
        ):
            return
        try:
            result = sweep_followups(db)
            self.last_sweep_date = now.date()
            log.info("follow-up sweep: %s", result)
        except Exception:  # noqa: BLE001
            db.rollback()
            self.next_sweep_attempt = time.monotonic() + SWEEP_RETRY_SECONDS
            log.exception("follow-up sweep failed; retrying in %ss", SWEEP_RETRY_SECONDS)

    def maybe_send_weekly_report(self, db) -> None:
        now = datetime.now()
        if (
            self.last_report_date == now.date()
            or now.weekday() != settings.WEEKLY_REPORT_DAY
            or now.hour < settings.WEEKLY_REPORT_HOUR
            or time.monotonic() < self.next_report_attempt
        ):
            return
        try:
            result = send_weekly_digests(db)
            self.last_report_date = now.date()
            log.info("weekly digest: %s", result)
        except Exception:  # noqa: BLE001
            db.rollback()
            self.next_report_attempt = time.monotonic() + SWEEP_RETRY_SECONDS
            log.exception("weekly digest failed; retrying in %ss", SWEEP_RETRY_SECONDS)

    def tick(self) -> bool:
        """One pass. Returns True if a job was run (so the caller can skip sleeping)."""
        db = SessionLocal()
        try:
            self.maybe_sweep(db)
            self.maybe_send_weekly_report(db)
            n = requeue_stale_jobs(db)
            if n:
                log.warning("requeued %s stale job(s)", n)
            job = claim_next_job(db)
            if job:
                log.info("running job %s (%s, %s items)", job.id, job.type, job.total)
                run_job(db, job)
                log.info("job %s finished: %s", job.id, job.status)
                return True
            return False
        except Exception:  # noqa: BLE001 - keep the worker alive through DB blips
            db.rollback()
            log.exception("worker tick failed")
            return False
        finally:
            db.close()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        log.info("worker started (poll every %ss)", settings.WORKER_POLL_SECONDS)
        while not self.stop:
            if not self.tick():
                time.sleep(settings.WORKER_POLL_SECONDS)
        log.info("worker stopped")


if __name__ == "__main__":
    Worker().run()
