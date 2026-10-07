from datetime import datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models import Activity, ActivityType, BackgroundJob, JobStatus, Lead, WebsiteAudit
from app.services import audit_runner
from app.services.audit_service import AuditError
from app.services.job_service import claim_next_job, requeue_stale_jobs, run_job
from app.worker import Worker


def fake_audit(url):
    if "dead" in url:
        raise AuditError("Could not reach website: timeout")
    if "boom" in url:
        raise RuntimeError("parser exploded")
    return {"overall_score": 40, "performance_score": 50, "seo_score": 35, "mobile_score": 60,
            "security_score": 45, "content_score": None, "recommendations": ["fix it"], "raw_report": {}}


@pytest.fixture(autouse=True)
def stub_audit(monkeypatch):
    monkeypatch.setattr(audit_runner, "run_website_audit", fake_audit)


@pytest.fixture
def leads(org_a):
    ids = {
        "good": org_a.make_lead("Good Site", "good.example.com"),
        "dead": org_a.make_lead("Dead Site", "dead.example.com"),
        "boom": org_a.make_lead("Boom Site", "boom.example.com"),
        "nosite": org_a.make_lead("No Website", None),
    }
    return ids


def db_job(job_id):
    with SessionLocal() as db:
        j = db.query(BackgroundJob).filter_by(id=job_id).one()
        db.expunge(j)
        return j


def test_bulk_audit_runs_in_worker_and_isolates_failures(org_a, leads):
    c = org_a.client
    r = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={})
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "QUEUED" and job["total"] == 3          # the lead with no website is skipped

    # only one active bulk audit per org
    assert c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).status_code == 409

    assert Worker().tick() is True
    done = c.get(f"/api/jobs/{job['id']}", headers=org_a.admin).json()
    assert done["status"] == "COMPLETED"
    assert (done["processed"], done["succeeded"], done["failed"]) == (3, 2, 1)
    assert "Boom Site" in done["error"] and "parser exploded" in done["error"]

    with SessionLocal() as db:
        audits = db.query(WebsiteAudit).all()
        assert len(audits) == 2                                       # good + dead(0-score); boom rolled back
        dead = db.query(Lead).filter_by(id=leads["dead"]).one()
        assert dead.website_score == 0 and dead.lead_score > 0        # unreachable site = opportunity, scored
        good = db.query(Lead).filter_by(id=leads["good"]).one()
        assert good.website_score == 40
        assert db.query(Activity).filter_by(type=ActivityType.AUDIT_COMPLETED).count() == 2

    assert Worker().tick() is False                                   # nothing left to do

    # everything with a website is audited now, so "unaudited" finds only the failed one
    again = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={})
    assert again.status_code == 202 and again.json()["total"] == 1


def test_explicit_lead_ids_ignore_other_orgs(org_a, org_b, leads):
    foreign = org_b.make_lead("Theirs", "theirs.example.com")
    r = org_a.client.post("/api/leads/bulk-audit", headers=org_a.admin,
                          json={"lead_ids": [leads["good"], foreign], "only_unaudited": False})
    assert r.status_code == 202 and r.json()["total"] == 1


def test_nothing_to_audit_is_a_clear_400(org_a):
    r = org_a.client.post("/api/leads/bulk-audit", headers=org_a.admin, json={})
    assert r.status_code == 400 and "No matching leads" in r.json()["detail"]


def test_cancel_before_start(org_a, leads):
    c = org_a.client
    job = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).json()
    assert c.post(f"/api/jobs/{job['id']}/cancel", headers=org_a.admin).json()["status"] == "CANCELLED"
    assert Worker().tick() is False
    with SessionLocal() as db:
        assert db.query(WebsiteAudit).count() == 0


def test_cancel_mid_run_keeps_finished_work(org_a, leads):
    c = org_a.client
    job = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).json()

    def cancel_after_first(_seconds):
        c.post(f"/api/jobs/{job['id']}/cancel", headers=org_a.admin)

    with SessionLocal() as db:
        run_job(db, claim_next_job(db), sleep=cancel_after_first)

    final = db_job(job["id"])
    assert final.status == JobStatus.CANCELLED and final.processed == 1
    with SessionLocal() as db:
        assert db.query(WebsiteAudit).count() == 1


def test_stale_running_job_resumes_where_it_stopped(org_a, leads):
    c = org_a.client
    job = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).json()
    with SessionLocal() as db:
        first_id = db.query(BackgroundJob).one().payload["lead_ids"][0]
        db.add(WebsiteAudit(organization_id=org_a.org_id, lead_id=first_id, overall_score=77))  # already done pre-crash
        db.query(BackgroundJob).update({
            "status": JobStatus.RUNNING, "processed": 1, "succeeded": 1,
            "updated_at": datetime.utcnow() - timedelta(minutes=30),   # worker died 30 min ago
        })
        db.commit()

    with SessionLocal() as db:
        assert requeue_stale_jobs(db) == 1
    assert Worker().tick() is True

    final = db_job(job["id"])
    assert final.status == JobStatus.COMPLETED and final.processed == 3
    with SessionLocal() as db:
        first_audits = db.query(WebsiteAudit).filter_by(lead_id=first_id).count()
        assert first_audits == 1                                        # not audited a second time


def test_a_healthy_running_job_is_not_requeued(org_a, leads):
    org_a.client.post("/api/leads/bulk-audit", headers=org_a.admin, json={})
    with SessionLocal() as db:
        claim_next_job(db)
        assert requeue_stale_jobs(db) == 0


def test_job_visibility_and_permissions(org_a, org_b, leads):
    c = org_a.client
    _, viewer = org_a.add_user("VIEWER")
    job = c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).json()

    assert c.get(f"/api/jobs/{job['id']}", headers=viewer).status_code == 200        # viewers can watch
    assert c.post(f"/api/jobs/{job['id']}/cancel", headers=viewer).status_code == 403
    assert c.get(f"/api/jobs/{job['id']}", headers=org_b.admin).status_code == 404   # other tenants can't
    assert c.post(f"/api/jobs/{job['id']}/cancel", headers=org_b.admin).status_code == 404
    assert c.get("/api/jobs", headers=org_b.admin).json() == []
