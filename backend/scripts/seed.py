"""
Run once against a fresh DB (after `alembic upgrade head`) to get a working
demo tenant: python scripts/seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Organization, User, UserRole, PipelineStage, Lead, LeadStatus, Settings

DEFAULT_STAGES = ["NEW", "CONTACTED", "REPLIED", "INTERESTED", "MEETING",
                   "PROPOSAL", "NEGOTIATION", "WON", "LOST"]


def main():
    db = SessionLocal()
    try:
        org = Organization(name="Demo Agency", slug="demo-agency")
        db.add(org)
        db.flush()

        admin = User(
            organization_id=org.id, name="Demo Admin", email="admin@demo.com",
            hashed_password=hash_password("admin123"), role=UserRole.ADMIN,
        )
        db.add(admin)

        for i, stage in enumerate(DEFAULT_STAGES):
            db.add(PipelineStage(organization_id=org.id, name=stage, order=i,
                                  is_won_stage=1 if stage == "WON" else 0,
                                  is_lost_stage=1 if stage == "LOST" else 0))

        db.add(Settings(organization_id=org.id, key="lead_scoring_weights", value={
            "website_unavailable": 20, "poor_website_score": 15, "phone_available": 10,
            "whatsapp_reply": 25, "customer_interested": 20,
        }))
        db.add(Settings(organization_id=org.id, key="opportunity_value_ranges", value={
            "LOW": [10000, 50000], "MEDIUM": [50000, 150000], "HIGH": [150000, 500000],
        }))

        db.add(Lead(
            organization_id=org.id, business_name="Sharma Electricals",
            category="Electronics Store", phone="+91 98765 43210",
            city="Gurugram", state="Haryana", country="India",
            website=None, lead_score=0, status=LeadStatus.NEW,
        ))
        db.add(Lead(
            organization_id=org.id, business_name="Green Leaf Cafe",
            category="Restaurant", phone="+91 98111 22333", website="https://greenleafcafe.example",
            city="Gurugram", state="Haryana", country="India",
            lead_score=0, status=LeadStatus.CONTACTED,
        ))

        db.commit()
        print(f"Seeded org '{org.slug}' — login with admin@demo.com / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
