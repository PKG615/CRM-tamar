"""
Tests run against SQLite by default (fast, no setup). To run them against a
real Postgres instead:

    TEST_DATABASE_URL=postgresql+psycopg2://user:pw@localhost/crm_test pytest

The schema is created from the models for each test and dropped afterwards.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_default = f"sqlite:///{tempfile.gettempdir()}/crm_pytest.db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _default)
os.environ["SECRET_KEY"] = "test-secret"
os.environ["AUDIT_DELAY_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.rate_limit import limiter
from app.main import app
from app.models import Base, Lead, User


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


class Org:
    """A registered organization with an admin token and helpers."""

    def __init__(self, client, name):
        self.client = client
        self.slug = name.lower().replace(" ", "-")
        r = client.post("/api/auth/register", json={
            "organization_name": name, "admin_name": f"{name} Admin",
            "admin_email": f"admin@{self.slug}.com", "admin_password": "password123",
        })
        assert r.status_code == 200, r.text
        self.admin = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = client.get("/api/users/me", headers=self.admin).json()
        self.admin_id, self.org_id = me["id"], None
        with SessionLocal() as db:
            self.org_id = db.query(User).filter(User.id == self.admin_id).one().organization_id

    def add_user(self, role, name=None):
        name = name or role.title()
        email = f"admin2@{self.slug}.com" if role == "ADMIN" else f"{role.lower()}@{self.slug}.com"
        r = self.client.post("/api/users", headers=self.admin, json={
            "name": name, "email": email, "role": role, "password": "password123"})
        assert r.status_code == 201, r.text
        login = self.client.post("/api/auth/login", json={
            "organization_slug": self.slug, "email": email, "password": "password123"})
        assert login.status_code == 200, login.text
        return r.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}

    def make_lead(self, name="Acme Cafe", website="example.com", **kw):
        """phone/email/etc. all have defaults but can be overridden via kw
        (e.g. make_lead("X", phone=None) for a lead with no phone)."""
        defaults = {"phone": "+91 98765 43210", "lead_score": 0}
        defaults.update(kw)
        with SessionLocal() as db:
            lead = Lead(organization_id=self.org_id, business_name=name, website=website, **defaults)
            db.add(lead)
            db.commit()
            return lead.id


@pytest.fixture
def org_a(client):
    return Org(client, "Alpha Co")


@pytest.fixture
def org_b(client):
    return Org(client, "Beta Co")
