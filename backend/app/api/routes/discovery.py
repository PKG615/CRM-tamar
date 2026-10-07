from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Lead, User, ActivityType
from app.services.google_maps_service import discover_leads, GoogleMapsError
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/leads", tags=["discovery"])


class DiscoverRequest(BaseModel):
    query: str                # e.g. "electronics store"
    city: str | None = None
    state: str | None = None
    country: str | None = None
    max_results: int = 20


@router.post("/discover")
def discover(payload: DiscoverRequest, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    """
    [Search Leads] button. Calls Google Places, then inserts only leads
    whose google_place_id isn't already in this org (requirement: never
    create duplicate leads from repeated searches over the same area).
    """
    try:
        candidates = discover_leads(
            payload.query, city=payload.city, state=payload.state, country=payload.country,
            max_results=payload.max_results,
        )
    except GoogleMapsError as e:
        raise HTTPException(status_code=502, detail=str(e))

    existing_place_ids = {
        row[0] for row in db.query(Lead.google_place_id).filter(
            Lead.organization_id == user.organization_id,
            Lead.google_place_id.isnot(None),
        ).all()
    }

    created = []
    skipped = 0
    for c in candidates:
        if c["google_place_id"] and c["google_place_id"] in existing_place_ids:
            skipped += 1
            continue
        lead = Lead(organization_id=user.organization_id, lead_score=0, **c)
        db.add(lead)
        db.flush()
        log_activity(db, user.organization_id, lead.id, ActivityType.LEAD_CREATED,
                     description=f"Discovered via Google Maps search: '{payload.query}'", user_id=user.id)
        created.append(lead)
        if c["google_place_id"]:
            existing_place_ids.add(c["google_place_id"])

    db.commit()
    for lead in created:
        db.refresh(lead)

    return {"created": created, "created_count": len(created), "skipped_duplicates": skipped}


@router.get("/discover/status")
def discovery_status(user: User = Depends(get_current_user)):
    """Lets the frontend show a setup banner if the API key isn't configured yet."""
    return {"google_maps_configured": bool(settings.GOOGLE_MAPS_API_KEY)}
