from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models import Settings, PipelineStage, User
from app.services.scoring_service import DEFAULT_WEIGHTS

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_default(db: Session, org_id: str, key: str, default: dict) -> dict:
    row = db.query(Settings).filter(Settings.organization_id == org_id, Settings.key == key).first()
    return row.value if row else default


DEFAULT_RANGES = {"LOW": [10000, 50000], "MEDIUM": [50000, 150000], "HIGH": [150000, 500000]}

# ISO 639-1 codes the AI prompts know how to write in — see
# app/services/ai_service.py's LANGUAGE_NAMES. Kept as a plain list (not a
# dict) here since the UI just needs the codes to populate a dropdown.
SUPPORTED_OUTREACH_LANGUAGES = ["en", "hi"]


@router.get("")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    requirement #7/#16: scoring weights & opportunity ranges must be
    configurable, never hard-coded. This is where an admin edits them.
    """
    row = db.query(Settings).filter(Settings.organization_id == user.organization_id, Settings.key == "outreach_language").first()
    return {
        "lead_scoring_weights": _get_or_default(db, user.organization_id, "lead_scoring_weights", DEFAULT_WEIGHTS),
        "opportunity_value_ranges": _get_or_default(db, user.organization_id, "opportunity_value_ranges", DEFAULT_RANGES),
        "outreach_language": row.value if row else "en",
        "supported_outreach_languages": SUPPORTED_OUTREACH_LANGUAGES,
    }


class SettingsUpdate(BaseModel):
    lead_scoring_weights: dict | None = None
    opportunity_value_ranges: dict | None = None
    outreach_language: str | None = None


@router.put("")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if key == "outreach_language" and value not in SUPPORTED_OUTREACH_LANGUAGES:
            raise HTTPException(status_code=400, detail=f"Unsupported language '{value}'. Supported: {SUPPORTED_OUTREACH_LANGUAGES}")
        row = db.query(Settings).filter(Settings.organization_id == user.organization_id, Settings.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Settings(organization_id=user.organization_id, key=key, value=value))
    db.commit()
    return get_settings(db, user)


# ---------- Pipeline stages ----------

@router.get("/pipeline-stages")
def list_stages(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(PipelineStage)
        .filter(PipelineStage.organization_id == user.organization_id)
        .order_by(PipelineStage.order)
        .all()
    )


class StageCreate(BaseModel):
    name: str
    order: int
    is_won_stage: bool = False
    is_lost_stage: bool = False


@router.post("/pipeline-stages")
def create_stage(
    payload: StageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    stage = PipelineStage(
        organization_id=user.organization_id,
        name=payload.name,
        order=payload.order,
        is_won_stage=1 if payload.is_won_stage else 0,
        is_lost_stage=1 if payload.is_lost_stage else 0,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


class StageUpdate(BaseModel):
    name: str | None = None
    order: int | None = None


@router.put("/pipeline-stages/{stage_id}")
def update_stage(
    stage_id: str,
    payload: StageUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    stage = db.query(PipelineStage).filter(
        PipelineStage.id == stage_id, PipelineStage.organization_id == user.organization_id
    ).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    db.commit()
    db.refresh(stage)
    return stage


@router.delete("/pipeline-stages/{stage_id}")
def delete_stage(
    stage_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    stage = db.query(PipelineStage).filter(
        PipelineStage.id == stage_id, PipelineStage.organization_id == user.organization_id
    ).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    db.delete(stage)
    db.commit()
    return {"deleted": True}
