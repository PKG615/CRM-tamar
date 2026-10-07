import json
from typing import Optional

import anthropic

from app.core.config import settings
from app.models import Lead, WebsiteAudit

_client: Optional[anthropic.Anthropic] = None

# Kept here (not in settings.py) since this is the one place that actually
# needs the display name for a prompt; settings.py's SUPPORTED_OUTREACH_LANGUAGES
# is the source of truth for which codes are valid — keep the key sets in sync.
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi"}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def generate_whatsapp_pitch(lead: Lead, audit: Optional[WebsiteAudit], language: str = "en") -> str:
    """
    Reuses the SAME AI pitch feature the lead-gen platform already has
    (requirement #8) — this is that one implementation; the CRM's
    [Generate Pitch] button calls this, it does not duplicate it.

    `language` is the org's Settings(key="outreach_language") value (see
    app/api/routes/settings.py) — leads in a Hindi-speaking market get a
    Hindi pitch without the rep having to translate it by hand.
    """
    language_name = LANGUAGE_NAMES.get(language, "English")
    audit_summary = "No website audit available." if not audit else (
        f"Website audit — overall {audit.overall_score}/100, "
        f"SEO {audit.seo_score}, mobile {audit.mobile_score}, "
        f"performance {audit.performance_score}."
    )

    prompt = f"""Write a short, personalized WhatsApp outreach message in {language_name} (in a friendly,
professional tone, max 4 sentences) to a business owner, based on:

Business: {lead.business_name}
Category: {lead.category or "unknown"}
City: {lead.city or "unknown"}
{audit_summary}

The message should introduce our digital services and reference a specific,
genuine improvement opportunity from the audit (if available) without being
pushy. End with a soft call to action (e.g. a quick call). Do not use emojis
excessively. Write the entire message in {language_name}. Output ONLY the
message text, nothing else — no translation, no English alongside it."""

    client = _get_client()
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def generate_sales_recommendation(lead: Lead, audit: Optional[WebsiteAudit]) -> dict:
    """
    Returns recommended_services, talking_points, next_action, followup_timing
    (requirement #7). Structured output via JSON-only prompting.
    """
    audit_summary = "No audit available." if not audit else json.dumps({
        "overall": audit.overall_score, "seo": audit.seo_score,
        "mobile": audit.mobile_score, "performance": audit.performance_score,
        "security": audit.security_score,
    })

    prompt = f"""You are a B2B sales strategist. Based on this lead, respond with ONLY a
JSON object (no markdown, no preamble) with keys:
"recommended_services" (list of strings, from: Website Redesign, SEO, AI Chatbot,
WhatsApp Automation, CRM, Digital Marketing),
"sales_talking_points" (list of 3 short strings),
"suggested_next_action" (string),
"suggested_followup_timing" (string, e.g. "within 2 days").

Lead: {lead.business_name}, category {lead.category}, city {lead.city}.
Audit: {audit_summary}"""

    client = _get_client()
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "recommended_services": [],
            "sales_talking_points": [],
            "suggested_next_action": "Review manually — AI response could not be parsed.",
            "suggested_followup_timing": "within 2 days",
        }


def ask_sales_assistant(question: str, context_data: dict) -> str:
    """
    requirement #15: answers questions using ACTUAL CRM data passed in
    `context_data` (already queried from the DB by the caller) — the model
    never invents lead facts, it only reasons over what's given.
    """
    prompt = f"""You are a sales assistant for a CRM. Answer the user's question using
ONLY the data provided below. If the data doesn't contain the answer, say so
plainly instead of guessing.

CRM DATA:
{json.dumps(context_data, default=str)[:8000]}

QUESTION: {question}

Answer concisely."""

    client = _get_client()
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
