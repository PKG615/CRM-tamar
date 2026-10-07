import socket

import httpx
import pytest

from app.services import audit_service
from app.services.audit_service import AuditError, _assert_public_url, run_website_audit


def resolve_to(monkeypatch, ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (ip, 0))])


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.20", "172.16.0.9",
                                "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fe80::1"])
def test_non_public_addresses_are_refused(monkeypatch, ip):
    resolve_to(monkeypatch, ip)
    with pytest.raises(AuditError, match="non-public"):
        _assert_public_url("http://some-site.example/")


def test_public_address_and_scheme_rules(monkeypatch):
    resolve_to(monkeypatch, "93.184.216.34")
    _assert_public_url("https://example.com/")                        # no exception
    for bad in ("ftp://example.com", "file:///etc/passwd", "javascript:alert(1)"):
        with pytest.raises(AuditError):
            _assert_public_url(bad)


def test_unresolvable_host_is_an_audit_error(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(AuditError, match="resolve"):
        _assert_public_url("http://does-not-exist.invalid")


REAL_CLIENT = httpx.Client  # captured at import so repeated patching in one test doesn't stack transports


def patch_transport(monkeypatch, handler):
    monkeypatch.setattr(audit_service.httpx, "Client",
                        lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


GOOD_HTML = """<html><head><title>Great Cafe</title><meta name="description" content="Coffee">
<meta name="viewport" content="width=device-width"><link rel="canonical" href="/"></head>
<body><h1>Hi</h1></body></html>"""


def test_redirect_to_internal_address_is_blocked(monkeypatch):
    def resolver(host, *a, **k):
        ip = "169.254.169.254" if host == "169.254.169.254" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    patch_transport(monkeypatch, lambda req: httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"}))
    with pytest.raises(AuditError, match="non-public"):
        run_website_audit("http://harmless-looking.example.com")


def test_http_to_https_redirect_is_scored_on_the_final_url(monkeypatch):
    resolve_to(monkeypatch, "93.184.216.34")

    def handler(req):
        if req.url.scheme == "http":
            return httpx.Response(301, headers={"location": "https://cafe.example.com/"})
        return httpx.Response(200, text=GOOD_HTML, headers={
            "strict-transport-security": "max-age=1", "x-content-type-options": "nosniff"})
    patch_transport(monkeypatch, handler)

    report = run_website_audit("http://cafe.example.com")
    assert report["security_score"] == 100                # judged on https://, not the http:// we started with
    assert report["seo_score"] == 100 and report["mobile_score"] == 100


def test_redirect_loop_and_http_errors_become_audit_errors(monkeypatch):
    resolve_to(monkeypatch, "93.184.216.34")
    patch_transport(monkeypatch, lambda req: httpx.Response(302, headers={"location": str(req.url)}))
    with pytest.raises(AuditError, match="redirects"):
        run_website_audit("https://loop.example.com")
    patch_transport(monkeypatch, lambda req: httpx.Response(503))
    with pytest.raises(AuditError, match="Could not reach"):
        run_website_audit("https://down.example.com")


def test_oversized_pages_are_truncated_not_loaded_whole(monkeypatch):
    resolve_to(monkeypatch, "93.184.216.34")
    patch_transport(monkeypatch, lambda req: httpx.Response(200, content=b"<html>" + b"a" * 5_000_000))
    html, *_ = audit_service._fetch_html("https://huge.example.com")
    assert len(html) <= audit_service.MAX_BODY_BYTES + 65536
