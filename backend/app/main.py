from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware

from app.api.routes import (
    leads, auth, pipeline, followups, deals, proposals,
    customers, activities, pitches, dashboard, ai, settings as settings_routes,
    discovery, audits, notifications, users, jobs, campaigns, exports,
)

# Route registration order matters within a shared prefix: FastAPI matches in
# registration order, so a literal path (exports' GET /api/leads/export.csv)
# must be registered before a path-parameter route that could shadow it
# (leads' GET /api/leads/{lead_id} would otherwise treat "export.csv" as a
# lead_id and 404 before exports.py's route is ever tried).

app = FastAPI(title="AI Lead Gen + Sales CRM API", version="0.1.0")

# Order matters: the last middleware added is the outermost. CORS must wrap the
# rate limiter so that 429 responses still carry CORS headers the browser can read.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router_module in (
    auth, exports, leads, pipeline, followups, deals, proposals,
    customers, activities, pitches, dashboard, ai, settings_routes,
    discovery, audits, notifications, users, jobs, campaigns,
):
    app.include_router(router_module.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
