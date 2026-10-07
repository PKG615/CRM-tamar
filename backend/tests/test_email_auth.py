"""
Email delivery is mocked (monkeypatched at the import site in each route
module) so these tests never touch a real SMTP server — they verify the
token/flow logic, not smtplib.
"""
import app.api.routes.auth as auth_routes
import app.api.routes.users as users_routes


def test_invite_without_smtp_returns_temporary_password(org_a, monkeypatch):
    monkeypatch.setattr(users_routes, "email_configured", lambda: False)
    c = org_a.client

    r = c.post("/api/users", headers=org_a.admin, json={
        "name": "Priya", "email": "priya@alpha-co.com", "role": "SALES_EXECUTIVE",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["invited_by_email"] is False
    assert body["temporary_password"]  # a real, usable password was generated

    login = c.post("/api/auth/login", json={
        "organization_slug": org_a.slug, "email": "priya@alpha-co.com",
        "password": body["temporary_password"],
    })
    assert login.status_code == 200


def test_invite_with_smtp_sends_email_and_hides_password(org_a, monkeypatch):
    sent = {}

    def fake_send_invite(to_email, name, org_name, url):
        sent["to"] = to_email
        sent["url"] = url
        return True

    monkeypatch.setattr(users_routes, "email_configured", lambda: True)
    monkeypatch.setattr(users_routes, "send_invite_email", fake_send_invite)
    c = org_a.client

    r = c.post("/api/users", headers=org_a.admin, json={
        "name": "Asha", "email": "asha@alpha-co.com", "role": "VIEWER",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["invited_by_email"] is True
    assert body["temporary_password"] is None
    assert sent["to"] == "asha@alpha-co.com"
    assert "/set-password?token=" in sent["url"]

    token = sent["url"].split("token=")[1].split("&")[0]
    set_pw = c.post("/api/auth/set-password", json={"token": token, "new_password": "brandnewpass1"})
    assert set_pw.status_code == 200
    assert "access_token" in set_pw.json()

    login = c.post("/api/auth/login", json={
        "organization_slug": org_a.slug, "email": "asha@alpha-co.com", "password": "brandnewpass1",
    })
    assert login.status_code == 200

    # the same invite link can't be replayed once the password has been set
    replay = c.post("/api/auth/set-password", json={"token": token, "new_password": "another123"})
    assert replay.status_code == 400


def test_invite_email_failure_falls_back_to_temporary_password(org_a, monkeypatch):
    monkeypatch.setattr(users_routes, "email_configured", lambda: True)
    monkeypatch.setattr(users_routes, "send_invite_email", lambda *a, **kw: False)  # SMTP server down
    c = org_a.client

    r = c.post("/api/users", headers=org_a.admin, json={
        "name": "Kabir", "email": "kabir@alpha-co.com", "role": "VIEWER",
    })
    body = r.json()
    assert body["invited_by_email"] is False
    assert body["temporary_password"]  # still recoverable even though the email attempt failed


def test_forgot_password_is_silent_about_account_existence(org_a, monkeypatch):
    monkeypatch.setattr(auth_routes, "email_configured", lambda: True)
    sent = []
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda *a, **kw: sent.append(a) or True)
    c = org_a.client

    known = c.post("/api/auth/forgot-password", json={
        "organization_slug": org_a.slug, "email": "admin@alpha-co.com"})
    unknown = c.post("/api/auth/forgot-password", json={
        "organization_slug": org_a.slug, "email": "nobody@alpha-co.com"})
    wrong_org = c.post("/api/auth/forgot-password", json={
        "organization_slug": "no-such-org", "email": "admin@alpha-co.com"})

    assert known.status_code == unknown.status_code == wrong_org.status_code == 200
    assert known.json() == unknown.json() == wrong_org.json()
    assert len(sent) == 1  # only the real account actually got an email


def test_forgot_password_reset_link_works_and_invalidates_old_password(org_a, monkeypatch):
    monkeypatch.setattr(auth_routes, "email_configured", lambda: True)
    captured = {}

    def fake_send_reset(to_email, name, url):
        captured["url"] = url
        return True

    monkeypatch.setattr(auth_routes, "send_password_reset_email", fake_send_reset)
    c = org_a.client

    c.post("/api/auth/forgot-password", json={"organization_slug": org_a.slug, "email": "admin@alpha-co.com"})
    token = captured["url"].split("token=")[1].split("&")[0]

    r = c.post("/api/auth/set-password", json={"token": token, "new_password": "resetpassword1"})
    assert r.status_code == 200

    old = c.post("/api/auth/login", json={
        "organization_slug": org_a.slug, "email": "admin@alpha-co.com", "password": "password123"})
    assert old.status_code == 401
    new = c.post("/api/auth/login", json={
        "organization_slug": org_a.slug, "email": "admin@alpha-co.com", "password": "resetpassword1"})
    assert new.status_code == 200


def test_set_password_rejects_wrong_token_purpose(org_a):
    """A normal login/access token must not work as a set-password token."""
    c = org_a.client
    r = c.post("/api/auth/set-password", json={
        "token": org_a.admin["Authorization"].split(" ")[1], "new_password": "whatever123"})
    assert r.status_code == 400
