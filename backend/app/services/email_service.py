"""
Plain SMTP via the standard library — no extra dependency, works with any
provider (SES, SendGrid, Mailgun, Postmark, a Gmail app-password relay...).

Stays a graceful no-op until SMTP_HOST is set, matching how the other
optional integrations behave (Google Maps, WhatsApp, Anthropic) — callers
check `is_configured()` and fall back to an in-app value the admin can
share directly, rather than losing the action entirely.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("email")


def is_configured() -> bool:
    return bool(settings.SMTP_HOST)


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """
    Returns True if the message was handed to the SMTP server successfully.
    Never raises — a broken mail server shouldn't 500 the API request that
    triggered it; callers decide what to do when this returns False (e.g.
    still return a value the admin can share manually).
    """
    if not is_configured():
        log.warning("SMTP not configured — skipping email to %s (%s)", to_email, subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(text_body or _strip_tags(html_body))
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - email delivery must never take the request down
        log.exception("failed to send email to %s", to_email)
        return False


def _strip_tags(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html)


# ---------------------------------------------------------------- templates

def send_invite_email(to_email: str, name: str, org_name: str, set_password_url: str) -> bool:
    subject = f"You've been added to {org_name} on LedgerCRM"
    html = f"""
    <p>Hi {name},</p>
    <p>You've been added to <strong>{org_name}</strong>'s workspace on LedgerCRM.</p>
    <p><a href="{set_password_url}">Set your password</a> to get started. This link expires in 7 days.</p>
    <p>If you weren't expecting this, you can ignore this email.</p>
    """
    return send_email(to_email, subject, html)


def send_password_reset_email(to_email: str, name: str, reset_url: str) -> bool:
    subject = "Reset your LedgerCRM password"
    html = f"""
    <p>Hi {name},</p>
    <p>We received a request to reset your LedgerCRM password.</p>
    <p><a href="{reset_url}">Reset your password</a>. This link expires in 1 hour.</p>
    <p>If you didn't request this, you can safely ignore this email — your password won't change.</p>
    """
    return send_email(to_email, subject, html)
