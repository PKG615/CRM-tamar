from datetime import date, timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Lead


def mk_followup(org, lead_id, days_from_today, assignee=None, notes="call back"):
    r = org.client.post("/api/followups", headers=org.admin, json={
        "lead_id": lead_id, "assigned_to": assignee or org.admin_id, "notes": notes,
        "due_date": (date.today() + timedelta(days=days_from_today)).isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def next_date(lead_id):
    with SessionLocal() as db:
        return db.query(Lead).filter_by(id=lead_id).one().next_followup_date


def test_next_followup_date_tracks_earliest_pending(org_a):
    lead = org_a.make_lead()
    assert next_date(lead) is None
    later = mk_followup(org_a, lead, 5)
    sooner = mk_followup(org_a, lead, 2)
    assert next_date(lead) == date.today() + timedelta(days=2)

    org_a.client.post(f"/api/followups/{sooner['id']}/complete", headers=org_a.admin, json={})
    assert next_date(lead) == date.today() + timedelta(days=5)

    org_a.client.post(f"/api/followups/{later['id']}/reschedule", headers=org_a.admin,
                      json={"new_due_date": (date.today() + timedelta(days=9)).isoformat()})
    assert next_date(lead) == date.today() + timedelta(days=9)

    org_a.client.post(f"/api/followups/{later['id']}/complete", headers=org_a.admin, json={})
    assert next_date(lead) is None


def test_followup_sweep_notifies_once_and_requires_secret(org_a, monkeypatch):
    c = org_a.client
    exec_id, ex = org_a.add_user("SALES_EXECUTIVE")
    lead = org_a.make_lead("Sweep Cafe")
    mk_followup(org_a, lead, -3, exec_id, "overdue one")
    mk_followup(org_a, lead, 0, exec_id, "due today")
    mk_followup(org_a, lead, 4, exec_id, "future")

    monkeypatch.setattr(settings, "CRON_SECRET", "")
    assert c.post("/api/notifications/system/check-followups").status_code == 403       # unset secret = closed
    monkeypatch.setattr(settings, "CRON_SECRET", "s3cret")
    assert c.post("/api/notifications/system/check-followups", headers={"X-Cron-Secret": "wrong"}).status_code == 403

    ok = c.post("/api/notifications/system/check-followups", headers={"X-Cron-Secret": "s3cret"})
    assert ok.json() == {"checked": 2, "notifications_sent": 2}
    again = c.post("/api/notifications/system/check-followups", headers={"X-Cron-Secret": "s3cret"})
    assert again.json()["notifications_sent"] == 0                                        # idempotent

    inbox = c.get("/api/notifications", headers=ex).json()
    assert inbox["unread_count"] == 2
    kinds = {n["type"] for n in inbox["items"]}
    assert kinds == {"FOLLOWUP_OVERDUE", "FOLLOWUP_DUE"}
    assert all("Sweep Cafe" in n["message"] for n in inbox["items"])
    assert c.get("/api/notifications", headers=org_a.admin).json()["unread_count"] == 0   # only the assignee is told


def test_recalculation_keeps_reply_bonus(org_a):
    c = org_a.client
    lead = org_a.make_lead("Scored", website=None)                 # no website (+20), has phone (+10)
    assert c.post("/api/ai/lead-score", headers=org_a.admin, json={"lead_id": lead}).json()["lead_score"] == 30
    c.post(f"/api/leads/{lead}/activities", headers=org_a.admin,
           json={"lead_id": lead, "type": "WHATSAPP_REPLY"})       # replied (+25)
    r = c.post("/api/ai/lead-score", headers=org_a.admin, json={"lead_id": lead}).json()
    assert r["lead_score"] == 55 and r["opportunity_level"] == "MEDIUM"
    c.put(f"/api/pipeline/{lead}", headers=org_a.admin, json={"new_status": "INTERESTED"})   # interested (+20)
    assert c.post("/api/ai/lead-score", headers=org_a.admin, json={"lead_id": lead}).json()["lead_score"] == 75


def test_proposal_totals_and_pdf(org_a, org_b):
    c = org_a.client
    lead = org_a.make_lead("Pdf Client")
    deal = c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead, "name": "Site"}).json()
    p = c.post("/api/proposals", headers=org_a.admin, json={
        "deal_id": deal["id"], "lead_id": lead,
        "line_items": [{"service": "Design", "quantity": 2, "unit_price": 1000, "discount": 100, "tax_percent": 18}]}).json()
    assert float(p["subtotal"]) == 1900 and float(p["grand_total"]) == 2242

    pdf = c.get(f"/api/proposals/{p['id']}/pdf", headers=org_a.admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert c.get(f"/api/proposals/{p['id']}/pdf", headers=org_b.admin).status_code == 404


def test_register_validation(client):
    body = {"organization_name": "Gamma", "admin_name": "G", "admin_email": "g@gamma.com", "admin_password": "password123"}
    assert client.post("/api/auth/register", json=body).status_code == 200
    assert client.post("/api/auth/register", json=body).status_code == 400                     # slug taken
    assert client.post("/api/auth/register", json={**body, "organization_name": "!!!"}).status_code == 400
    assert client.post("/api/auth/register", json={**body, "organization_name": "Delta", "admin_password": "short"}).status_code == 422
    login = client.post("/api/auth/login", json={"organization_slug": "gamma", "email": "G@GAMMA.com", "password": "password123"})
    assert login.status_code == 200                                                            # emails are case-insensitive
