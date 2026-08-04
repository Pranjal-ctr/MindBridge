# Kio SaaS App — Project Context

> **Last Updated:** July 11, 2026
> **Status:** Phase 5 Complete + Kio Rebrand -- Google Auth, Onboarding, Guardians, Platform Counselors & Admin

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

| Path             | Component              | Description                          |
|------------------|------------------------|--------------------------------------|
| `/`              | LandingPage            | Public marketing/landing page        |
| `/login`         | LoginSignup            | Auth (login/signup with role select) |
| `/student`       | StudentDashboard       | AI chat + mood tracking              |
| `/parent`        | ParentDashboard        | Child's wellness insights            |
| `/counselor`     | CounselorDashboard     | Student profiles + AI summaries      |
| `/school`        | SchoolAdminDashboard   | School-wide anonymized analytics     |
| `/book-counselor`| BookCounselor          | Counselor session booking            |

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
- Phase 1 (Auth + Student Dashboard + Chat) -- COMPLETE
- Phase 2 (Phone Collection + Parent Linking) -- COMPLETE
- Phase 3 (Comrade AI with Gemini 2.5 Flash) -- COMPLETE
- Frontend design pages exported and runnable
- 8 pages/routes implemented (including /student/family)
- FastAPI backend with 13 modules (including AI)
- PostgreSQL schema (27+ tables) + SQLAlchemy models
- JWT authentication + RBAC + multi-tenancy
- Gemini 2.5 Flash integration via google-genai SDK
- Comrade system prompt with safety/privacy/injection resistance
- AI message metadata (model, prompt_version, response_time_ms)
- DB-first prompt versioning with code fallback
- Safety event logging (audit_logs)
- Parent invite code system (MB-XXXX format, 48h TTL)
- Counselor + School Admin dashboards (frontend static, backend ready)
- Analytics module (backend ready)

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

1. **Counselor Dashboard Integration** -- Connect React to counselor API (students, sessions, notes)
2. **School Admin Dashboard Integration** -- Connect React to analytics API
3. **AI Memory System** -- Persistent student context across conversations
4. **Risk Detection** -- Automated workflows from safety events
5. **Real-time WebSocket Chat** -- Streaming AI responses
6. **File Uploads** -- S3/local storage for attachments
7. **Email Notifications** -- Verification and alerts


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