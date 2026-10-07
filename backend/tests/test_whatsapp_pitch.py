"""
WhatsApp send behavior: service-level payload shape, and the route's choice
between a template (cold, first-touch) and free-form text (warm, replied
before) — the actual Graph API call is monkeypatched so no network is hit.
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.models import Pitch, PitchChannel, PitchStatus
from app.services import whatsapp_service


def _capture(monkeypatch):
    """Patches the one shared HTTP call and records every payload sent."""
    calls = []

    def fake_post(self, url, headers=None, json=None, **kw):
        calls.append(json)
        return httpx.Response(200, json={"messages": [{"id": "wamid.fake123"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return calls


def _make_pitch(org_id, lead_id, status=PitchStatus.DRAFT, message="Hi there!"):
    with SessionLocal() as db:
        p = Pitch(organization_id=org_id, lead_id=lead_id, message=message,
                   channel=PitchChannel.WHATSAPP, status=status)
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id


# ---------------------------------------------------------------- service layer

def test_free_form_payload_shape(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")

    whatsapp_service.send_whatsapp_message("+91 98765 43210", "Hello!")

    assert calls[0]["type"] == "text"
    assert calls[0]["to"] == "919876543210"  # non-digits stripped
    assert calls[0]["text"]["body"] == "Hello!"


def test_template_payload_shape(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")

    whatsapp_service.send_whatsapp_template("+91 98765 43210", "intro_offer", body_params=["Acme Cafe"])

    body = calls[0]
    assert body["type"] == "template"
    assert body["template"]["name"] == "intro_offer"
    assert body["template"]["language"]["code"] == "en_US"  # default
    assert body["template"]["components"][0]["parameters"][0]["text"] == "Acme Cafe"


def test_missing_credentials_raises_before_any_request(monkeypatch):
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "")
    with pytest.raises(whatsapp_service.WhatsAppError, match="not configured"):
        whatsapp_service.send_whatsapp_message("+919876543210", "hi")


# ---------------------------------------------------------------- route-level choice

def test_cold_lead_uses_template_when_configured(monkeypatch, org_a):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_TEMPLATE_NAME", "intro_offer")

    lead_id = org_a.make_lead(name="Acme Cafe")
    pitch_id = _make_pitch(org_a.org_id, lead_id)

    r = org_a.client.post(f"/api/leads/{lead_id}/pitch/{pitch_id}/send", headers=org_a.admin)
    assert r.status_code == 200, r.text
    assert calls[0]["type"] == "template"
    assert calls[0]["template"]["components"][0]["parameters"][0]["text"] == "Acme Cafe"


def test_cold_lead_falls_back_to_free_form_without_a_template(monkeypatch, org_a):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_TEMPLATE_NAME", "")  # none configured

    lead_id = org_a.make_lead(name="Acme Cafe")
    pitch_id = _make_pitch(org_a.org_id, lead_id)

    r = org_a.client.post(f"/api/leads/{lead_id}/pitch/{pitch_id}/send", headers=org_a.admin)
    assert r.status_code == 200, r.text
    assert calls[0]["type"] == "text"


def test_warm_lead_uses_free_form_even_with_a_template_configured(monkeypatch, org_a):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_TEMPLATE_NAME", "intro_offer")

    lead_id = org_a.make_lead(name="Acme Cafe")
    _make_pitch(org_a.org_id, lead_id, status=PitchStatus.REPLIED, message="earlier message")
    pitch_id = _make_pitch(org_a.org_id, lead_id)  # the new draft we're about to send

    r = org_a.client.post(f"/api/leads/{lead_id}/pitch/{pitch_id}/send", headers=org_a.admin)
    assert r.status_code == 200, r.text
    assert calls[0]["type"] == "text"  # already-warm conversation — no template needed


def test_failed_cold_send_without_template_gets_a_helpful_hint(monkeypatch, org_a):
    def fake_post(self, url, headers=None, json=None, **kw):
        return httpx.Response(400, json={"error": {"message": "template required"}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp_service.settings, "WHATSAPP_TEMPLATE_NAME", "")

    lead_id = org_a.make_lead(name="Acme Cafe")
    pitch_id = _make_pitch(org_a.org_id, lead_id)

    r = org_a.client.post(f"/api/leads/{lead_id}/pitch/{pitch_id}/send", headers=org_a.admin)
    assert r.status_code == 502
    assert "WHATSAPP_TEMPLATE_NAME" in r.json()["detail"]

    with SessionLocal() as db:
        assert db.query(Pitch).filter(Pitch.id == pitch_id).one().status == PitchStatus.FAILED
