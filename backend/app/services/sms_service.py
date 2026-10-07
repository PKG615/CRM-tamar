"""
SMS via Twilio's REST API directly over httpx — no twilio SDK dependency,
same reasoning as google_maps_service.py. Stays a graceful no-op until
TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER are set.
"""
import re

import httpx

from app.core.config import settings


class SMSError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER)


def _normalize_phone(phone: str) -> str:
    """Twilio wants E.164 (+countrycode...). Best-effort: strip everything
    except digits, then re-add a single leading '+'."""
    digits_only = re.sub(r"\D", "", phone or "")
    if len(digits_only) < 8:
        raise SMSError(f"'{phone}' is not a usable phone number")
    return "+" + digits_only


def send_sms(to_phone: str, message: str) -> dict:
    """Returns {"message_id": ...} on success; raises SMSError on failure."""
    if not is_configured():
        raise SMSError("SMS is not configured (missing Twilio account SID, auth token, or from-number)")

    to = _normalize_phone(to_phone)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={"To": to, "From": settings.TWILIO_FROM_NUMBER, "Body": message},
        )

    data = resp.json()
    if resp.status_code >= 400:
        raise SMSError(f"Twilio error: {data.get('message', str(data))}")

    return {"message_id": data.get("sid")}
