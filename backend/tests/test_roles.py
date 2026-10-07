"""Role gating: viewers are read-only, executives sell, managers configure, admins manage users."""
import pytest


@pytest.fixture
def team(org_a):
    ids = {}
    heads = {"ADMIN": org_a.admin}
    for role in ("SALES_MANAGER", "SALES_EXECUTIVE", "VIEWER"):
        ids[role], heads[role] = org_a.add_user(role)
    return org_a, ids, heads


def test_viewer_can_read_but_not_write(team):
    org, _, h = team
    lead_id = org.make_lead()
    c = org.client
    for path in ("/api/leads", "/api/pipeline", "/api/dashboard", "/api/deals", "/api/followups",
                 "/api/proposals", "/api/customers", f"/api/leads/{lead_id}", "/api/jobs"):
        assert c.get(path, headers=h["VIEWER"]).status_code == 200, path

    v = h["VIEWER"]
    writes = [
        ("post", "/api/deals", {"lead_id": lead_id, "name": "x"}),
        ("put", f"/api/pipeline/{lead_id}", {"new_status": "CONTACTED"}),
        ("post", "/api/followups", {"lead_id": lead_id, "assigned_to": "x", "due_date": "2030-01-01"}),
        ("post", f"/api/leads/{lead_id}/activities", {"lead_id": lead_id, "type": "NOTE"}),
        ("post", f"/api/leads/{lead_id}/audit", None),
        ("post", f"/api/leads/{lead_id}/pitch", None),
        ("post", "/api/customers/convert", {"lead_id": lead_id}),
        ("post", "/api/ai/lead-score", {"lead_id": lead_id}),
        ("post", "/api/leads/bulk-audit", {}),
        ("post", "/api/leads/discover", {"query": "cafe"}),
    ]
    for method, path, body in writes:
        r = getattr(c, method)(path, headers=v, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (method, path, r.status_code, r.text)


def test_executive_can_sell_but_not_manage(team):
    org, ids, h = team
    lead_id = org.make_lead()
    c, ex = org.client, h["SALES_EXECUTIVE"]

    r = c.post("/api/deals", headers=ex, json={"lead_id": lead_id, "name": "Website", "amount": 5000})
    assert r.status_code == 200, r.text
    assert c.put(f"/api/pipeline/{lead_id}", headers=ex, json={"new_status": "CONTACTED"}).status_code == 200

    # manager-only
    assert c.put(f"/api/leads/{lead_id}/assign", headers=ex, json={"assigned_to": ids["SALES_EXECUTIVE"]}).status_code == 403
    assert c.put("/api/settings", headers=ex, json={"lead_scoring_weights": {"phone_available": 1}}).status_code == 403
    assert c.post("/api/settings/pipeline-stages", headers=ex, json={"name": "X", "order": 99}).status_code == 403
    # admin-only
    assert c.get("/api/users", headers=ex).status_code == 403
    assert c.post("/api/users", headers=ex, json={"name": "n", "email": "n@x.com", "password": "password123"}).status_code == 403


def test_manager_configures_but_cannot_manage_users(team):
    org, ids, h = team
    lead_id = org.make_lead()
    c, mg = org.client, h["SALES_MANAGER"]
    assert c.put(f"/api/leads/{lead_id}/assign", headers=mg, json={"assigned_to": ids["SALES_EXECUTIVE"]}).status_code == 200
    assert c.put("/api/settings", headers=mg, json={"lead_scoring_weights": {"phone_available": 12}}).status_code == 200
    assert c.get("/api/users", headers=mg).status_code == 200      # can view the team
    assert c.post("/api/users", headers=mg, json={"name": "n", "email": "n@x.com", "password": "password123"}).status_code == 403
    assert c.put(f"/api/users/{ids['VIEWER']}", headers=mg, json={"role": "ADMIN"}).status_code == 403


def test_unauthenticated_requests_rejected(client):
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/health").status_code == 200
