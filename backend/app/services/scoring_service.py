from sqlalchemy.orm import Session

from app.models import Activity, ActivityType, Lead, LeadStatus, Pitch, PitchStatus, Settings, WebsiteAudit

DEFAULT_WEIGHTS = {
    "website_unavailable": 20,
    "poor_website_score": 15,
    "poor_mobile_score": 10,
    "poor_seo_score": 10,
    "poor_content_score": 8,
    "phone_available": 10,
    "email_available": 5,
    "whatsapp_reply": 25,
    "customer_interested": 20,
    "has_previous_activity": 5,
}

POOR_SCORE_THRESHOLD = 50  # website/mobile/seo score below this counts as "poor"


def get_scoring_weights(db: Session, organization_id: str) -> dict:
    """
    Per-org override lives in Settings(key='lead_scoring_weights'). Falls
    back to DEFAULT_WEIGHTS so a brand-new org works out of the box, but
    admins can tune every weight from Settings without a deploy.
    """
    row = (
        db.query(Settings)
        .filter(Settings.organization_id == organization_id, Settings.key == "lead_scoring_weights")
        .first()
    )
    if row and isinstance(row.value, dict):
        merged = DEFAULT_WEIGHTS.copy()
        merged.update(row.value)
        return merged
    return DEFAULT_WEIGHTS


def calculate_lead_score(
    db: Session,
    lead: Lead,
    latest_audit: WebsiteAudit | None,
    has_replied: bool = False,
    is_interested: bool = False,
    has_previous_activity: bool = False,
) -> int:
    """
    Returns 0-100. Pure function of (lead, audit, activity signals) and
    the org's configured weights — recompute any time inputs change
    (new audit, new reply, status change), never store stale logic.
    """
    w = get_scoring_weights(db, lead.organization_id)
    score = 0

    if not lead.website:
        score += w["website_unavailable"]
    elif latest_audit:
        if latest_audit.overall_score is not None and latest_audit.overall_score < POOR_SCORE_THRESHOLD:
            score += w["poor_website_score"]
        if latest_audit.mobile_score is not None and latest_audit.mobile_score < POOR_SCORE_THRESHOLD:
            score += w["poor_mobile_score"]
        if latest_audit.seo_score is not None and latest_audit.seo_score < POOR_SCORE_THRESHOLD:
            score += w["poor_seo_score"]
        if latest_audit.content_score is not None and latest_audit.content_score < POOR_SCORE_THRESHOLD:
            score += w["poor_content_score"]

    if lead.phone:
        score += w["phone_available"]
    if lead.email:
        score += w["email_available"]
    if has_replied:
        score += w["whatsapp_reply"]
    if is_interested:
        score += w["customer_interested"]
    if has_previous_activity:
        score += w["has_previous_activity"]

    return max(0, min(100, score))


def opportunity_level_for_score(db: Session, organization_id: str, score: int) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def estimated_value_range(db: Session, organization_id: str, opportunity_level: str) -> tuple[float, float]:
    """
    Per-org configurable via Settings(key='opportunity_value_ranges'),
    e.g. {"LOW": [10000, 50000], "MEDIUM": [50000, 150000], "HIGH": [150000, 500000]}.
    Requirement #7: "should be configurable and should NOT be hard-coded."
    """
    defaults = {"LOW": [10000, 50000], "MEDIUM": [50000, 150000], "HIGH": [150000, 500000]}
    row = (
        db.query(Settings)
        .filter(Settings.organization_id == organization_id, Settings.key == "opportunity_value_ranges")
        .first()
    )
    ranges = row.value if (row and isinstance(row.value, dict)) else defaults
    lo, hi = ranges.get(opportunity_level, defaults[opportunity_level])
    return float(lo), float(hi)


_INTERESTED_STATUSES = (
    LeadStatus.INTERESTED, LeadStatus.MEETING, LeadStatus.PROPOSAL, LeadStatus.NEGOTIATION, LeadStatus.WON,
)
_OUTREACH_ACTIVITIES = (
    ActivityType.CALL, ActivityType.EMAIL, ActivityType.MEETING, ActivityType.NOTE, ActivityType.WHATSAPP_SENT,
)


def recalculate_lead(db: Session, lead: Lead) -> int:
    """
    The one place a lead's score, opportunity level and estimated value get
    recomputed. Called after an audit, or on demand from the UI. Deriving all
    signals here (not at each call site) means running an audit can't
    silently drop, say, the bonus for a lead that already replied on WhatsApp.
    """
    audit = (
        db.query(WebsiteAudit)
        .filter(WebsiteAudit.lead_id == lead.id)
        .order_by(WebsiteAudit.created_at.desc())
        .first()
    )
    has_replied = (
        db.query(Pitch.id).filter(Pitch.lead_id == lead.id, Pitch.status == PitchStatus.REPLIED).first()
        is not None
        or db.query(Activity.id).filter(
            Activity.lead_id == lead.id, Activity.type == ActivityType.WHATSAPP_REPLY
        ).first() is not None
    )
    has_previous_activity = db.query(Activity.id).filter(
        Activity.lead_id == lead.id, Activity.type.in_(_OUTREACH_ACTIVITIES)
    ).first() is not None

    score = calculate_lead_score(
        db, lead, audit,
        has_replied=has_replied,
        is_interested=lead.status in _INTERESTED_STATUSES,
        has_previous_activity=has_previous_activity,
    )
    level = opportunity_level_for_score(db, lead.organization_id, score)
    lo, hi = estimated_value_range(db, lead.organization_id, level)

    lead.lead_score = score
    lead.opportunity_level = level
    lead.estimated_deal_value_min = lo
    lead.estimated_deal_value_max = hi
    if audit:
        lead.website_score = audit.overall_score
    return score
