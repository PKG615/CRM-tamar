"""
Sliding-window rate limiting, in memory, per process.

Three buckets:
  * auth       POST /api/auth/login|register     keyed by client IP   (brute-force guard)
  * expensive  AI calls, audits, discovery, ...  keyed by user        (they cost real money / CPU)
  * general    everything else under /api         keyed by user (or IP if unauthenticated)

Honest limitation: counters live in this process's memory. With N uvicorn
workers or N containers, each keeps its own counters, so the effective limit
is up to N x the configured value. That's fine for abuse protection; if you
need exact global limits, back `SlidingWindowLimiter` with Redis.
"""
import re
import threading
import time
from collections import deque

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

WINDOW_SECONDS = 60.0

_AUTH_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/forgot-password", "/api/auth/set-password"}
_EXPENSIVE = [
    re.compile(p) for p in (
        r"^/api/ai/",
        r"^/api/leads/discover$",
        r"^/api/leads/bulk-audit$",
        r"^/api/leads/[^/]+/audit$",
        r"^/api/leads/[^/]+/pitch$",
        r"^/api/leads/[^/]+/pitch/[^/]+/send$",
    )
]


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def check(self, key: str, limit: int, window: float = WINDOW_SECONDS, now: float | None = None):
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = now - window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, int(hits[0] + window - now) + 1)
            hits.append(now)
            self._prune(now, window)
            return True, 0

    def _prune(self, now: float, window: float) -> None:
        if now - self._last_prune < window:
            return
        self._last_prune = now
        for k in [k for k, h in self._hits.items() if not h or h[-1] <= now - window]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _client_ip(request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # rightmost entry = the one appended by our own proxy; leftmost can be spoofed
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _user_key(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    return f"user:{sub}" if sub else None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if (
            not settings.RATE_LIMIT_ENABLED
            or request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path == "/api/health"
        ):
            return await call_next(request)

        ip = _client_ip(request)
        if request.method == "POST" and path in _AUTH_PATHS:
            bucket, key, limit = "auth", f"ip:{ip}", settings.RATE_LIMIT_AUTH_PER_MINUTE
        else:
            who = _user_key(request) or f"ip:{ip}"
            if request.method == "POST" and any(rx.match(path) for rx in _EXPENSIVE):
                bucket, limit = "expensive", settings.RATE_LIMIT_EXPENSIVE_PER_MINUTE
            else:
                bucket, limit = "general", settings.RATE_LIMIT_PER_MINUTE
            key = who

        allowed, retry_after = limiter.check(f"{bucket}:{key}", limit)
        if not allowed:
            return JSONResponse(
                {"detail": "Too many requests — please slow down and try again shortly."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
