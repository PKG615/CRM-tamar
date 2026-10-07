import csv
import io


def _rows(response):
    return list(csv.reader(io.StringIO(response.text)))


def test_leads_export_contains_expected_rows(org_a):
    org_a.make_lead("Acme Cafe", "acme.com", city="Pune", lead_score=72)
    org_a.make_lead("Beta Biz", "beta.com", city="Mumbai", lead_score=40)

    r = org_a.client.get("/api/leads/export.csv", headers=org_a.admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "leads.csv" in r.headers["content-disposition"]

    rows = _rows(r)
    assert rows[0][0] == "Business Name"
    names = [row[0] for row in rows[1:]]
    assert set(names) == {"Acme Cafe", "Beta Biz"}


def test_leads_export_respects_filters(org_a):
    org_a.make_lead("Pune Cafe", "a.com", city="Pune")
    org_a.make_lead("Mumbai Cafe", "b.com", city="Mumbai")

    r = org_a.client.get("/api/leads/export.csv", headers=org_a.admin, params={"city": "Pune"})
    rows = _rows(r)
    names = [row[0] for row in rows[1:]]
    assert names == ["Pune Cafe"]


def test_leads_export_is_tenant_scoped(org_a, org_b):
    org_a.make_lead("Mine", "mine.com")
    org_b.make_lead("Theirs", "theirs.com")

    r = org_a.client.get("/api/leads/export.csv", headers=org_a.admin)
    names = [row[0] for row in _rows(r)[1:]]
    assert names == ["Mine"]


def test_deals_export_contains_expected_columns(org_a):
    lead_id = org_a.make_lead("Acme Cafe")
    org_a.client.post("/api/deals", headers=org_a.admin, json={
        "lead_id": lead_id, "name": "Website redesign", "amount": 50000, "stage": "NEW",
    })

    r = org_a.client.get("/api/deals/export.csv", headers=org_a.admin)
    assert r.status_code == 200
    rows = _rows(r)
    assert rows[0][0] == "Deal Name"
    assert rows[1][0] == "Website redesign"
    assert rows[1][2] == "50000.00" or rows[1][2] == "50000"  # Decimal formatting is DB-dependent


def test_exports_require_auth(org_a):
    r = org_a.client.get("/api/leads/export.csv")
    assert r.status_code == 401
