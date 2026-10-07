def test_admin_creates_user_who_can_log_in_and_change_password(org_a):
    c = org_a.client
    uid, h = org_a.add_user("SALES_EXECUTIVE", "Ravi")
    me = c.get("/api/users/me", headers=h).json()
    assert me["name"] == "Ravi" and me["role"] == "SALES_EXECUTIVE"

    assert c.post("/api/users/me/password", headers=h,
                  json={"current_password": "wrong-one", "new_password": "newpassword1"}).status_code == 400
    assert c.post("/api/users/me/password", headers=h,
                  json={"current_password": "password123", "new_password": "newpassword1"}).status_code == 200
    ok = c.post("/api/auth/login", json={"organization_slug": org_a.slug,
                                          "email": "sales_executive@alpha-co.com", "password": "newpassword1"})
    assert ok.status_code == 200
    old = c.post("/api/auth/login", json={"organization_slug": org_a.slug,
                                           "email": "sales_executive@alpha-co.com", "password": "password123"})
    assert old.status_code == 401


def test_duplicate_email_and_weak_password_rejected(org_a):
    c = org_a.client
    org_a.add_user("VIEWER")
    dup = c.post("/api/users", headers=org_a.admin, json={
        "name": "Again", "email": "VIEWER@alpha-co.com", "role": "VIEWER", "password": "password123"})
    assert dup.status_code == 400                      # emails are case-insensitive
    short = c.post("/api/users", headers=org_a.admin, json={
        "name": "S", "email": "s@alpha-co.com", "role": "VIEWER", "password": "short"})
    assert short.status_code == 422
    bad_role = c.post("/api/users", headers=org_a.admin, json={
        "name": "S", "email": "s@alpha-co.com", "role": "SUPERUSER", "password": "password123"})
    assert bad_role.status_code == 422


def test_deactivated_user_is_locked_out_immediately(org_a):
    c = org_a.client
    uid, h = org_a.add_user("SALES_EXECUTIVE")
    assert c.get("/api/leads", headers=h).status_code == 200
    assert c.put(f"/api/users/{uid}", headers=org_a.admin, json={"is_active": False}).status_code == 200
    assert c.get("/api/leads", headers=h).status_code == 403            # existing token stops working
    login = c.post("/api/auth/login", json={"organization_slug": org_a.slug,
                                             "email": "sales_executive@alpha-co.com", "password": "password123"})
    assert login.status_code == 403
    assert uid not in [u["id"] for u in c.get("/api/users/directory", headers=org_a.admin).json()]


def test_admin_cannot_lock_themselves_out_or_remove_last_admin(org_a):
    c = org_a.client
    assert c.put(f"/api/users/{org_a.admin_id}", headers=org_a.admin, json={"role": "VIEWER"}).status_code == 400
    assert c.put(f"/api/users/{org_a.admin_id}", headers=org_a.admin, json={"is_active": False}).status_code == 400

    # a second admin may demote the first, but never the last remaining admin
    second_id, second = org_a.add_user("ADMIN", "Second")
    assert c.put(f"/api/users/{org_a.admin_id}", headers=second, json={"role": "VIEWER"}).status_code == 200
    assert c.put(f"/api/users/{second_id}", headers=second, json={"role": "VIEWER"}).status_code == 400


def test_admin_reset_password_and_audit_trail(org_a):
    c = org_a.client
    uid, _ = org_a.add_user("VIEWER")
    assert c.post(f"/api/users/{uid}/reset-password", headers=org_a.admin,
                  json={"new_password": "brandnewpass1"}).status_code == 200
    assert c.post("/api/auth/login", json={"organization_slug": org_a.slug,
                                            "email": "viewer@alpha-co.com", "password": "brandnewpass1"}).status_code == 200
    from app.core.database import SessionLocal
    from app.models import AuditLog
    with SessionLocal() as db:
        actions = {a.action for a in db.query(AuditLog).all()}
    assert {"USER_CREATED", "USER_PASSWORD_RESET"} <= actions


def test_users_are_isolated_between_orgs(org_a, org_b):
    c = org_a.client
    b_id, _ = org_b.add_user("VIEWER")
    assert c.put(f"/api/users/{b_id}", headers=org_a.admin, json={"role": "ADMIN"}).status_code == 404
    assert c.post(f"/api/users/{b_id}/reset-password", headers=org_a.admin,
                  json={"new_password": "hijacked123"}).status_code == 404
    names = [u["email"] for u in c.get("/api/users", headers=org_a.admin).json()]
    assert all(e.endswith("@alpha-co.com") for e in names)
    # same email can exist in two orgs
    org_a.add_user("VIEWER")
