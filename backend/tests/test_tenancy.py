"""IDs in request bodies must belong to the caller's organization."""


def test_cannot_touch_another_orgs_lead(org_a, org_b):
    c = org_a.client
    foreign_lead = org_b.make_lead("Beta's lead")

    assert c.get(f"/api/leads/{foreign_lead}", headers=org_a.admin).status_code == 404
    assert c.post("/api/deals", headers=org_a.admin, json={"lead_id": foreign_lead, "name": "x"}).status_code == 404
    assert c.post("/api/followups", headers=org_a.admin, json={
        "lead_id": foreign_lead, "assigned_to": org_a.admin_id, "due_date": "2030-01-01"}).status_code == 404
    assert c.post(f"/api/leads/{foreign_lead}/activities", headers=org_a.admin,
                  json={"lead_id": foreign_lead, "type": "NOTE"}).status_code == 404
    assert c.put(f"/api/pipeline/{foreign_lead}", headers=org_a.admin, json={"new_status": "WON"}).status_code == 404
    assert c.post("/api/customers/convert", headers=org_a.admin, json={"lead_id": foreign_lead}).status_code == 404
    assert c.post(f"/api/leads/{foreign_lead}/audit", headers=org_a.admin).status_code == 404
    # nothing leaked into org B's timeline
    assert c.get(f"/api/leads/{foreign_lead}/activities", headers=org_b.admin).json() == []


def test_cannot_assign_work_to_another_orgs_user(org_a, org_b):
    c = org_a.client
    lead = org_a.make_lead()
    b_user, _ = org_b.add_user("SALES_EXECUTIVE")

    assert c.put(f"/api/leads/{lead}/assign", headers=org_a.admin, json={"assigned_to": b_user}).status_code == 400
    assert c.post("/api/leads/bulk-assign", headers=org_a.admin,
                  json={"lead_ids": [lead], "assigned_to": b_user}).status_code == 400
    assert c.post("/api/followups", headers=org_a.admin, json={
        "lead_id": lead, "assigned_to": b_user, "due_date": "2030-01-01"}).status_code == 400
    assert c.post("/api/deals", headers=org_a.admin, json={
        "lead_id": lead, "name": "x", "sales_owner": b_user}).status_code == 400
    deal = c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead, "name": "ok"}).json()
    assert c.put(f"/api/deals/{deal['id']}", headers=org_a.admin, json={"sales_owner": b_user}).status_code == 400


def test_lists_only_show_own_org(org_a, org_b):
    c = org_a.client
    org_a.make_lead("Mine")
    org_b.make_lead("Theirs")
    names = [l["business_name"] for l in c.get("/api/leads", headers=org_a.admin).json()["items"]]
    assert names == ["Mine"]
    assert c.get("/api/dashboard", headers=org_b.admin).json()["total_leads"] == 1


def test_proposal_lead_must_match_deal(org_a):
    c = org_a.client
    lead1, lead2 = org_a.make_lead("One"), org_a.make_lead("Two")
    deal = c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead1, "name": "d"}).json()
    item = {"service": "SEO", "quantity": 1, "unit_price": 100, "tax_percent": 18}
    bad = c.post("/api/proposals", headers=org_a.admin,
                 json={"deal_id": deal["id"], "lead_id": lead2, "line_items": [item]})
    assert bad.status_code == 400


def test_invalid_input_is_a_422_not_a_500(org_a):
    c = org_a.client
    lead = org_a.make_lead()
    assert c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead, "name": "x", "stage": "BOGUS"}).status_code == 422
    assert c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead, "name": "x", "probability": 150}).status_code == 422
    assert c.post(f"/api/leads/{lead}/activities", headers=org_a.admin,
                  json={"lead_id": lead, "type": "NOT_A_TYPE"}).status_code == 422
    deal = c.post("/api/deals", headers=org_a.admin, json={"lead_id": lead, "name": "x"}).json()
    assert c.post("/api/proposals", headers=org_a.admin, json={"deal_id": deal["id"], "lead_id": lead, "line_items": []}).status_code == 422
