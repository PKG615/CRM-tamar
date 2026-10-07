from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Pitch, PitchStatus, PitchChannel, Lead, WebsiteAudit, User, ActivityType, Settings
from app.services.ai_service import generate_whatsapp_pitch
from app.services.activity_service import log_activity
from app.services.whatsapp_service import send_whatsapp_message, send_whatsapp_template, WhatsAppError

router = APIRouter(prefix="/api/leads", tags=["pitches"])


@router.get("/{lead_id}/pitches")
def list_pitches(lead_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Pitch)
        .filter(Pitch.organization_id == user.organization_id, Pitch.lead_id == lead_id)
        .order_by(Pitch.created_at.desc())
        .all()
    )


@router.post("/{lead_id}/pitch")
def generate_pitch(lead_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """
    [Generate Pitch] button. Reuses the one AI pitch implementation
    (app/services/ai_service.py) — no second pitch system (requirement #8).
    Every generated pitch is stored, sent or not.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == user.organization_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    latest_audit = (
        db.query(WebsiteAudit)
        .filter(WebsiteAudit.lead_id == lead_id)
        .order_by(WebsiteAudit.created_at.desc())
        .first()
    )

    lang_row = db.query(Settings).filter(
        Settings.organization_id == user.organization_id, Settings.key == "outreach_language"
    ).first()
    message = generate_whatsapp_pitch(lead, latest_audit, language=(lang_row.value if lang_row else "en"))

    pitch = Pitch(
        organization_id=user.organization_id,
        lead_id=lead_id,
        generated_by=user.id,
        message=message,
        channel=PitchChannel.WHATSAPP,
        status=PitchStatus.DRAFT,
    )
    db.add(pitch)
    db.flush()
    log_activity(db, user.organization_id, lead_id, ActivityType.PITCH_GENERATED, user_id=user.id)
    db.commit()
    db.refresh(pitch)
    return pitch


class PitchEdit(BaseModel):
    message: str


@router.put("/{lead_id}/pitch/{pitch_id}")
def edit_pitch(lead_id: str, pitch_id: str, payload: PitchEdit, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    pitch = db.query(Pitch).filter(
        Pitch.id == pitch_id, Pitch.lead_id == lead_id, Pitch.organization_id == user.organization_id
    ).first()
    if not pitch:
        raise HTTPException(status_code=404, detail="Pitch not found")
    if pitch.status != PitchStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft pitches can be edited")
    pitch.message = payload.message
    db.commit()
    db.refresh(pitch)
    return pitch


@router.post("/{lead_id}/pitch/{pitch_id}/send")
def send_pitch(lead_id: str, pitch_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """
    Sends via the WhatsApp Business Cloud API (app/services/whatsapp_service.py).
    If WHATSAPP_API_TOKEN isn't configured, or the number is unreachable,
    the pitch is marked FAILED (not silently left as DRAFT) so the rep
    sees it needs attention rather than assuming it went out.
    """
    pitch = db.query(Pitch).filter(
        Pitch.id == pitch_id, Pitch.lead_id == lead_id, Pitch.organization_id == user.organization_id
    ).first()
    if not pitch:
        raise HTTPException(status_code=404, detail="Pitch not found")

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == user.organization_id).first()
    if not lead or not lead.phone:
        raise HTTPException(status_code=400, detail="This lead has no phone number to send WhatsApp to")

    # Meta only allows free-form text within an open 24h customer-service
    # window. A lead with no prior sent/delivered/read/replied pitch has
    # never had that window opened, so it's cold first-touch outreach and
    # needs a pre-approved template instead — otherwise Meta rejects the send.
    has_prior_contact = db.query(Pitch.id).filter(
        Pitch.lead_id == lead_id,
        Pitch.id != pitch.id,
        Pitch.status.in_([PitchStatus.SENT, PitchStatus.DELIVERED, PitchStatus.READ, PitchStatus.REPLIED]),
    ).first() is not None

    used_template = False
    if not has_prior_contact and settings.WHATSAPP_TEMPLATE_NAME:
        try:
            result = send_whatsapp_template(
                lead.phone, settings.WHATSAPP_TEMPLATE_NAME, body_params=[lead.business_name],
            )
            used_template = True
        except WhatsAppError as e:
            pitch.status = PitchStatus.FAILED
            db.commit()
            raise HTTPException(status_code=502, detail=str(e))
    else:
        try:
            result = send_whatsapp_message(lead.phone, pitch.message)
        except WhatsAppError as e:
            pitch.status = PitchStatus.FAILED
            db.commit()
            # Cold lead + no template configured is the single most common cause
            # of this failure, so say so rather than just relaying Meta's error.
            hint = (
                " This looks like first-touch outreach to a lead who has never "
                "replied — Meta requires a pre-approved template for that. Set "
                "WHATSAPP_TEMPLATE_NAME once one is approved in Meta Business Manager."
                if not has_prior_contact and not settings.WHATSAPP_TEMPLATE_NAME else ""
            )
            raise HTTPException(status_code=502, detail=str(e) + hint)

    pitch.status = PitchStatus.SENT
    pitch.sent_at = datetime.utcnow()
    db.flush()
    log_activity(
        db, user.organization_id, lead_id, ActivityType.WHATSAPP_SENT,
        description=f"WhatsApp {'template' if used_template else 'message'} sent — ID: {result.get('message_id', 'unknown')}",
        user_id=user.id,
    )
    db.commit()
    db.refresh(pitch)
    return pitch
