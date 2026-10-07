# LedgerCRM — AI Lead Generation + Sales CRM

Multi-tenant SaaS: React frontend, FastAPI backend, PostgreSQL, a
Postgres-backed background worker (no Redis/Celery needed), Docker
deployment, and a 51-test pytest suite. Built end-to-end from the
requirements doc, including production hardening beyond the original spec.

## What it does

Google Maps lead discovery → website audit → AI-generated WhatsApp pitch →
CRM (pipeline, follow-ups, deals, proposals, customer conversion) → an AI
sales assistant grounded in real CRM data, with team management,
notifications, and reporting wrapped around it.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Alembic, PostgreSQL, JWT auth
- **Frontend**: React + Vite, a "ledger" design system (flat bordered
  panels, navy/teal/amber palette, no card-shadow kit)
- **Background jobs**: a Python worker (`python -m app.worker`) claims
  work from a `background_jobs` table using `SELECT ... FOR UPDATE SKIP
  LOCKED` — Postgres is the queue, so there's no separate broker to run
- **AI**: Anthropic API for pitch generation, sales recommendations, and
  the sales assistant
- **Deploy**: Docker Compose (db + api + worker + nginx-served frontend)

## Run it

```bash
cp .env.example .env               # fill in POSTGRES_PASSWORD, SECRET_KEY (openssl rand -hex 32)
docker compose up -d --build
open http://localhost:8080
```

API keys (`ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`, `WHATSAPP_API_TOKEN`
+ `WHATSAPP_PHONE_NUMBER_ID`) are optional — each feature just stays
disabled with a clear error until its key is set.

For local development without Docker, see `backend/README`-style comments
in `docker-compose.yml`, or run `uvicorn app.main:app --reload` against a
local Postgres with `alembic upgrade head` applied, and `npm run dev` in
`frontend/`.

### Tests

```bash
cd backend
pip install -r requirements.txt
pytest              # 51 tests, run against SQLite — no DB setup needed
```

## Architecture highlights

- **Multi-tenancy**: every table carries `organization_id`; every query
  filters by it; `app/core/tenancy.py` additionally guards foreign keys
  that arrive in request bodies (e.g. `assigned_to`, `lead_id`) so one
  tenant can't attach data to another tenant's records.
- **Roles**: ADMIN / SALES_MANAGER / SALES_EXECUTIVE / VIEWER, enforced
  server-side via `require_writer` / `require_manager` / `require_admin`
  dependencies (`app/core/security.py`) — a hidden button in the UI is a
  convenience, the API is the actual enforcement.
- **Background worker**: bulk website audits and the daily overdue
  follow-up notification sweep both run in `app/worker.py`. Jobs are
  resumable (a crashed worker's `RUNNING` job gets requeued and picks up
  where it left off) and cancellable from the UI.
- **Nothing hard-coded**: lead-scoring weights, opportunity value ranges,
  and pipeline stages are all per-organization settings, editable from
  `/settings`.
- **Security**: bcrypt password hashing, JWTs scoped to one org, rate
  limiting (per-IP for auth, per-user for everything else, stricter for
  AI/audit/discovery calls), a production startup check that refuses to
  boot with a default/weak `SECRET_KEY`, timing-safe comparison for the
  cron secret, nginx configured to trust only its own `X-Forwarded-For`
  entry.

## Feature list

**Lead generation**: Google Maps search (deduped by `google_place_id`),
website audit engine (SEO/mobile/security/performance scoring, upgrades
to real Google PageSpeed Insights if a key is set), configurable lead
scoring, AI-generated WhatsApp pitches sent via the Meta Cloud API.

**CRM**: dashboard, lead list with search/filter/pagination, lead detail
(pitch, audit, score, deals, activity timeline), drag-and-drop pipeline,
follow-ups (overdue/today/upcoming), deals, proposals (line items, PDF
download), customer conversion, reports (win rate, deals by stage, top
leads).

**Team & ops**: team management (invite, role changes, password reset,
deactivation — with last-admin and self-demotion protection), in-app
notifications (lead assigned, deal won/lost, proposal accepted, follow-up
due/overdue), an audit log of sensitive actions, an AI sales assistant
chat grounded in real CRM data, bulk website audits as a cancellable
background job with live progress.

**Total**: 53 API endpoints, 51 passing tests, clean Vite build.

## Email delivery — done

`app/services/email_service.py` — plain SMTP (stdlib `smtplib`, no extra
dependency), works with any provider: SES, SendGrid, Mailgun, Postmark, or
a Gmail app-password relay. Set `SMTP_HOST` (+ user/password/from) and
`FRONTEND_URL` in `.env` to turn it on; leave `SMTP_HOST` blank and
everything still works, just without email — same "stays a graceful
no-op until configured" pattern as Google Maps / WhatsApp / Anthropic.

- **Forgot password** (`/login` → "Forgot password?" → `/set-password`) —
  always returns the same generic response whether or not the account
  exists (no account-enumeration leak), only actually emails a link if
  the account exists, is active, and SMTP is configured.
- **Team invites** — the "Add member" password field is now optional;
  leave it blank and, if SMTP is configured, the person gets a "set your
  password" email. If email isn't configured (or fails to send), a
  temporary password is generated and returned once in the response for
  the admin to share directly — an account is never left in a broken
  password-less state either way.
- **Token design**: invite/reset links use a signed JWT (not a DB table)
  carrying a fingerprint of the user's *current* password hash. Using the
  link changes the password, which changes the fingerprint, which makes
  the same link fail if reused — no separate token-revocation bookkeeping
  needed. Verified end-to-end (old password rejected after reset, new
  password works, reusing a consumed token correctly fails, and
  forgot-password gives byte-identical responses for real vs. fake
  emails).

55 endpoints, 57 passing tests, 55 frontend modules.

## Content score + WhatsApp templates — done

**`content_score`**: found and fixed a real bug while adding this —
`_score_mobile` had lost its `def` line in an earlier edit, so
`run_website_audit` crashed with a `NameError` on every call (masked
until a test exercised the actual scoring path). Fixed, and
`_score_content` now checks word count, average sentence length, and
whether a long page has any subheadings — each with a plain-English
recommendation, same pattern as the other scorers. Verified: a one-line
page scores 60 with a "too thin" recommendation; a substantial,
well-structured page scores 100.

**WhatsApp templates**: `send_whatsapp_template()` sends Meta's
template-message payload (name + language + `{{1}}`, `{{2}}`... body
params) alongside the existing free-form `send_whatsapp_message()`. The
send route now checks whether a lead has any prior sent/delivered/
read/replied pitch — no prior contact means the 24h window was never
opened, so it uses the template (configured via `WHATSAPP_TEMPLATE_NAME`)
instead of free-form text; a warm lead still gets free-form. If a cold
send is attempted with no template configured and Meta rejects it, the
error now says why instead of just relaying Meta's raw message. 7 new
tests cover both payload shapes and all three routing cases (cold+
template, cold+no-template, warm).

64 passing tests (up from 57), 55 endpoints, 55 frontend modules.

## Campaigns, CSV export, multi-language — done

**Bulk outreach campaigns** (`/campaigns`): email or SMS blasts to a
filtered slice of leads (by status, city, min score), with
`{{business_name}}`/`{{city}}`/`{{category}}` placeholders. Sending runs
in the background worker (`JobType.CAMPAIGN_SEND`), same resumable/
cancellable pattern as bulk audits — a 500-recipient campaign doesn't hold
an HTTP connection open, and the recipient list is frozen at enqueue time
so a crash mid-send resumes correctly rather than re-sending from scratch.
"Preview audience" shows the recipient count before committing. SMS goes
through Twilio's REST API directly (`TWILIO_ACCOUNT_SID`/`AUTH_TOKEN`/
`FROM_NUMBER`); email reuses `email_service.py`. A weekly digest email
(new leads, deals won, overdue follow-ups) goes out to each org's
admins/managers automatically via the worker — nothing to configure
beyond having SMTP set up.

**CSV export**: `GET /api/leads/export.csv` (same filters as the Leads
list, so "export what I'm looking at" works) and `/api/deals/export.csv`.
Buttons on both pages.

**Multi-language (English/Hindi)**: a lightweight custom i18n layer
(`src/i18n/translations.js` + `LanguageContext`) covering nav, topbar,
common actions, the dashboard, and login — not every string on every
page, by design (see the file's own comment). A language switcher sits
in the sidebar and on the login screen; the choice persists in
`localStorage`.

**Found while wiring this up, not before**: the app was actually broken
— `App.jsx` referenced a variable called `TITLES` while the constant was
named `TITLE_KEYS` (a `ReferenceError` on every single page load),
`LanguageProvider` was imported but never actually wrapped around the
app, and `Login.jsx`/`Sidebar.jsx`/`Dashboard.jsx` still had hardcoded
English strings despite the translation keys existing for all three. A
clean `npm run build` did not catch any of this, because esbuild doesn't
check for undefined variables — it took running ESLint with `no-undef`
across the whole source (not just "did it build") to confirm the fix and
find nothing else like it. Worth remembering: a successful build is
necessary but not sufficient evidence a React app actually runs.

76 passing tests, 62 endpoints, 58 frontend modules.

## What's left, and why it's not "done" here

- **Live API smoke test** (Google Maps, PageSpeed, real WhatsApp sends,
  SMTP): genuinely not something I can complete from here — this sandbox
  has no network access to those hosts, so there's nothing to point at as
  "tested." Every integration is written defensively (graceful no-op when
  unconfigured, clear errors on failure) and covered by tests that
  simulate their APIs, but a real credential can still surface something
  a simulation didn't — provider-side rate limits, a template Meta
  actually rejects for a reason other than "no template", a PageSpeed
  quota. Run one smoke test per integration before depending on it.
- **Multi-worker load test**: same honesty — the job queue's correctness
  under concurrency (`SELECT ... FOR UPDATE SKIP LOCKED`) is a sound,
  well-known pattern, but "sound in theory" and "load-tested" are
  different claims, and standing up several real worker processes against
  concurrent load isn't something this environment can do either. If it
  matters before launch, run 2+ `python -m app.worker` processes against
  a shared Postgres with a large bulk-audit job queued and confirm no
  lead gets audited twice and no job is dropped.
#   C R M - t a m a r  
 