"""
Weekly digest email, sent to every org's ADMIN/SALES_MANAGER users.
Triggered by the worker once a week (see maybe_send_weekly_report in
app/worker.py) — not an API endpoint, since nobody requests this on
demand, it just needs to go out on a schedule.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Organization, User, UserRole, Lead, Deal, DealStage, Followup, FollowupStatus
from app.services import email_service


def _org_digest_stats(db: Session, organization_id: str, since: datetime) -> dict:
    new_leads = db.query(Lead).filter(
        Lead.organization_id == organization_id, Lead.created_at >= since, Lead.is_deleted.is_(False),
    ).count()

    won_deals = db.query(Deal).filter(
        Deal.organization_id == organization_id, Deal.stage == DealStage.WON, Deal.updated_at >= since,
    ).all()
    won_revenue = sum(float(d.amount or 0) for d in won_deals)

    overdue_followups = db.query(Followup).filter(
        Followup.organization_id == organization_id, Followup.status == FollowupStatus.PENDING,
        Followup.due_date < datetime.utcnow().date(),
    ).count()

    return {
        "new_leads": new_leads,
        "won_deals": len(won_deals),
        "won_revenue": won_revenue,
        "overdue_followups": overdue_followups,
    }


def _digest_html(org_name: str, stats: dict) -> str:
    return f"""
    <h2>Weekly digest — {org_name}</h2>
    <ul>
      <li><strong>{stats['new_leads']}</strong> new leads this week</li>
      <li><strong>{stats['won_deals']}</strong> deals won (₹{stats['won_revenue']:,.0f})</li>
      <li><strong>{stats['overdue_followups']}</strong> follow-ups currently overdue</li>
    </ul>
    <p>Log in to LedgerCRM for the full picture.</p>
    """


def send_weekly_digests(db: Session) -> dict:
    """
    Runs across every organization. Returns a summary dict for logging.
    Never raises for one bad org/email — a bounce for one tenant shouldn't
    stop every other tenant's digest.
    """
    since = datetime.utcnow() - timedelta(days=7)
    sent, skipped, failed = 0, 0, 0

    orgs = db.query(Organization).filter(Organization.is_active.is_(True)).all()
    for org in orgs:
        try:
            recipients = db.query(User).filter(
                User.organization_id == org.id, User.is_active.is_(True),
                User.role.in_([UserRole.ADMIN, UserRole.SALES_MANAGER]),
            ).all()
            if not recipients:
                skipped += 1
                continue

            stats = _org_digest_stats(db, org.id, since)
            html = _digest_html(org.name, stats)
            for user in recipients:
                if email_service.send_email(user.email, f"{org.name} — weekly digest", html):
                    sent += 1
                else:
                    failed += 1
        except Exception:  # noqa: BLE001 - one org's failure must not block the rest
            failed += 1

    return {"orgs": len(orgs), "emails_sent": sent, "orgs_skipped_no_recipient": skipped, "emails_failed": failed}
