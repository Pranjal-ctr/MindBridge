# Kio SaaS App — Project Context

> **Last Updated:** September 11, 2026
> **Status:** Production hardening complete -- audit trail, availability engine, revocable sessions, observability, consent layer
> **Tests:** 370 backend (`pytest tests/`) + 42 frontend (`npm test`)

---

## 📋 Project Overview

**Kio** is an AI-driven SaaS platform that supports **student wellness** and **parenting guidance**. It offers personalized insights and resources for emotional health and academic success.

### Core Value Proposition
- **Students** get a private, 24/7 AI wellness companion
- **Parents** receive aggregated insights (never raw conversations) to support their child
- **Counselors** get AI-generated summaries for efficient professional intervention
- **Schools** get anonymized analytics to understand and improve student wellness

---

## 🏗️ Tech Stack

| Layer         | Technology                                |
|---------------|-------------------------------------------|
| **Framework** | React 18.3 + TypeScript                   |
| **Bundler**   | Vite 6.3                                  |
| **Styling**   | Tailwind CSS v4 (via `@tailwindcss/vite`) |
| **UI Lib**    | shadcn/ui (Radix primitives)              |
| **Charts**    | Recharts                                  |
| **Routing**   | React Router v7                           |
| **Animations**| Motion (Framer Motion)                    |
| **Icons**     | Lucide React                              |
| **Fonts**     | Inter (Google Fonts)                      |

---

## 📁 Project Structure

```
Design MindBridge SaaS App/
├── index.html                    # Entry HTML
├── package.json                  # Dependencies & scripts
├── tsconfig.json                 # TypeScript configuration
├── vite.config.ts                # Vite + Tailwind + React plugins
├── postcss.config.mjs            # PostCSS (empty, Tailwind v4 handles it)
├── claude.md                     # ⬅ THIS FILE — project context
├── guidelines/
│   └── Guidelines.md             # Design system guidelines (template)
├── src/
│   ├── main.tsx                  # React entry point
│   ├── styles/
│   │   ├── index.css             # CSS entry (imports fonts, tailwind, theme)
│   │   ├── fonts.css             # Google Fonts (Inter)
│   │   ├── tailwind.css          # Tailwind v4 config (@source directive)
│   │   ├── theme.css             # Design tokens (CSS variables + @theme)
│   │   └── globals.css           # Global overrides (currently empty)
│   └── app/
│       ├── App.tsx               # Root component with React Router
│       └── components/
│           ├── LandingPage.tsx    # Public marketing page
│           ├── LoginSignup.tsx    # Auth page (login/signup toggle)
│           ├── StudentDashboard.tsx   # AI chat + wellness tracking
│           ├── ParentDashboard.tsx    # Insights + recommendations
│           ├── CounselorDashboard.tsx # Student profiles + sessions
│           ├── SchoolAdminDashboard.tsx # Anonymized analytics
│           ├── StudentInviteCode.tsx  # Family/invite code management
│           ├── figma/
│           │   └── ImageWithFallback.tsx  # Figma image helper
│           └── ui/               # shadcn/ui primitives (48 files)
│               ├── button.tsx
│               ├── card.tsx
│               ├── utils.ts      # cn() utility
│               └── ... (accordion, dialog, etc.)
```

---

## 🗺️ Routes

**Public**

| Path                | Component            | Description                             |
|---------------------|----------------------|-----------------------------------------|
| `/`                 | LandingPage          | Public marketing/landing page           |
| `/login`            | LoginSignup          | Auth (login/signup with role select)    |
| `/terms`            | TermsOfService       | Terms of service (pending legal review) |
| `/privacy`          | PrivacyPolicy        | Privacy policy (pending legal review)   |
| `/verify-email`     | VerifyEmail          | Email-verification landing + resend     |
| `/forgot-password`  | ForgotPassword       | Request a password-reset link           |
| `/reset-password`   | ResetPassword        | Complete a password reset               |
| `/guardian-consent` | GuardianConsent      | One-time guardian approval link (13–17) |

**Signed-in** (behind `ProtectedRoute`, which also mounts `VerifyBanner`,
`GuardianConsentBanner`; the `NotificationBell` is mounted per-dashboard + `AdminLayout`)

| Path                  | Component            | Description                          |
|-----------------------|----------------------|--------------------------------------|
| `/student`            | StudentDashboard     | Comrade chat + check-in + mood        |
| `/student/family`     | StudentInviteCode    | Guardian management + invite codes    |
| `/student/growth`     | StudentGrowthProfile | Wellness trend + personal insights    |
| `/student/activities` | StudentActivities    | Weekly activities + AI summary        |
| `/student/profile`    | StudentProfile       | Age, gender, account details          |
| `/parent`             | ParentDashboard      | Child's wellness insights             |
| `/counselor`          | CounselorDashboard   | Roster, sessions, notes, risk queue   |
| `/school`             | SchoolAdminDashboard | School-wide anonymized analytics      |
| `/book-counselor`     | BookCounselor        | Time-first booking (students+parents) |

**Platform admin** (`/admin/*`, nested under `AdminLayout`)

| Path                          | Description                                    |
|-------------------------------|------------------------------------------------|
| `/admin`                      | Platform KPIs, unreviewed risk first           |
| `/admin/schools[/:tenantId]`  | School registration, seats, subscriptions      |
| `/admin/users`                | Disable / reset password                       |
| `/admin/counselors[/:id]`     | Register, verify (gates the booking directory) |
| `/admin/risk[/:riskId]`       | Cross-tenant risk oversight (read-only)        |
| `/admin/ai`                   | Model routing per feature + prompt activation  |
| `/admin/playground`           | AI playground                                  |
| `/admin/audit`                | Audit logs (+ CSV export)                      |
| `/admin/settings`             | Safety thresholds as validated JSON            |

`*` redirects to `/`.

---

## 🎨 Design System (Kio Brand — see `Rebranding/brand.md`)

### Colors (CSS Variables in `theme.css`)
- **Primary:** `#232B6D` (Kio Navy)
- **Secondary:** `#5A6BFF` (Kio Blue — interactive elements, links, charts)
- **Accent:** `#31D7C2` (Kio Teal — highlights, success, positive indicators)
- **Background:** `#F8FAFC` / **Text:** `#111827` primary, `#6B7280` secondary
- **Destructive:** `#ef4444` (Red 500)
- **Wellness Colors:** Green, Blue, Purple, Pink, Amber
- Brand gradient token: `--brand-gradient` (navy → blue → teal)
- Full dark mode support via `.dark` class (navy-tinted dark palette)

### Logo
- Wordmark component: `src/app/components/KioLogo.tsx` (`reverse` prop for dark surfaces)
- Favicon/app icon: `public/favicon.svg`; source assets in `Rebranding/`

### Typography
- **Headings:** Poppins (Google Fonts) via `--font-heading`
- **UI/Body:** Inter (Google Fonts) via `--font-sans`
- **Base size:** 16px
- **Weights:** 400 (normal), 500 (medium)

### Radius
- Base: `0.75rem` with sm/md/lg/xl variants

---

## 🔧 Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

---

## 📝 Change Log

### September 16, 2026 — Audit trail: append-only, correlated, content-minimal
- **The table was missing the four columns an incident actually needs.**
  `audit_logs` had actor/action/target since migration 001, which answers "what
  happened" but not "who were they acting *as*", "which school does this belong
  to", "did it succeed", or "which request was this". Migration 018 adds
  `actor_role`, `tenant_id`, `result`, `severity`, `request_id` (all additive;
  nothing dropped or renamed), plus indexes on `(action, created_at)`,
  `(tenant_id, created_at)` and `request_id`.
  Role and school are **denormalised on purpose**: a later role change must not
  rewrite what someone was permitted to do when they did it, and when a platform
  admin acts on a school the event belongs to the school **acted upon**, not to
  the admin's own tenant. `previous_state`/`new_state` were deliberately *not*
  added — `details.changed` carries changed field *names*, which answers the
  operational question without making the audit table a second copy of records
  holding a child's DOB, guardian details and risk level.
- **Seven call sites were building `AuditLog(...)` by hand** and bypassing
  `log_audit()` entirely, so they would silently have missed every new column.
  All now go through the helper. One was an outright bug: break-glass access
  did `action=f"break_glass_chat_access: {reason}"`, interpolating admin-typed
  free text into the **indexed action column** — so no two break-glass events
  ever shared an action and the UI's filter could only ever prefix-match. The
  reason is metadata; it moved to `details`.
- **Append-only is now the database's property, not the absence of code.** A
  Postgres trigger raises on `UPDATE`, `DELETE` and `TRUNCATE`. Installed by
  migration 018 *and* by an `after_create` hook in `models.py`, because the test
  suite builds its schema with `create_all` — a migration-only trigger would
  leave the append-only test asserting against a table that has none. Safe
  because user and tenant deletion here are both **soft**, so the
  `ON DELETE SET NULL` on `user_id` never fires from the app path. No
  UPDATE/DELETE endpoint exists and a test asserts that against the **live route
  table**, so adding one later fails CI rather than shipping quietly.
- **Coverage** (`app/audit_actions.py` — constants, not free strings; a typo in
  a string literal fails nowhere, it just creates an event class nobody will
  filter for). Values keep the repo's dotted-lowercase convention and the nine
  pre-existing actions keep their **exact** historical strings, so old rows and
  saved filters still work. New: the whole auth lifecycle (login success/failure,
  logout, Google, signup, verify, password reset, refresh rotation, replay
  revocation), counselor registration + **verification** (which gates the public
  booking directory), AI routing and **prompt activation** (which changes what
  Comrade says to every student), schedule/time-off CRUD, booking conflicts,
  risk-case and risk-queue views, crisis notification created/sent/**failed**,
  and reads/exports of the audit log itself.
- **Six constants are declared but deliberately not emitted** — the operations
  don't exist: no endpoint changes a user's role or school,
  `counselor_school_assignments` is only ever *read*, and `risk_assessments`
  has no assignee column. They are recorded in `docs/audit-logging.md` so whoever builds those
  wires the event rather than inventing a fifth spelling.
- **Privacy.** Audit rows say *that* something happened and to which record,
  never what was said. Safety events record the matched **category**, never the
  sentence that matched; crisis rows record a recipient **count**, never names;
  risk rows record levels, never `summary`; config rows record the **key**,
  never the value. Backstopped by `scrub_details()` (redacts ~25 key patterns,
  walks nested structures, caps strings at 200 chars) and by tests that sweep
  every row written during a real login/refresh/logout/safety-scan and assert no
  JWT-shaped string, password, or scanned message text is present anywhere.
- **Correlation reuses the existing request id** — `log_audit()` reads the
  `ContextVar` from `app/observability.py` rather than threading a parameter
  through ~60 call sites, and no second scheme was introduced. One id now joins
  audit row → structured log → Sentry event; the admin page filters on it.
- **Failure policy is explicit per event class.** `log_audit()` joins the
  caller's transaction and **fails closed** (admin, RBAC, school, break-glass,
  config, booking) — an unrecorded change is worse than a failed one. New
  `log_audit_detached()` commits in its own session and **fails open** (auth,
  safety, crisis, booking conflicts): those paths frequently *raise*, so a row
  on the caller's session would vanish exactly when it becomes evidence, and an
  audit problem must never lock every user out or block a crisis alert reaching
  a counselor. No queue, broker or worker was added.
- **Export is streamed and bounded** — 500 rows per round trip instead of
  building the whole file in memory, capped at 10,000 with the cap echoed in
  `X-Export-Max-Rows` (a silently truncated audit export is a compliance
  problem, not a UX one). The export event is committed **before** the first
  byte: FastAPI closes `yield` dependencies before the body streams, so the
  generator opens its own session — a bug the test client could not have caught,
  since `get_db` is overridden there. Verified against a real server.
- **Admin UI**: actor/role/school/result/severity/request-id columns, server-side
  filters for each, and a detail drawer. Filtering and paging stay server-side —
  the table is append-only and unbounded. Pagination orders by
  `(created_at, audit_id)`; `created_at` alone is not unique, so without the
  tiebreak pages silently repeat rows.
- **Access is platform-admin only**, enforced server-side (tested across all four
  other roles). School admins get **no** audit access: they can already see their
  roster, and a row naming which counselor opened which student's risk case is
  sensitive even inside one school. The `tenant_id` column and the scoped query
  exist and are tested, so enabling it later is a one-line change.
- ⚠️ **Retention is an open legal/product decision and no automatic deletion is
  implemented.** It is deliberately not guessed at — it depends on the same
  unanswered DPDP questions already recorded in `app/consent/policy.py`. Note
  that the append-only trigger makes future purging *deliberately awkward*: any
  retention policy must ship as a migration that drops the trigger, purges, and
  reinstalls it.
- Docs: new `docs/audit-logging.md` (what is and is not recorded, who can read
  it, append-only, failure policy, retention, and how audit logs / structured
  logs / Sentry relate), plus a section in `docs/production-configuration.md`.
- Tests: 38 new in `backend/tests/test_audit.py` (370 backend total).

### September 11, 2026 — Production hardening: observability, revocable sessions, schema drift
- **Two outright bugs.** `/health/db` returned **200** with an `"unhealthy"` body when
  the database was unreachable, so Docker's `HEALTHCHECK`, Render and any load balancer
  read it as passing and kept routing traffic to an instance that could not answer a
  single request. It also returned `str(exception)`, which for a connection failure
  contains the DSN. Now **503**, naming no driver, host or credential. And there were
  **no exception handlers at all** — FastAPI's default re-raises, which under `DEBUG=true`
  renders a traceback (file paths, library versions, sometimes query values) straight to
  the browser. Unexpected errors now return a generic message plus a request id, and are
  logged in full.
- **Revocable sessions** (migration 017, `backend/app/auth/sessions.py`). Refresh tokens
  were stateless JWTs, so logout deleted the client's copy and **nothing else** — a token
  captured beforehand kept minting sessions for the full seven days. On the shared school
  machines this product is used from, that is the whole threat. A refresh token now names
  a row in `refresh_sessions`: refreshing rotates it, logout revokes the family, and
  presenting an already-spent token revokes the **entire lineage** (a copy is in
  circulation; ending both halves beats silently continuing). Every refusal returns the
  same message, so a stolen token learns nothing about which kind it is. Access tokens
  stay stateless and short-lived — checking them per request would buy minutes at the
  cost of a query on every call.
- **Schema drift fixed** (same migration): `alembic check` failed for three separate
  reasons — migration 016 created `updated_at` on two counselor tables while the models
  used `TimestampMixin` (which declares only `created_at`, so `FullTimestampMixin` was
  introduced rather than dropping the columns); four indexes existed in the DB and in no
  model, so autogenerate proposed **deleting** them; and ~40 columns were `NOT NULL` in
  models but nullable in the DB, dating to migration 001, so `create_all` (what the tests
  use) and the migration chain produced different schemas. **CI now runs `alembic check`**,
  because a suite that builds its schema with `create_all` structurally cannot catch this.
- **Observability**: request ids (generated per request, echoed in the response, in every
  log line; a client-supplied id is accepted only if it is a short opaque token), plus
  Sentry on both sides — `backend/app/observability.py` and `src/lib/monitoring.ts`.
  **Absent DSN = disabled**, so development and CI never reach a production project.
  What is sent is deliberately narrow: this frontend renders counseling conversations,
  wellness scores and children's names, and an error report is not the place for any of it.
- **Frontend `ErrorBoundary`** mounted outermost in `App.tsx` — outside the router *and*
  the auth provider, so a crash in either still renders a fallback rather than a white screen.
- **Production config guards**: `ALLOWED_HOSTS`, `FORCE_HTTPS` (off by default — a container
  behind a TLS-terminating proxy sees `http://` internally and would redirect forever), and
  a CSP whose API origin is substituted at container start by
  `deploy/docker-entrypoint-frontend.sh`, which **refuses to boot without `API_ORIGIN`**:
  a CSP missing it blocks every call in the browser before it is sent, so server logs stay
  empty and the page simply does nothing. See `docs/production-configuration.md`.

### September 10, 2026 — Availability engine: recurring schedules + time-first booking
- **Counselors no longer hand-create slots** (migration 016, additive — nothing dropped).
  Every bookable time used to be a row in `counselor_availability`, so a counselor who
  forgot a week silently disappeared from the booking page. Now recurring weekly
  schedules (`counselor_schedules`, `counselor_schedule_exceptions`) that concrete slots
  are **derived** from; nothing is persisted, so a 9–5 week is five rows rather than
  thousands. `counselor_availability` is left in place and populated — **deprecated, not
  dropped**: those rows explain how existing bookings came to exist.
- **The database is now the authority on whether a time is free.**
  `counselor_sessions.ends_at` is the load-bearing addition — with only `scheduled_at`,
  "does 10:00–10:45 clash with 10:30–11:00?" could not be asked. An **EXCLUDE constraint**
  over `tstzrange(scheduled_at, ends_at)` makes overlapping live sessions impossible,
  enforced by Postgres rather than by whoever remembers to check; cancelled and no-show
  rows sit outside it so they stop consuming time. Where a host forbids `btree_gist` the
  migration logs loudly and falls back to an index, and the service can **report which
  mode it is in** rather than being quietly weaker than the box it was tested on.
- **Timezones**: a schedule's "09:00" is a claim about the counselor's morning, not a UTC
  instant, so recurring times are stored naive and interpreted in the counselor's IANA
  zone; everything downstream is UTC and the server's own timezone is never consulted.
  `tzdata` is now a declared dependency — `zoneinfo` carries no data of its own and
  Windows has no system database. Overnight schedules stay one row (`end_time <=
  start_time` runs past midnight).
- **Slot grid anchored to working hours, not to what bookings leave behind.** Found by
  opening the page: a counselor working 09:00–17:00 in 30-minute sessions was offering
  12:15, 12:45, 1:15. The generator subtracted booked time *first* and then walked each
  surviving interval from its own beginning, so one off-grid session re-anchored the whole
  rest of the day — the times a student was offered depended on who else had booked.
  Candidates are now generated on the **fixed** grid and then rejected if they intersect a
  booking plus its buffer (touching is fine, intersecting is not — same semantics as the
  DB constraint). Slightly fewer slots in exchange for predictability, which is the right
  trade for a page whose whole job is telling someone when they can be seen.
- **Booking is time-first** (`BookCounselor.tsx`). Was counselor-first: pick a person,
  then hope they had made a slot. Someone who needs to talk on Thursday evening has a
  *time* in mind, not a counselor — so the flow is date → time window → whoever is free,
  with "Any counselor" as the default rather than an option. **One component serves both
  students and parents** (the backend runs a single booking path, so forking the UI would
  give the same bug two places to live); parents get one extra step, which child, and the
  child id is verified server-side. A 409 refreshes availability and keeps the "just
  booked" banner up — the first version cleared it inside the refresh the 409 itself
  triggered, so the slot vanished with no explanation.
- **`CounselorAvailability.tsx` is now a weekly grid**: state the hours you work each
  weekday and Kio derives the slots. Multiple intervals per day, intervals disabled
  without being deleted, session settings (duration, buffer, timezone) and dated
  exceptions on the same screen — in the counselor's head they are one question.
  Timezone is an explicit choice, never inferred.
- New endpoints: `GET /counselors/availability/search`, `POST|GET|PUT|DELETE
  /counselors/schedules`, `.../exceptions`, `GET|PUT /counselors/settings`,
  `POST /counselors/sessions/{id}/cancel`. New client `src/lib/availability-api.ts`.

### September 9, 2026 — Logging that reaches a handler; the CORS trap behind "unable to connect"
- **App logs were being discarded.** Nothing configured the root logger and uvicorn
  configures only its own, so every `logger.*` call under `app/` propagated to a
  handler-less root and vanished. Two mattered: `auth/service.py` logs the
  email-verification link specifically so local development works with
  `EMAIL_PROVIDER=noop` (it never appeared, so verifying an email locally was impossible),
  and `email/service.py` logs delivery failures inside `try_send`, which deliberately
  never raises — **a production Resend outage was therefore completely silent**. `main.py`
  now configures the root logger and defers to an existing handler so pytest and gunicorn
  keep their own setup. pytest installing its own handler is exactly why the suite never
  caught this.
- **CORS**: the dev allowlist held only 5173/3000. Vite takes the next free port when its
  default is busy and binds IPv6 on some Windows setups, so a normal local session can
  present an origin of `localhost:5174` or `[::1]:5173`. Each drew a 400 on the preflight,
  the browser blocked the request, and axios surfaced `ERR_NETWORK` — which the login form
  rendered as "Unable to connect to server", sending you to restart a server that was
  running and answering. The allowlist now covers 3000/5173/5174/5175 across the
  `localhost`, `127.0.0.1` and `[::1]` forms (all loopback-only; production still
  overrides `CORS_ORIGINS` wholesale via env). Since a blocked preflight and an
  unreachable server are genuinely indistinguishable from JavaScript, `LoginSignup` now
  names **both** possibilities, the API URL it called, and the page origin.

### September 8, 2026 — Crisis alerts reach humans, Admin completed, consent layer
- **The crisis path now reaches a human.** `crisis.py` had been fanning out
  notifications since Phase 6 and **no frontend file read `/notifications`** — no bell,
  no page, no toast. Added `NotificationBell` (polling, paused on hidden tabs, optimistic
  read) mounted on all five signed-in surfaces via student/parent/counselor/school
  dashboards + `AdminLayout`. Plus **email escalation** to counselors and school admins
  (`crisis_alert_email`), because an in-app badge only reaches staff already signed in —
  out of school hours, nobody. Email is content-free: student name and tier only, never
  message text or categories, and **the subject omits the name** (lock-screen previews).
  Parent email is **off by default** (`crisis.email_parents`) — it cannot be unsent and can
  out a student; parents still get the content-free in-app notification. Mail failure can
  never swallow the queue entry.
- **8 stub Admin pages built**, `UnderConstruction.tsx` deleted. Dashboard (platform KPIs
  with unreviewed-risk first), Counselors + detail (verification gates the public booking
  directory, so it confirms), Risk Center + detail, AI Control (routing + prompt
  activation, which changes what Comrade says to every student — confirms), Settings
  (safety thresholds as validated JSON), and **Audit Logs** — whose `listAuditLogs` /
  `exportAuditLogsCsv` clients had existed unused since the P0 commit, making that
  backend work unreachable.
- **New: cross-tenant risk oversight** (`GET /admin/risk`, `/admin/risk/{id}`).
  `/risk/queue` filters on the *caller's* tenant, so a platform admin hitting it saw their
  own empty queue. Deliberately **read-only** — recording a verdict is a clinical judgment
  belonging to the counselor who owns the case. Ordered most-severe-then-oldest so stale
  rows surface; `age_hours` is server-computed so SLA flags don't depend on the browser clock.
- **Consent layer + age gate** (migration 015). Terms/Privacy were `href="#"` dead links
  with an unbound checkbox; there was no DOB and no record that anyone agreed to anything.
  Now: `users.date_of_birth` + `guardian_consent_status`, append-only `user_consents`
  (never updated — withdrawal stamps `revoked_at`, a new version writes a new row),
  IP/user-agent captured, and **policy versions** so a grant proves *what* was agreed to.
  Under 13 refused before a row is written; 13–17 created but `pending` until a guardian
  approves via emailed one-time link (one-shot, so a forwarded email can't flip it).
  **Google signup carries the same gate** — it verifies an email address, not an age.
- **Policy pages** `/terms` + `/privacy` (public), `/guardian-consent`, and a
  `GuardianConsentBanner` mounted once in `ProtectedRoute`. Enforcement is **soft** by
  design (banner, not a wall) — a blocked screen teaches a struggling 15-year-old that the
  thing they reached for doesn't work.
- ⚠️ **The policy documents are engineering drafts and carry a visible "pending legal
  review" banner.** They describe what the code actually does; they are not lawyer-reviewed
  and are not launch-sufficient. Two open questions are recorded in
  `app/consent/policy.py`: whether DPDP permits Kio's continuous behavioural monitoring of
  minors at all, and what counts as "verifiable" parental consent per jurisdiction.
- Tests: 8 admin-risk, 19 consent (incl. leap-day and boundary arithmetic), 4 crisis-email,
  7 notification-bell, 10 age-gate frontend.

### September 7, 2026 — Deployment artifacts + school analytics made real
- **The repo is now deployable.** There were previously no deployment artifacts of
  any kind. Added `backend/Dockerfile` (multi-stage, pinned `python:3.11.9-slim`,
  non-root, healthcheck), root `Dockerfile` (Vite build → nginx), `deploy/nginx.conf`,
  `docker-compose.yml` (+ `.env.docker.example`), `render.yaml` as a worked
  blueprint, and `docs/deployment.md` (env matrix, hosting options, **Postgres
  backup/restore policy**, rollback, smoke test, troubleshooting).
- **`alembic upgrade head` now actually runs somewhere.** `backend/docker-entrypoint.sh`
  migrates on boot (`RUN_MIGRATIONS`, default true) and supports `migrate` / `seed`
  subcommands; `seed` **refuses when `ENVIRONMENT=production`** (it creates demo
  accounts sharing one published password). `render.yaml` uses the release-job
  pattern instead, which is what >1 replica requires.
- **SPA rewrites shipped for every host** — `deploy/nginx.conf`, `public/_redirects`,
  `vercel.json`, `render.yaml` routes. Without these `/student`, `/verify-email` and
  `/reset-password` 404, which breaks emailed verification and password-reset links
  specifically. Rewrite (200), never redirect, so `?token=` survives.
- **`DATABASE_URL` normalisation** (`app/config.py`): Render/Railway/Heroku hand out
  `postgres://`, which SQLAlchemy routes to psycopg2 — not installed — so the app
  died at import with a `ModuleNotFoundError` naming neither the DB nor the driver.
  Now coerced to `postgresql+asyncpg://`; an explicit `+driver` is left alone.
- **Requirements exact-pinned** and split (`requirements.txt` runtime /
  `requirements-dev.txt` test). `.*` ranges meant a deploy could install a different
  tree than CI tested. `google-auth` added as a **declared** dependency — it is
  imported directly by `app/auth/google.py` but was only arriving transitively via
  `google-genai`. The `bcrypt==4.1.3` pin is documented as load-bearing for passlib.
- **CI**: new `migrations` job (applies 001→head on an empty DB and asserts a single
  head — the test suite builds schema from models via `create_all` and never
  exercises the chain), plus typecheck, frontend tests, and a `docker-build` job.
  Fixed `test_suspended_school_blocks_signup_and_login`, which 422'd on the now-required
  `phone` field before reaching its 403 assertion — the tenant-suspension gate had been
  silently untested.

- **School analytics are real numbers or no numbers.** Four of seven `AnalyticsOverview`
  fields were empty, hardcoded, or wrong: `stress_by_category` was never populated,
  `wellness_trend` read `analytics_snapshots` (written only by `seed.py`),
  `counselor_utilization` was a literal `0.0`, and `active_counselors` joined
  `counselor_profiles` on `users.tenant_id` — a relationship migration 008 replaced,
  so it returned ~0 for every school. Rebuilt on `wellness_scores`,
  `stress_distributions` (latest row per student, DISTINCT ON), and
  `counselor_school_assignments` / `counselor_sessions`. Added check-in participation
  from `wellness_records.mood_label`.
- **Small-cohort suppression** (`MIN_COHORT_SIZE = 10`): a school admin can see the
  roster, so "1 student at critical risk" in a tiny school names them. Below the floor
  every distribution is withheld and `cohort_suppressed` is set. Residual limitation
  documented in the service: single-student tiers above the floor are still returned.
- **"No data" is now distinct from zero** — `avg_wellness_score` and per-month trend
  scores are nullable. A month with no records renders as a gap, not a wellbeing collapse.
- **Timezone bug found by the new tests**: `date_trunc('month', <timestamptz>)`
  truncates in the *session* timezone, so on a non-UTC server (the test DB reports
  Asia/Calcutta) the current month bucketed to the previous month and the entire trend
  chart came back silently empty. Now `date_trunc('month', created_at AT TIME ZONE 'UTC')`.
- **`SchoolAdminDashboard` rewritten against the API.** The hardcoded `wellnessTrend` /
  `riskDistribution` / `stressByCategory` arrays are gone, along with the invented "Key
  Insights", "Recommended Actions" and a "Monthly Wellness Report" card citing 97% parent
  satisfaction — a metric that exists nowhere in the product. Real school name (new
  `school_name` on the overview), **working sign-out** (was a `<Link to="/">` leaving a
  valid JWT in localStorage — the same bug fixed on the counselor dashboard in August),
  sidebar nav scrolls to real sections instead of `href="#"`, plus loading/error/empty
  and suppressed states.
- Tests: 16 new in `backend/tests/test_analytics.py` (175 backend total) — the module
  previously had **zero** coverage, which is how the four broken fields survived.

### August 4, 2026 — Counselor dashboard: real identity, live sessions & notes
- **Sign-out bug fixed**: the counselor sidebar was a `<Link to="/">` with no handler, so
  "Sign Out" left a valid JWT in localStorage — on a shared school machine the next person
  could walk back in. Now calls `logout()` like the student/parent dashboards.
- **No more fake counselor**: the hardcoded `"Dr. Jennifer Martinez"` is replaced by the
  signed-in user from `useAuth()`.
- **Stats are real**: Active Students (roster length), Next 7 Days and Sessions Completed
  (from `/counselors/sessions`). "Avg Session Time" was **removed, not recomputed** —
  `counselor_sessions` has no duration column, so the old `45m` was unbackable.
- **Sessions & notes are live** (`CounselorSessions.tsx`, `ScheduleSessionDialog.tsx`,
  `src/lib/counselor-api.ts`): the mock `upcomingSessions` array is gone. Upcoming/past
  split, per-session status transitions, and lazily-loaded notes on expand. "Schedule
  Session" on a student card now works. The dead student-level "Add Note" button was
  dropped — notes attach to a session, so scheduling has to come first.
- **Sidebar nav works**: four `href="#"` links became in-page scroll targets
  (Students / Availability / Sessions & Notes / Risk Alerts).
- **Backend** (additive, no migration): `list_sessions` now joins `student_profiles → users`
  so `SessionResponse.student_name` is populated — it was always `null`, which would have
  rendered a list of blank names. `create_session` resolves the student first, returning
  404 instead of letting a bad id surface as a raw FK 500.
- Note: counselor **availability was already built and live** (`CounselorAvailability.tsx`);
  only the session lifecycle was missing.
- Tests: 9 new in `backend/tests/test_counselor_sessions.py` (158 backend total).

### August 4, 2026 — Go-live auth: real email delivery, verification & password reset
- **Email delivery is live** (`app/email/service.py`): `ResendEmailProvider` added behind the
  existing `EmailService` ABC — uses `httpx` (already a dependency), so **no new packages**.
  `EMAIL_PROVIDER=resend` + `RESEND_API_KEY`; a blank key or unknown provider degrades to
  `noop` (logs the link) instead of crashing. New `try_send()` never raises — a mail outage
  can't turn a successful signup into a 500. Templates in `app/email/templates.py`
  (plain-text + inline-styled HTML on the Kio palette; no webfonts).
- **Email verification completed**: signup now actually sends the link (via FastAPI
  `BackgroundTasks`, matching the chat hooks idiom, so mail latency never blocks the
  response). `POST /auth/verify` switched from a bare query param to a JSON body; new
  `POST /auth/verify/resend`. Frontend `/verify-email` landing page recovers from expired
  links instead of dead-ending.
- **Password reset** (new): `POST /auth/password/forgot` + `/auth/password/reset`, with
  `/forgot-password` and `/reset-password` pages. Forgot **always** returns the same
  response whether or not the account exists (no enumeration oracle). Reset links are
  genuinely **single-use with no new table** — the token carries a `pwf` fingerprint of the
  current `password_hash`, so it stops matching the moment the password changes. Google-only
  accounts (`password_hash IS NULL`) are told to use Google rather than failing opaquely.
  A completed reset also sets `is_verified` (it proves inbox control).
- **Soft enforcement**: `is_verified` added to `UserResponse` (additive) and surfaced as an
  amber `VerifyBanner` mounted **once inside `ProtectedRoute`** — every signed-in surface
  gets it from one place. Nothing is blocked while unverified; dismissal is per session.
  `refreshUser()` added to the auth context so the banner clears without a re-login.
- **No migration** — `users.is_verified` already existed. New settings: `RESEND_API_KEY`,
  `EMAIL_FROM`, `EMAIL_REPLY_TO`, `FRONTEND_URL`, `EMAIL_VERIFY_TOKEN_HOURS`,
  `PASSWORD_RESET_TOKEN_HOURS`.
- **Google sign-in needed no code** — it was already complete and env-gated; see the new
  `docs/domain-google-auth-and-email.md` runbook (domain → Resend SPF/DKIM/DMARC → Google
  Console origins → prod env matrix → smoke test → troubleshooting).
- Tests: 21 new in `backend/tests/test_auth_email.py` (149 backend total) + 7 frontend.

### August 3, 2026 — Safety hardening + counselor verdict capture (trust & evaluation)
- **Chat/signup UX** (prior pass): mobile+email format validation (front + back, E.164-ish
  phone), Comrade replies render Markdown (`react-markdown`), optimistic user message +
  typewriter reveal (`ChatMessage.tsx`).
- **Server-side safety floor** (`intelligence/analysis.py`): a credible `self_harm` /
  `suicidal_ideation` / `abuse` category score forces overall risk to at least
  `enforced_overall` **before** the level is derived — an under-scored aggregate can no
  longer mask acute risk (prompt guidance is now a code guarantee). Protective factors
  never lower risk (they only move the wellness score). Thresholds live in
  `platform_config.safety_floors` (DB-first, code fallback) — tunable from Admin with no deploy.
- **Hinglish hard/soft tripwire** (`ai/safety.py`): patterns restructured to
  category→severity→regex across 8 categories with English + romanized-Hindi + misspellings.
  **Hard** (explicit) trips the instant counselor tripwire; **soft** (hyperbole-prone, e.g.
  "sab khatam") is logged as `safety_soft_signal:*` but never alerts — the LLM (which sees the
  raw text) weighs it. Explicit violence now also trips. `detect_safety_events` back-compat kept.
- **Counselor review UI** (`RiskQueue.tsx`): surfaces AI contributors (top risk categories),
  confidence %, and an "Inconclusive" badge (confidence below `min_confidence`); shows the
  response SLA per level and an emergency-escalation checklist for critical.
- **Verdict capture** (migration 014, all-nullable / backward compatible): new
  `counselor_risk_level` / `verdict` (agree|disagree) / `outcome` on `risk_assessments`
  (comments reuse `resolution_note`). Counselors record their own level + outcome on resolve,
  building an AI-vs-human labeled dataset from day one (audit-logged with structured details).
  `RiskReviewUpdate` extended (only `review_status` required); `RiskQueueItem` gains
  `confidence`/`inconclusive`.
- **Non-diagnostic disclaimer** (`Disclaimer.tsx`) on login + student/parent/counselor/school
  dashboards; **SLA + escalation** single source of truth in `src/lib/risk-sla.ts` and
  `docs/safety-sla-and-escalation.md`.

### July 11, 2026 — Phase 7: Production-MVP Polish (12h check-in windows, persistent activities, parent dashboard v4)
- **Check-in v2**: 12-hour UTC windows (AM/PM); mandatory modal when the window has no
  check-in; max 2 submissions per window (initial + one update, both stored as rows,
  latest = current mood, 409 after). 5-point display scale (😄 Very Happy → 😞 Very Low)
  over the same stable API identifiers. Status endpoint now returns `updates_remaining`,
  `window_ends_at`, `checkin.created_at` (additive). Chat page shows a Current Mood card
  (mood + last updated + Update button / "already updated" state) — old 3-mood selector removed.
- **Persistent activity engine** (migration 012, `student_activities`): weekly set (6, LLM
  w/ catalog fallback) generated once per ISO week + 1 deterministic daily pick; no repeats
  within 21 days; completions persist (`Completed ✓`, 409 on double-complete); catalog
  expanded to ~26 items. Activities feed a new `activity_completion` wellness component.
- **Wellness engine**: formula fully documented in `app/intelligence/wellness.py` docstring;
  new components `activity_completion` + `mood_recovery` (config shallow-merge surfaces
  them over older DB weight rows); ±15-point smoothing clamp per recalc.
- **Parent insights (additive fields)**: `weekly_mood_summary` (replaces per-day calendar
  for parents — daily icons stay private to the student), `wellbeing_dimensions` (10 radar
  dims from real signals), stress factors blended from LLM distribution + check-in reasons +
  risk categories, `protective_factors`/`risk_factors` from the insight prompt.
- **Parent dashboard v4**: tabs (Overview / Recommendations / Family Activities); premium
  summary hero (score, trend, risk, emotional state, period delta); smoothed trend with
  custom tooltips; weekly mood summary card; large 10-dim radar; dated risk timeline with
  movement arrows; readable recommendation cards; "Why am I seeing this?" transparency card.
- **Student**: mood calendar modal (monthly, emoji, own notes) on the dashboard mood card;
  polished wellness card row; "Complete Today's Check-in" nudge card fallback.
- Tests: 118 backend + 7 frontend (window rules, persistence, no-repeat, update mode).

### July 11, 2026 — Phase 6 Group G: Wellness Intelligence Engine (check-in, reports, activities)
- **Mandatory daily check-in**: full-screen non-dismissible modal after login (5-emoji mood +
  10 reason chips + optional reflection), once per calendar day (`POST /wellness/checkin`
  409s after; `GET /wellness/checkin/today` gates the dashboard). Stored on `wellness_records`
  via new nullable columns `mood_label`/`mood_reason`/`reflection` (migration 011). The legacy
  one-tap `POST /wellness/mood` keeps updating sentiment during the day without touching the
  official check-in.
- **Mood calendar**: `GET /wellness/mood-calendar?month=` (student, with reasons) and
  `GET /parents/children/{id}/mood-calendar` (labels only — reasons/reflections stay private).
- **Weekly AI reports** (`app/intelligence/reports.py`, feature `weekly_report`): role-appropriate
  student/parent/counselor versions, cached per ISO week in new `weekly_reports` table,
  deterministic fallback when no LLM. Endpoints on wellness/parents/counselors routers.
- **Personalized activities** (`app/intelligence/activities.py`, feature `activities`):
  LLM-generated from aggregated signals with a deterministic signal-aware catalog fallback;
  `POST /wellness/activities/complete` logs to the student timeline. New `/student/activities`
  page (activities + weekly summary + personal insights).
- **Personal insights** (`app/intelligence/personal_insights.py`): deterministic pattern mining
  (weekday moods, reason correlations, 14-day trend, persistent stress source, streaks) gated
  on ≥7 check-in days; `GET /wellness/insights`.
- **Parent dashboard v3**: AI weekly summary card, 7/30/90-day wellness trend
  (`GET /parents/children/{id}/wellness-trend?days=`), monthly mood calendar, wellbeing radar
  (score components), risk timeline strip, expanded "Why this score?" (contribution bars +
  last-updated + confidence), positive changes / areas needing attention, and LLM-tailored
  `family_communication` + `family_activities` (added to the parent-insight prompt/payload).
- **Counselor dashboard**: student roster now live from `GET /counselors/students`; per-student
  on-demand weekly AI report.
- Tests: 117 backend (20 new in `test_phase6_wellness.py`) + new vitest setup with 6 frontend
  tests for the check-in modal (`npm test`).

### July 11, 2026 — MindBridge → Kio Rebrand
- Product renamed **MindBridge → Kio** across frontend, backend, and docs, using the
  brand kit in `Rebranding/` (navy `#232B6D`, teal `#31D7C2`, blue `#5A6BFF`; Poppins
  headings + Inter UI). AI companion remains **Comrade**.
- New `KioLogo` wordmark component replaces the Brain-icon headers; `public/favicon.svg`
  + browser title/meta/OG tags added; theme tokens (light + dark) rebuilt on the Kio palette.
- **Unchanged for backward compatibility:** DB names (`mindbridge`, `mindbridge_test`),
  seed emails (`admin@mindbridge.ai`) and demo password, localStorage token keys
  (`mindbridge_*`), invite-code format (`MB-XXXX`), dev JWT secret string, API routes/schema.

### July 2026 — Phase 4 (Security) & Phase 5 (Auth, Onboarding, Platform)
**Phase 4 — architecture review + P0/P1 fixes:**
- Provider-agnostic AI layer (AIProvider / AIProviderFactory / AIRouter, DB-driven routes,
  fallback, retry, usage logging + cost) — Gemini implemented; adding Claude/OpenAI/Ollama
  is one provider file + registry line.
- Async Gemini call (`client.aio`); self-signup restricted to student/parent; server-controlled
  `sender_type`/metadata; JWT prod-secret startup guard; background title/memory hooks; safety
  logs on their own committed session; rate limiting; per-student daily AI budget; email lowercasing.
- **AI Playground** (`/admin/playground`) and **Platform Admin** dashboard (`/admin`): school
  registration, seats, subscriptions, break-glass chat access (audit-logged).

**Phase 5 — Google Auth, Onboarding, Guardians, Platform Counselors & Admin:**
- **Google Sign-In** (GIS ID-token flow, `google-auth`; no new dep): `/auth/google` +
  `/auth/google/complete`. Same JWT; new users provide only mobile + institution code.
  Fully env-driven — app works with no credentials (button hidden, endpoint 503).
  `users.google_sub` + `auth_provider`; `password_hash` nullable (migration 007).
- **Student onboarding** (5-question wizard on first login): `app/onboarding` + `student_onboarding`
  table; responses injected into the Comrade system prompt for personalization.
- **Guardian management** (student-managed on `/student/family`): `student_guardians` table, CRUD,
  one-primary constraint, per-guardian invite code reusing the row-locked redeem flow.
  `EmailService` interface + Noop provider (future Resend/SendGrid/SES/SMTP).
- **Platform-wide counselors** (migration 008): counselors belong to the Kio platform, not a
  school. `counselor_availability` slots; `GET /counselors/directory`, `/slots`, `POST /book`
  (row-locked). Any student/parent from any school can book any verified counselor.
- **Expanded Platform Admin** (migration 009): counselor register/verify/activate, user
  disable/reset-password, tenant delete, AI model routing per feature
  (chat/memory/title/risk/parent_insight), and cross-tenant platform analytics.
- Migrations 007–009 (never editing prior ones). 41 passing tests.

### June 12, 2026 — Initial Setup
- **Source:** Figma Make export from [Figma Design](https://www.figma.com/design/mouUmFRhGjj5mOwiUKrohb/Design-MindBridge-SaaS-App)
- **Changes to make it runnable:**
  1. Moved `react` + `react-dom` from `peerDependencies` → `dependencies`
  2. Added `@types/react`, `@types/react-dom`, `typescript` to `devDependencies`
  3. Created `tsconfig.json` (missing from Figma export)
  4. Added Inter font to `fonts.css` (was empty)
  5. Created this `claude.md` context file

### June 14, 2026 — Backend API Implementation
- **Full FastAPI backend** created at `backend/`
- **Database:** 27 PostgreSQL tables via SQLAlchemy 2.0 async models
- **Auth:** JWT (access + refresh tokens) with bcrypt password hashing
- **RBAC:** Role-based access control (student, parent, counselor, school_admin, admin)
- **Multi-tenancy:** Row-level isolation via `tenant_id` in JWT
- **12 API modules:** auth, users, conversations, memory, wellness, risk, parents, counselors, analytics, notifications, subscriptions, admin
- **60+ API endpoints** with Pydantic v2 schemas
- **Alembic migrations** for schema versioning
- **Seed data** matching frontend mock values (Riverside High School)
- **Tests:** pytest + httpx async test suite
- **Documentation:** Swagger UI, ReDoc, markdown API reference

### Current State

**Shipped end to end** (backend + UI both real, no mock data):
- Auth: email/password, Google Sign-In, email verification, password reset,
  **revocable refresh sessions** (migration 017), RBAC, multi-tenancy
- Consent layer + age gate (under-13 refused, 13–17 guardian-approved), policy pages
- Comrade AI chat (Gemini 2.5 Flash) with DB-first prompt versioning, memory hooks,
  per-student daily budget, safety tripwires
- Wellness: 12-hour check-in windows, mood calendar, persistent weekly activities,
  personal insights, weekly AI reports
- Risk: server-side safety floor, counselor risk queue, verdict capture,
  crisis notifications (in-app bell + email escalation)
- Counselors: recurring availability engine, time-first booking, sessions + notes
- Parent dashboard v4, school analytics with small-cohort suppression
- Platform admin: all 9 pages, cross-tenant risk oversight, audit logs, AI routing
- Deployment: Dockerfiles, compose, nginx, `render.yaml`, CI (tests, `alembic check`,
  typecheck, frontend tests, docker build), Sentry + request ids
- Audit trail: append-only (DB-enforced), request-correlated, content-minimal,
  platform-admin only, streamed CSV export — see `docs/audit-logging.md`

**Numbers:** 29 frontend routes · 20 backend modules · 47 tables · 18 migrations ·
370 backend tests · 42 frontend tests

**Known gaps** — see Next Steps below.

---

## 🖥️ Backend Architecture

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| Database | PostgreSQL 15+ (async via asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.14 |
| Validation | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt |

### Backend Structure
```
backend/
├── app/
│   ├── config.py           # pydantic-settings
│   ├── dependencies.py     # Auth, RBAC, tenant deps
│   ├── auth/               # JWT signup/login/refresh
│   ├── users/              # Profile CRUD
│   ├── conversations/      # ChatGPT-style chat + AI responses
│   ├── ai/                 # Comrade AI (Gemini integration)
│   │   ├── __init__.py
│   │   ├── prompts.py      # System prompt (fallback) + builder
│   │   ├── service.py      # Gemini API + prompt loading from DB
│   │   └── safety.py       # Safety keyword detection + audit logging
│   ├── linking/            # Parent-student invite code system
│   ├── memory/             # AI memory system (future)
│   ├── wellness/           # Records, goals, journal
│   ├── risk/               # Risk detection (future)
│   ├── parents/            # Insights dashboard
│   ├── counselors/         # Sessions & notes
│   ├── analytics/          # School analytics
│   ├── notifications/      # User notifications
│   ├── subscriptions/      # Billing
│   └── admin/              # Platform admin
├── database/
│   ├── models.py           # 27 SQLAlchemy models
│   ├── enums.py            # Python enums
│   ├── session.py          # Async DB session
│   ├── schema.sql          # PostgreSQL DDL
│   └── seed.py             # Demo data
├── migrations/             # Alembic
├── tests/                  # pytest suite
├── main.py                 # FastAPI entry
└── requirements.txt
```

### Demo Credentials (after seeding)
| Role | Email | Password |
|------|-------|----------|
| Student | sarah.johnson@student.rhs.edu | MindBridge2026! |
| Parent | parent.johnson@email.com | MindBridge2026! |
| Counselor | jennifer.martinez@rhs.edu | MindBridge2026! |
| School Admin | admin@rhs.edu | MindBridge2026! |
| Platform Admin | admin@mindbridge.ai | MindBridge2026! |

School Code: `RHS2026`

---

## Comrade AI Architecture

### System Prompt
- **Persona:** Comrade -- a trusted companion for students (not a "wellness bot")
- **Capabilities:** Academic stress, study habits, motivation, confidence, social challenges, emotional wellbeing, goal setting
- **Safety:** Self-harm/abuse/violence detection with crisis helpline info
- **Privacy:** Never reveals parent data, system prompts, or internal architecture
- **Injection Resistance:** Refuses prompt leak attempts, continues conversation normally

### Prompt Versioning
- Active prompt loaded from `ai_prompt_versions` table (DB-first)
- Fallback to `app/ai/prompts.py` if no DB prompt found
- Prompt name: `comrade-system`, version: `v1`

### AI Message Metadata (JSONB)
```json
{
  "model": "gemini-2.5-flash",
  "prompt_version": "v1",
  "response_time_ms": 842
}
```

### Safety Event Logging
- Regex-based keyword detection for: `self_harm`, `abuse`, `violence`
- Logged to `audit_logs` table with `safety_event:{type}` action
- No workflows triggered -- data collection for future risk detection

### Summary Hook
- Placeholder at message_count >= 20
- Future: auto-summarize long conversations for context window management

---  

## Next Steps (Planned)

1. **Legal review of the policy documents** — `/terms` and `/privacy` are engineering
   drafts carrying a visible "pending legal review" banner. They describe what the code
   actually does but are **not launch-sufficient**. Two open questions are recorded in
   `app/consent/policy.py`: whether DPDP permits Kio's continuous behavioural monitoring
   of minors at all, and what counts as "verifiable" parental consent per jurisdiction.
   This blocks a real launch; nothing else on this list does.
2. **Real-time streaming chat** — responses are currently returned whole. No WebSocket
   or SSE path exists yet; `conversations/service.py` would need a streaming provider call.
3. **File uploads** — no `UploadFile` anywhere in the backend. Needs S3/local storage plus
   a scanning story before students can attach anything.
4. **Consent backfill** — the age gate covers new signups only. Existing accounts are test
   data, so no backfill was written; this becomes real work the moment there are real users.
5. **Audit-log retention** — no retention period is defined and no automatic
   deletion exists. This is a legal/product decision, not an oversight: it turns
   on the same unanswered DPDP questions as item 1, plus whether audit records
   about a student are in scope for an erasure request. Do not add a retention
   job or purge endpoint until a period is agreed. Note the append-only trigger
   means any purge must ship as a migration that drops it, deletes, and
   reinstalls it — awkward by design.
6. **Retire `counselor_availability`** — deprecated by the availability engine but left
   populated because those rows explain how existing bookings came to exist. Droppable once
   no live booking references them.
7. **`test_phase4.py`** at the backend root is a live-server script, not a unit test: it
   hits `localhost:8000` at import and breaks a bare `pytest`. CI runs `pytest tests/`, so
   it is invisible there. Move it under a marker or into `scripts/`.

Before implementing any feature:

1. Review existing architecture.
2. Look for simpler solutions.
3. Consider scalability.
4. Consider security.
5. Consider backward compatibility.
6. Consider cost optimization.
7. Explain the plan.
8. Wait for approval.
9. Then implement.

Do not make architectural changes without explaining why.
Prefer minimal diffs over large rewrites.
Maintain production-quality code.