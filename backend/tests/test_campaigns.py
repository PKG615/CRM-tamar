"""
Bulk campaign tests. Email/SMS delivery is monkeypatched at job_service's
import site (same pattern as test_email_auth.py / test_whatsapp_pitch.py)
so nothing here touches a real SMTP server or Twilio.
"""
import app.services.job_service as job_service
from app.core.database import SessionLocal
from app.models import Campaign, CampaignRecipient, CampaignStatus, RecipientStatus
from app.services.job_service import claim_next_job, run_job
from app.worker import Worker


def _run_the_queued_job():
    """Campaigns send via the same worker queue as bulk audits."""
    return Worker().tick()


def test_email_campaign_sends_to_matching_leads(org_a, monkeypatch):
    sent = []
    monkeypatch.setattr(job_service.email_service, "send_email",
                         lambda to, subject, html, text=None: sent.append((to, subject, text)) or True)

    org_a.make_lead("Acme Cafe", "acme.com", email="owner@acme.com", city="Pune")
    org_a.make_lead("No Email Biz", "noemail.com", email=None, city="Pune")  # excluded: no email
    c = org_a.client

    preview = c.post("/api/campaigns/preview", headers=org_a.admin, json={
        "name": "x", "channel": "EMAIL", "subject": "x", "message": "x", "filters": {"city": "Pune"},
    })
    assert preview.status_code == 200 and preview.json()["count"] == 1

    r = c.post("/api/campaigns", headers=org_a.admin, json={
        "name": "Pune outreach", "channel": "EMAIL", "subject": "Hello {{business_name}}",
        "message": "Hi {{contact_name}}, we noticed {{business_name}} in {{city}}.",
        "filters": {"city": "Pune"},
    })
    assert r.status_code == 202, r.text
    campaign = r.json()
    assert campaign["status"] == "QUEUED" and campaign["total"] == 1

    assert _run_the_queued_job() is True
    done = c.get(f"/api/campaigns/{campaign['id']}", headers=org_a.admin).json()
    assert done["status"] == "COMPLETED" and done["sent"] == 1 and done["failed"] == 0

    assert len(sent) == 1
    to, subject, text = sent[0]
    assert to == "owner@acme.com"
    assert subject == "Hello Acme Cafe"
    assert "Hi Acme Cafe, we noticed Acme Cafe in Pune." == text

    recipients = c.get(f"/api/campaigns/{campaign['id']}/recipients", headers=org_a.admin).json()
    assert len(recipients) == 1 and recipients[0]["status"] == "SENT"


def test_sms_campaign_partial_failure_isolated_per_recipient(org_a, monkeypatch):
    def fake_sms(to, message):
        if to == "+911111111111":
            raise job_service.sms_service.SMSError("invalid number")
        return {"message_id": "SMfake"}

    monkeypatch.setattr(job_service.sms_service, "send_sms", fake_sms)

    org_a.make_lead("Good Phone Co", "good.com", phone="+919999999999")
    org_a.make_lead("Bad Phone Co", "bad.com", phone="+911111111111")
    c = org_a.client

    r = c.post("/api/campaigns", headers=org_a.admin, json={
        "name": "SMS blast", "channel": "SMS", "message": "Hi {{business_name}}", "filters": {},
    })
    assert r.status_code == 202
    campaign = r.json()
    assert campaign["total"] == 2

    assert _run_the_queued_job() is True
    done = c.get(f"/api/campaigns/{campaign['id']}", headers=org_a.admin).json()
    assert done["status"] == "COMPLETED"
    assert done["sent"] == 1 and done["failed"] == 1
    assert "Bad Phone Co" in done["error"] and "invalid number" in done["error"]

    recipients = c.get(f"/api/campaigns/{campaign['id']}/recipients", headers=org_a.admin).json()
    statuses = {r["status"] for r in recipients}
    assert statuses == {"SENT", "FAILED"}


def test_email_campaign_without_subject_is_rejected(org_a):
    r = org_a.client.post("/api/campaigns", headers=org_a.admin, json={
        "name": "x", "channel": "EMAIL", "message": "hi", "filters": {},
    })
    assert r.status_code == 400 and "subject" in r.json()["detail"].lower()


def test_no_matching_leads_is_a_clear_400(org_a):
    org_a.make_lead("No Phone Biz", "x.com", phone=None, email=None)
    r = org_a.client.post("/api/campaigns", headers=org_a.admin, json={
        "name": "x", "channel": "SMS", "message": "hi", "filters": {},
    })
    assert r.status_code == 400 and "No leads match" in r.json()["detail"]


def test_tenant_isolation(org_a, org_b):
    org_a.make_lead("Mine", "mine.com", email="a@mine.com")
    org_b.make_lead("Theirs", "theirs.com", email="b@theirs.com")

    r = org_a.client.post("/api/campaigns/preview", headers=org_a.admin, json={
        "name": "x", "channel": "EMAIL", "subject": "x", "message": "x", "filters": {},
    })
    assert r.json()["count"] == 1  # only org_a's lead, never org_b's

    campaign = org_a.client.post("/api/campaigns", headers=org_a.admin, json={
        "name": "x", "channel": "EMAIL", "subject": "x", "message": "x", "filters": {},
    }).json()
    assert org_b.client.get(f"/api/campaigns/{campaign['id']}", headers=org_b.admin).status_code == 404


def test_viewer_cannot_create_or_cancel_campaign(org_a):
    _, viewer = org_a.add_user("VIEWER")
    org_a.make_lead("X", "x.com", email="x@x.com")
    r = org_a.client.post("/api/campaigns", headers=viewer, json={
        "name": "x", "channel": "EMAIL", "subject": "x", "message": "x", "filters": {},
    })
    assert r.status_code == 403
    # but a viewer CAN list/read campaigns
    assert org_a.client.get("/api/campaigns", headers=viewer).status_code == 200


def test_cancel_mid_run_keeps_sent_messages(org_a, monkeypatch):
    monkeypatch.setattr(job_service.email_service, "send_email", lambda *a, **kw: True)
    for i in range(3):
        org_a.make_lead(f"Biz {i}", f"biz{i}.com", email=f"b{i}@biz.com")
    c = org_a.client

    campaign = c.post("/api/campaigns", headers=org_a.admin, json={
        "name": "x", "channel": "EMAIL", "subject": "x", "message": "x", "filters": {},
    }).json()

    def cancel_after_first(_seconds):
        c.post(f"/api/campaigns/{campaign['id']}/cancel", headers=org_a.admin)

    with SessionLocal() as db:
        run_job(db, claim_next_job(db), sleep=cancel_after_first)

    with SessionLocal() as db:
        final = db.query(Campaign).filter_by(id=campaign["id"]).one()
        assert final.status == CampaignStatus.CANCELLED
        assert final.sent == 1  # the one message sent before cancellation stays sent
        sent_recipients = db.query(CampaignRecipient).filter_by(
            campaign_id=campaign["id"], status=RecipientStatus.SENT
        ).count()
        assert sent_recipients == 1
