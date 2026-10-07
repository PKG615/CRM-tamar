from pydantic import model_validator
from pydantic_settings import BaseSettings


DEFAULT_SECRET_KEY = "change-me-in-env"


class Settings(BaseSettings):
    # "production" turns on startup safety checks (see _production_safety below).
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/crm_platform"

    # Auth
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # AI provider (keys never exposed to frontend — read only here, server-side)
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"

    # Google Maps
    GOOGLE_MAPS_API_KEY: str = ""

    # WhatsApp Business API
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    # Meta only allows free-form text within a 24h customer-service window;
    # first-touch cold outreach must use a pre-approved template instead.
    # Register one in Meta Business Manager (a single {{1}} body variable
    # for the business name is enough for a simple "hi {{1}}, ..." opener)
    # and set its name here. Leave blank to always send free-form text —
    # fine for warm leads, but Meta will reject cold first-touch sends.
    WHATSAPP_TEMPLATE_NAME: str = ""
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en_US"

    # SMS (Twilio), for bulk SMS campaigns. Same graceful-no-op pattern as
    # every other optional integration here.
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Bulk outreach campaigns
    CAMPAIGN_MAX_RECIPIENTS: int = 1000
    CAMPAIGN_DELAY_SECONDS: float = 0.3

    # Scheduled weekly digest email to admins/managers (worker-triggered,
    # same pattern as the daily follow-up sweep)
    WEEKLY_REPORT_DAY: int = 0   # Monday = 0 (Python's date.weekday())
    WEEKLY_REPORT_HOUR: int = 8  # server-local hour, 24h

    # CORS: comma-separated list of allowed browser origins. Only needed when
    # the frontend is served from a different origin than the API (e.g. Vercel
    # frontend + separately hosted API). Behind the bundled nginx it's same-origin.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Rate limiting (per process, in memory — see app/core/rate_limit.py)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120          # general API traffic, per user
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10      # login/register, per client IP
    RATE_LIMIT_EXPENSIVE_PER_MINUTE: int = 10  # AI / audit / discovery calls, per user
    # Only enable behind a reverse proxy you control (nginx in docker-compose):
    # it makes the limiter read the client IP from X-Forwarded-For.
    TRUST_PROXY_HEADERS: bool = False

    # Background worker
    WORKER_POLL_SECONDS: float = 3.0
    AUDIT_DELAY_SECONDS: float = 1.0   # pause between sites in a bulk audit
    BULK_AUDIT_MAX_LEADS: int = 500
    FOLLOWUP_SWEEP_HOUR: int = 8       # daily follow-up notifications, server-local time

    # Shared secret for cron-triggered system endpoints (e.g. overdue
    # follow-up sweep) — these touch every tenant, so they can't use a
    # normal per-org user JWT. Set this and pass it as X-Cron-Secret.
    CRON_SECRET: str = ""

    # Email (team invites, password reset). Stays disabled — invite/reset
    # endpoints fall back to returning a value the admin shares directly —
    # until SMTP_HOST is set. Works with any SMTP provider (SES, SendGrid,
    # Mailgun, Postmark, a Gmail app-password relay, etc).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@example.com"
    SMTP_USE_TLS: bool = True

    # Where the frontend is served, so emailed links point somewhere real.
    FRONTEND_URL: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _production_safety(self):
        # A guessable JWT secret lets anyone forge admin tokens for any tenant, so
        # refuse to boot in production with the default or a short one.
        if self.ENVIRONMENT.lower() == "production" and (
            self.SECRET_KEY == DEFAULT_SECRET_KEY or len(self.SECRET_KEY) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be set to a random value of at least 32 characters when "
                "ENVIRONMENT=production (generate one with: openssl rand -hex 32)"
            )
        return self

    class Config:
        env_file = ".env"


settings = Settings()
