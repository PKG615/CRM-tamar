import ipaddress
import re
import socket
import time
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class AuditError(Exception):
    pass


MAX_BODY_BYTES = 2_000_000
MAX_REDIRECTS = 5


def _assert_public_url(url: str) -> None:
    """
    SSRF guard. The audit fetches URLs that came from third-party data, and it
    now runs unattended in a worker, so refuse anything that resolves to a
    private / loopback / link-local address (this also blocks cloud metadata
    endpoints like 169.254.169.254). Checked again on every redirect hop.
    Known limitation: DNS is resolved here and again by httpx, so a hostile
    DNS server could still rebind between the two lookups.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AuditError("Only http(s) websites can be audited")
    host = parsed.hostname
    if not host:
        raise AuditError("Invalid website URL")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise AuditError(f"Could not resolve host: {host}")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise AuditError("Refusing to audit a non-public address")


def _fetch_html(url: str, timeout: float = 12.0) -> tuple[str, float, dict, str]:
    """Returns (html, response_time_seconds, response_headers, final_url)."""
    start = time.monotonic()
    current = url
    with httpx.Client(follow_redirects=False, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LeadAuditBot/1.0)"
    }) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_url(current)
            with client.stream("GET", current) as resp:
                location = resp.headers.get("location")
                if resp.is_redirect and location:
                    current = str(httpx.URL(current).join(location))
                    continue
                resp.raise_for_status()
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) >= MAX_BODY_BYTES:
                        break
                headers = dict(resp.headers)
                encoding = resp.encoding or "utf-8"
            break
        else:
            raise AuditError("Too many redirects")
    elapsed = time.monotonic() - start
    return bytes(body[:MAX_BODY_BYTES]).decode(encoding, errors="replace"), elapsed, headers, current


def _score_seo(soup: BeautifulSoup) -> tuple[int, list[str]]:
    """0-100 heuristic SEO score + human-readable recommendations."""
    score = 100
    recs = []

    title = soup.find("title")
    if not title or not title.text.strip():
        score -= 20
        recs.append("Add a descriptive <title> tag — none was found.")
    elif len(title.text.strip()) > 60:
        score -= 5
        recs.append("Page title is longer than 60 characters — search engines may truncate it.")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc or not meta_desc.get("content", "").strip():
        score -= 15
        recs.append("Add a meta description — helps click-through from search results.")

    h1s = soup.find_all("h1")
    if len(h1s) == 0:
        score -= 15
        recs.append("No <h1> heading found — search engines use this to understand page topic.")
    elif len(h1s) > 1:
        score -= 5
        recs.append("Multiple <h1> tags found — use only one per page.")

    images = soup.find_all("img")
    if images:
        missing_alt = sum(1 for img in images if not img.get("alt", "").strip())
        if missing_alt / len(images) > 0.5:
            score -= 10
            recs.append(f"{missing_alt}/{len(images)} images are missing alt text — hurts SEO and accessibility.")

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if not canonical:
        score -= 5
        recs.append("No canonical link tag found.")

    return max(0, score), recs


def _score_content(soup: BeautifulSoup) -> tuple[int, list[str]]:
    """
    0-100 content-quality heuristic: how much actual substance is on the
    page, and how readable it is. Deliberately simple (word count,
    sentence length, heading structure) rather than anything that needs
    an external API or NLP model — good enough to flag the obvious cases
    (a near-empty page, a wall of text with no structure) without
    pretending to be a real content-quality tool.
    """
    score = 100
    recs = []

    # Strip script/style/noscript first so JS code and CSS never get
    # counted as "content" — clone the tree so other scorers still see
    # the original soup untouched.
    text_soup = BeautifulSoup(str(soup), "lxml")
    for tag in text_soup(["script", "style", "noscript"]):
        tag.decompose()
    text = text_soup.get_text(separator=" ")
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    word_count = len(words)

    if word_count < 100:
        score -= 40
        recs.append(f"Only {word_count} words of visible content — pages this thin struggle to rank and rarely convince a visitor.")
    elif word_count < 300:
        score -= 15
        recs.append(f"Only {word_count} words of visible content — consider adding more detail about products, services, or the business.")

    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if sentences and word_count > 0:
        avg_words_per_sentence = word_count / len(sentences)
        if avg_words_per_sentence > 30:
            score -= 15
            recs.append(f"Average sentence length is {avg_words_per_sentence:.0f} words — shorter sentences are easier to read.")

    subheadings = soup.find_all(["h2", "h3"])
    if word_count > 500 and not subheadings:
        score -= 15
        recs.append("Long page with no subheadings (h2/h3) — breaking content into sections helps both readers and SEO.")

    return max(0, score), recs


def _score_mobile(soup: BeautifulSoup) -> tuple[int, list[str]]:
    score = 100
    recs = []
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if not viewport:
        score -= 40
        recs.append("No viewport meta tag — the site likely isn't mobile-responsive.")
    return max(0, score), recs


def _score_security(url: str, headers: dict) -> tuple[int, list[str]]:
    score = 100
    recs = []
    if not url.lower().startswith("https://"):
        score -= 40
        recs.append("Site is not served over HTTPS — a major trust and SEO issue.")
    if "strict-transport-security" not in {k.lower() for k in headers}:
        score -= 10
        recs.append("Missing Strict-Transport-Security header.")
    if "x-content-type-options" not in {k.lower() for k in headers}:
        score -= 5
        recs.append("Missing X-Content-Type-Options header.")
    return max(0, score), recs


def _score_performance_heuristic(response_time: float, html_size_kb: float) -> tuple[int, list[str]]:
    """
    Used when PAGESPEED / no API key configured. A rough proxy only —
    real performance scoring should go through PageSpeed Insights
    (see get_pagespeed_scores below) once GOOGLE_MAPS_API_KEY-style key
    is provisioned for it.
    """
    score = 100
    recs = []
    if response_time > 3:
        score -= 30
        recs.append(f"Page took {response_time:.1f}s to respond — aim for under 1-2s.")
    elif response_time > 1.5:
        score -= 15
        recs.append(f"Page took {response_time:.1f}s to respond — could be faster.")
    if html_size_kb > 500:
        score -= 15
        recs.append(f"HTML document is {html_size_kb:.0f}KB — consider reducing page weight.")
    return max(0, score), recs


def get_pagespeed_scores(url: str, api_key: str) -> Optional[dict]:
    """
    Real performance/SEO/accessibility scores from Google PageSpeed
    Insights, if a key is configured. Returns None on any failure so the
    caller falls back to the heuristic scorer rather than failing the
    whole audit over one optional API.
    """
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(PAGESPEED_URL, params={"url": url, "key": api_key, "strategy": "mobile"})
            resp.raise_for_status()
            data = resp.json()
        categories = data["lighthouseResult"]["categories"]
        return {
            "performance": round(categories["performance"]["score"] * 100),
            "seo": round(categories.get("seo", {}).get("score", 0) * 100) if "seo" in categories else None,
            "accessibility": round(categories.get("accessibility", {}).get("score", 0) * 100) if "accessibility" in categories else None,
        }
    except Exception:
        return None


def run_website_audit(website_url: str) -> dict:
    """
    Main entry point. Returns a dict shaped for WebsiteAudit:
    {overall_score, performance_score, seo_score, mobile_score,
     security_score, content_score, recommendations: [...], raw_report: {...}}

    Never raises for "site is slow/has issues" — those are audit
    FINDINGS. It raises AuditError only when the site can't be reached
    at all (dead link, DNS failure, timeout) since that itself is useful
    signal (requirement: "website unavailable" scores leads higher).
    """
    if not website_url:
        raise AuditError("No website URL provided")

    parsed = urlparse(website_url)
    if not parsed.scheme:
        website_url = f"https://{website_url}"

    try:
        html, response_time, headers, final_url = _fetch_html(website_url)
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        raise AuditError(f"Could not reach website: {e}")

    soup = BeautifulSoup(html, "lxml")
    html_size_kb = len(html.encode("utf-8")) / 1024

    seo_score, seo_recs = _score_seo(soup)
    mobile_score, mobile_recs = _score_mobile(soup)
    security_score, security_recs = _score_security(final_url, headers)  # judge the URL actually served
    content_score, content_recs = _score_content(soup)

    pagespeed = None
    if settings.GOOGLE_MAPS_API_KEY:  # PageSpeed uses the same Google Cloud API key
        pagespeed = get_pagespeed_scores(website_url, settings.GOOGLE_MAPS_API_KEY)

    if pagespeed:
        performance_score = pagespeed["performance"]
        perf_recs = []
    else:
        performance_score, perf_recs = _score_performance_heuristic(response_time, html_size_kb)

    overall_score = round((seo_score + mobile_score + security_score + performance_score + content_score) / 5)
    all_recs = perf_recs + seo_recs + mobile_recs + security_recs + content_recs

    return {
        "overall_score": overall_score,
        "performance_score": performance_score,
        "seo_score": seo_score,
        "mobile_score": mobile_score,
        "security_score": security_score,
        "content_score": content_score,
        "recommendations": all_recs,
        "raw_report": {
            "response_time_seconds": round(response_time, 2),
            "html_size_kb": round(html_size_kb, 1),
            "used_pagespeed_api": pagespeed is not None,
        },
    }
