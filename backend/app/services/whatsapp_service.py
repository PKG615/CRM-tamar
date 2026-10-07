"""
WhatsApp Cloud API (Meta) dispatch. Uses the same credential pattern as the
other integrations — read server-side only from settings, never exposed to
the frontend.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""
import re

import httpx

from app.core.config import settings

GRAPH_API_VERSION = "v20.0"


class WhatsAppError(Exception):
    pass


def _normalize_phone(phone: str) -> str:
    """WhatsApp wants digits only, country code included, no '+' or spaces."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        raise WhatsAppError(f"Cannot send WhatsApp message: '{phone}' is not a usable phone number")
    return digits


def _post_message(payload: dict) -> dict:
    """Shared dispatch — both free-form and template sends hit the same
    Graph API endpoint, differing only in the payload's `type`/body."""
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp Business API is not configured (missing token or phone number ID)")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, headers=headers, json=payload)

    data = resp.json()
    if resp.status_code >= 400:
        error_msg = data.get("error", {}).get("message", str(data))
        raise WhatsAppError(f"WhatsApp API error: {error_msg}")

    return {
        "message_id": data.get("messages", [{}])[0].get("id"),
        "raw": data,
    }


def send_whatsapp_message(to_phone: str, message: str) -> dict:
    """
    Sends a free-form text message. Only valid within WhatsApp's 24h
    customer-service window (i.e. the contact messaged you recently) —
    for first-ever contact with a cold lead, use send_whatsapp_template
    instead, or Meta will reject the send.
    """
    to = _normalize_phone(to_phone)
    return _post_message({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    })


def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    body_params: list[str] | None = None,
    language_code: str | None = None,
) -> dict:
    """
    Sends a pre-approved template message — the only kind Meta allows for
    first-touch cold outreach (no open 24h window yet). `body_params` fills
    the template's {{1}}, {{2}}, ... placeholders in order; their count and
    meaning must match whatever was actually approved for `template_name`
    in Meta Business Manager, which this code has no way to verify ahead
    of the API call — a mismatch surfaces as a WhatsAppError from Meta.
    """
    to = _normalize_phone(to_phone)
    components = []
    if body_params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in body_params],
        })

    return _post_message({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code or settings.WHATSAPP_TEMPLATE_LANGUAGE},
            "components": components,
        },
    })
