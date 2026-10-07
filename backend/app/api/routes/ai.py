from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Lead, WebsiteAudit, Pitch, Followup, User
from app.services import scoring_service, ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_lead_or_404(db: Session, lead_id: str, user: User) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == user.organization_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _latest_audit(db: Session, lead_id: str) -> WebsiteAudit | None:
    return (
        db.query(WebsiteAudit)
        .filter(WebsiteAudit.lead_id == lead_id)
        .order_by(WebsiteAudit.created_at.desc())
        .first()
    )


class LeadScoreRequest(BaseModel):
    lead_id: str


@router.post("/lead-score")
def ai_lead_score(payload: LeadScoreRequest, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    lead = _get_lead_or_404(db, payload.lead_id, user)
    score = scoring_service.recalculate_lead(db, lead)
    db.commit()
    return {
        "lead_score": score,
        "opportunity_level": lead.opportunity_level,
        "estimated_value_min": float(lead.estimated_deal_value_min),
        "estimated_value_max": float(lead.estimated_deal_value_max),
    }


class SalesRecommendationRequest(BaseModel):
    lead_id: str


@router.post("/sales-recommendation")
def ai_sales_recommendation(payload: SalesRecommendationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = _get_lead_or_404(db, payload.lead_id, user)
    audit = _latest_audit(db, lead.id)
    return ai_service.generate_sales_recommendation(lead, audit)


class FollowupSuggestionRequest(BaseModel):
    lead_id: str


@router.post("/followup")
def ai_followup_suggestion(payload: FollowupSuggestionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = _get_lead_or_404(db, payload.lead_id, user)
    audit = _latest_audit(db, lead.id)
    rec = ai_service.generate_sales_recommendation(lead, audit)
    return {
        "suggested_next_action": rec.get("suggested_next_action"),
        "suggested_followup_timing": rec.get("suggested_followup_timing"),
    }


class SummarizeLeadRequest(BaseModel):
    lead_id: str


@router.post("/summarize-lead")
def ai_summarize_lead(payload: SummarizeLeadRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = _get_lead_or_404(db, payload.lead_id, user)
    audit = _latest_audit(db, lead.id)
    context = {
        "business_name": lead.business_name, "category": lead.category, "city": lead.city,
        "status": lead.status.value, "lead_score": lead.lead_score,
        "website_score": lead.website_score,
        "audit_overall": audit.overall_score if audit else None,
    }
    summary = ai_service.ask_sales_assistant("Summarize this lead and why it's a good opportunity.", context)
    return {"summary": summary}


class AssistantRequest(BaseModel):
    question: str


@router.post("/assistant")
def ai_assistant(payload: AssistantRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    requirement #15. Pulls a bounded snapshot of real CRM data for this org
    (never the whole DB) and lets the model reason over ONLY that — it
    cannot hallucinate leads that aren't in `context_data`.
    """
    leads = (
        db.query(Lead)
        .filter(Lead.organization_id == user.organization_id, Lead.is_deleted.is_(False))
        .order_by(Lead.lead_score.desc())
        .limit(100)
        .all()
    )
    context_data = {
        "leads": [
            {
                "id": l.id, "business_name": l.business_name, "status": l.status.value,
                "lead_score": l.lead_score, "website_score": l.website_score,
                "next_followup_date": l.next_followup_date, "assigned_to": l.assigned_to,
            }
            for l in leads
        ]
    }
    answer = ai_service.ask_sales_assistant(payload.question, context_data)
    return {"answer": answer}
