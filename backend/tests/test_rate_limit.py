from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, limiter

LOGIN = {"organization_slug": "nope", "email": "x@y.com", "password": "whatever1"}


def test_window_slides():
    lim = SlidingWindowLimiter()
    assert lim.check("k", 2, window=60, now=0)[0]
    assert lim.check("k", 2, window=60, now=1)[0]
    allowed, retry = lim.check("k", 2, window=60, now=2)
    assert not allowed and 1 <= retry <= 60
    assert lim.check("k", 2, window=60, now=61)[0]        # first hit has aged out
    assert lim.check("other", 2, window=60, now=2)[0]     # keys are independent


def test_login_is_limited_per_ip(client):
    for _ in range(settings.RATE_LIMIT_AUTH_PER_MINUTE):
        assert client.post("/api/auth/login", json=LOGIN).status_code == 401
    r = client.post("/api/auth/login", json=LOGIN)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


def test_429_still_carries_cors_headers(client):
    for _ in range(settings.RATE_LIMIT_AUTH_PER_MINUTE):
        client.post("/api/auth/login", json=LOGIN)
    r = client.post("/api/auth/login", json=LOGIN, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_general_limit_is_per_user(org_a, org_b, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 5)
    limiter.reset()
    c = org_a.client
    for _ in range(5):
        assert c.get("/api/leads", headers=org_a.admin).status_code == 200
    assert c.get("/api/leads", headers=org_a.admin).status_code == 429
    assert c.get("/api/leads", headers=org_b.admin).status_code == 200   # someone else is unaffected
    assert c.get("/api/health").status_code == 200                       # health checks are exempt


def test_expensive_endpoints_have_a_tighter_limit(org_a, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_EXPENSIVE_PER_MINUTE", 2)
    limiter.reset()
    c = org_a.client
    # no leads exist, so these fail fast with 400 — but they still count against the bucket
    assert c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).status_code == 400
    assert c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).status_code == 400
    assert c.post("/api/leads/bulk-audit", headers=org_a.admin, json={}).status_code == 429
    assert c.get("/api/leads", headers=org_a.admin).status_code == 200   # ordinary traffic still fine


def test_forwarded_for_uses_rightmost_hop_and_only_when_trusted(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 2)

    # untrusted: header is ignored, everyone shares the socket address
    limiter.reset()
    for i in range(2):
        client.post("/api/auth/login", json=LOGIN, headers={"X-Forwarded-For": f"5.5.5.{i}"})
    assert client.post("/api/auth/login", json=LOGIN, headers={"X-Forwarded-For": "5.5.5.99"}).status_code == 429

    # trusted proxy: buckets follow the proxy-appended (rightmost) address; spoofing the left side doesn't help
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    limiter.reset()
    for i in range(2):
        client.post("/api/auth/login", json=LOGIN, headers={"X-Forwarded-For": f"66.6.6.{i}, 9.9.9.9"})
    assert client.post("/api/auth/login", json=LOGIN, headers={"X-Forwarded-For": "1.2.3.4, 9.9.9.9"}).status_code == 429
    assert client.post("/api/auth/login", json=LOGIN, headers={"X-Forwarded-For": "1.2.3.4, 8.8.8.8"}).status_code == 401
