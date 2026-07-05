# MindBridge SaaS App — Project Context

> **Last Updated:** June 25, 2026
> **Status:** Phase 3 Complete -- Comrade AI Integration (Gemini 2.5 Flash)

---

## 📋 Project Overview

**MindBridge** is an AI-driven SaaS platform that supports **student wellness** and **parenting guidance**. It offers personalized insights and resources for emotional health and academic success.

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

## 🎨 Design System

### Colors (CSS Variables in `theme.css`)
- **Primary:** `#2563EB` (Blue 600)
- **Secondary:** `#6366f1` (Indigo 500)
- **Accent:** `#10b981` (Emerald 500)
- **Destructive:** `#ef4444` (Red 500)
- **Wellness Colors:** Green, Blue, Purple, Pink, Amber
- Full dark mode support via `.dark` class

### Typography
- **Font:** Inter (Google Fonts)
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
