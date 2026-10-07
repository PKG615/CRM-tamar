from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_writer
from app.models import Deal, DealStage, User, ActivityType
from app.schemas.crm import DealCreate, DealUpdate
from app.services.activity_service import log_activity
from app.services.notification_service import notify
from app.services.audit_log_service import record as audit_record
from app.models import NotificationType
from app.core.tenancy import get_org_lead, ensure_org_user

router = APIRouter(prefix="/api/deals", tags=["deals"])


@router.get("")
def list_deals(lead_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Deal).filter(Deal.organization_id == user.organization_id)
    if lead_id:
        q = q.filter(Deal.lead_id == lead_id)
    return q.order_by(Deal.created_at.desc()).all()


@router.post("")
def create_deal(payload: DealCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    get_org_lead(db, user.organization_id, payload.lead_id)
    ensure_org_user(db, user.organization_id, payload.sales_owner)
    deal = Deal(organization_id=user.organization_id, **payload.model_dump())
    db.add(deal)
    db.flush()
    log_activity(db, user.organization_id, payload.lead_id, ActivityType.DEAL_CREATED,
                 description=f"Deal '{payload.name}' created", user_id=user.id)
    db.commit()
    db.refresh(deal)
    return deal


@router.put("/{deal_id}")
def update_deal(deal_id: str, payload: DealUpdate, db: Session = Depends(get_db), user: User = Depends(require_writer)):
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.organization_id == user.organization_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    changes = payload.model_dump(exclude_unset=True)
    if "sales_owner" in changes:
        ensure_org_user(db, user.organization_id, changes["sales_owner"])
    old_stage = deal.stage
    for field, value in changes.items():
        setattr(deal, field, value)
    db.flush()

    if payload.stage and payload.stage != old_stage:
        new_stage = payload.stage
        if new_stage == DealStage.WON:
            log_activity(db, user.organization_id, deal.lead_id, ActivityType.DEAL_WON, user_id=user.id)
            audit_record(db, user.organization_id, user.id, "DEAL_WON", "Deal", deal.id,
                         changes={"amount": str(deal.amount)})
            if deal.sales_owner:
                notify(db, user.organization_id, deal.sales_owner, NotificationType.DEAL_WON,
                       f"Deal '{deal.name}' was won 🎉", link=f"/leads/{deal.lead_id}")
        elif new_stage == DealStage.LOST:
            log_activity(db, user.organization_id, deal.lead_id, ActivityType.DEAL_LOST, user_id=user.id)
            audit_record(db, user.organization_id, user.id, "DEAL_LOST", "Deal", deal.id)
            if deal.sales_owner:
                notify(db, user.organization_id, deal.sales_owner, NotificationType.DEAL_LOST,
                       f"Deal '{deal.name}' was marked lost", link=f"/leads/{deal.lead_id}")
        else:
            log_activity(db, user.organization_id, deal.lead_id, ActivityType.STATUS_CHANGED,
                         description=f"Deal stage: {old_stage.value} → {new_stage.value}", user_id=user.id)

    db.commit()
    db.refresh(deal)
    return deal
