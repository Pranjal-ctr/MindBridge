# Kio

Kio is a mental wellness platform built for schools. Students get a private AI companion to talk to, parents get a summary of how their kid is doing (never the actual conversations), counselors get a queue of students who might need attention, and school admins get anonymized, school-wide analytics.

It's a full-stack app: a React/TypeScript frontend and a FastAPI/PostgreSQL backend, with an AI layer built around Google Gemini that's designed to swap providers without touching the rest of the codebase.

---

## How it's meant to work

- **Students** chat with "Comrade," an AI companion tuned for academic stress, motivation, and emotional support. Every conversation is analyzed in the background for wellness signals and, where warranted, risk flags — without the student's message ever being read by a human unless it's escalated.
- **Parents** don't see raw chat logs. They see aggregated insights: mood trends, wellness scores, and recommendations generated from the underlying data.
- **Counselors** work from an AI-generated queue of students flagged for review, plus booking/availability tools, rather than reading every conversation manually.
- **School admins** see anonymized, school-wide analytics — no individual student data.
- **Platform admins** manage schools, counselor verification, AI model routing per feature, and break-glass access (audited) across the whole platform.

---

## Tech stack

**Frontend**
- React 18 + TypeScript, built with Vite
- React Router for navigation
- Tailwind CSS v4 + shadcn/ui (Radix primitives)
- Recharts for dashboards, Motion for animation

**Backend**
- FastAPI (async) on Python 3.11+
- PostgreSQL via SQLAlchemy 2.0 (async) + asyncpg
- Alembic for migrations
- JWT auth (python-jose) with bcrypt password hashing, role-based access control, and row-level tenant isolation

**AI**
- Google Gemini 2.5 Flash by default, called through a provider-agnostic layer (`AIProvider` / `AIProviderFactory` / `AIRouter`) so adding Claude, OpenAI, or a local Ollama model is a matter of writing one provider file, not rewiring the app
- Per-feature model routing (chat, memory, title generation, risk scoring, parent insights can each use a different model)
- Usage logging with token counts and cost tracking

---

## Project layout

```
Kio/
├── src/                          # Frontend
│   ├── app/
│   │   ├── App.tsx               # Routes
│   │   └── components/
│   │       ├── LandingPage.tsx
│   │       ├── LoginSignup.tsx
│   │       ├── StudentDashboard.tsx
│   │       ├── StudentOnboarding.tsx
│   │       ├── StudentGrowthProfile.tsx
│   │       ├── StudentInviteCode.tsx      # guardian/invite management
│   │       ├── ParentDashboard.tsx
│   │       ├── CounselorDashboard.tsx
│   │       ├── CounselorAvailability.tsx
│   │       ├── BookCounselor.tsx
│   │       ├── RiskQueue.tsx
│   │       ├── SchoolAdminDashboard.tsx
│   │       ├── PlatformAdminDashboard.tsx
│   │       ├── AdminPlayground.tsx        # AI prompt/model testing tool
│   │       └── ui/                        # shadcn/ui primitives
│   ├── hooks/                    # useConversations, useMemory, useWellnessScore, useChildInsights...
│   └── lib/                      # api client, auth context, route guards, types
│
├── backend/
│   ├── main.py                   # FastAPI app, router registration
│   ├── database/
│   │   ├── models.py              # SQLAlchemy models
│   │   └── schema.sql
│   ├── migrations/versions/       # Alembic migrations, 001 → 010
│   └── app/
│       ├── auth/                  # signup, login, JWT, Google Sign-In
│       ├── users/
│       ├── conversations/         # chat + AI responses
│       ├── ai/                    # provider-agnostic AI layer, Comrade prompts, safety detection
│       ├── memory/                # persistent AI memory per student
│       ├── wellness/               # wellness scoring, mood tracking
│       ├── risk/                  # risk detection + counselor review queue
│       ├── parents/                # insights dashboard
│       ├── counselors/             # sessions, availability, booking
│       ├── linking/                # parent-student invite codes, guardians
│       ├── onboarding/             # student onboarding wizard
│       ├── analytics/              # school + cross-tenant analytics
│       ├── notifications/
│       ├── subscriptions/
│       ├── email/                  # email provider interface (Noop by default)
│       └── admin/                  # platform admin: schools, counselors, model routing
│   └── tests/
│
└── guidelines/                    # design system notes
```

---

## Getting it running locally

You'll need Node 18+, Python 3.11+, PostgreSQL 15+, and a Gemini API key ([free tier here](https://aistudio.google.com/apikey)).

**1. Clone and install the frontend**

```bash
git clone <repository-url>
cd Kio
npm install
```

**2. Set up the backend**

```bash
cd backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/mindbridge
JWT_SECRET_KEY=some-long-random-string     # e.g. python -c "import secrets; print(secrets.token_hex(32))"
GEMINI_API_KEY=your-gemini-api-key
CORS_ORIGINS=["http://localhost:5173"]
```

**3. Create the database and run migrations**

```sql
CREATE DATABASE mindbridge;
```

```bash
alembic upgrade head
```

**4. Run both halves**

```bash
# backend/, venv activated
uvicorn main:app --reload --port 8000

# project root, separate terminal
npm run dev
```

Frontend: `http://localhost:5173`
API docs: `http://localhost:8000/docs`

---

## Signing up

There's no seed script wired into the default flow — create accounts through `/login` → Sign Up. Students, parents, and school admins need a school/tenant code; parents additionally need an invite code generated by their linked student from `/student/family`. Counselors are registered platform-wide by a platform admin, not through self-signup.

---

## A few things worth knowing about the AI layer

- **Comrade**'s system prompt is loaded from the database first (`ai_prompt_versions` table), falling back to the version checked into `app/ai/prompts.py` if nothing's set. This lets prompts be updated without a deploy.
- Messages are scanned for self-harm, abuse, and violence keywords. Matches get logged to `audit_logs` — nothing is auto-escalated from a keyword hit alone; that's handled by the separate wellness/risk pipeline that runs after each message.
- The AI never has access to raw account credentials, other students' data, or its own system prompt — it's built to refuse and continue naturally if someone tries to extract it.
- Per-student daily AI usage is budget-capped to control cost.

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | asyncpg connection string |
| `JWT_SECRET_KEY` | yes | must not be left as a default in production — there's a startup guard for this |
| `GEMINI_API_KEY` | yes | from Google AI Studio |
| `CORS_ORIGINS` | yes | JSON array of allowed origins |
| `GEMINI_MODEL` | no | defaults to `gemini-2.5-flash` |
| `DEBUG` | no | defaults to `true` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | defaults to `30` |
| `GOOGLE_CLIENT_ID` | no | enables Google Sign-In; button/endpoint stay disabled without it |

Full list in `backend/.env.example`.

---

## Consent, the age gate, and the policy documents

Kio processes mental-health data belonging largely to minors, so signup is gated:

- **Under 13** — refused outright, before any row is written.
- **13–17** — the account is created but held at `guardian_consent_status="pending"`
  until a parent approves via a one-time emailed link. Enforcement is a persistent
  banner rather than a hard block; see `GuardianConsentBanner` for why.
- **18+** — consents for themselves.

Google sign-in carries the same gate: it verifies an email address, not an age.

Consent is recorded in `user_consents`, append-only and versioned against the
published policy version, with IP and user agent. Withdrawing stamps `revoked_at`;
a new policy version writes a new row. Thresholds and versions live in one place,
`backend/app/consent/policy.py`, mirrored for the client in `src/lib/policy.ts`.

> ⚠️ **The Terms of Service and Privacy Policy in this repo are engineering drafts.**
> They accurately describe what the code does with data, and they render with a
> visible "pending legal review" banner. They have **not** been reviewed by a lawyer
> and are not sufficient for launch. Two questions need counsel before serving real
> minors — both recorded in `app/consent/policy.py`:
>
> 1. India's DPDP Act restricts behavioural monitoring of under-18s. Kio does
>    continuous wellness scoring and risk detection on minors. Whether that is
>    permitted, and under what conditions, is the largest open legal question about
>    this product.
> 2. What counts as *verifiable* parental consent per jurisdiction. Email
>    confirmation is what is implemented; it is not sufficient everywhere.

---

## Migrations

```bash
alembic upgrade head              # apply everything
alembic current                   # check where you are
alembic revision --autogenerate -m "description"
alembic downgrade -1               # roll back one step
```

Migrations are never edited after the fact — each change is a new numbered file (currently `001` through `014`, covering the initial schema through Google auth/onboarding, platform-wide counselors, AI routing config, the wellness/risk intelligence layer, the admin dashboard, and counselor verdict capture).

---

## Deployment

Full runbook — environment matrix, hosting options, backups, rollback, smoke
test: **[docs/deployment.md](docs/deployment.md)**.

The whole stack in one command:

```bash
cp .env.docker.example .env       # fill in POSTGRES_PASSWORD, JWT_SECRET_KEY, ...
docker compose up --build
```

Web on `:8080`, API on `:8000`. The API container runs `alembic upgrade head`
on start.

| Artifact | What it's for |
|---|---|
| `backend/Dockerfile` | API image. Migrations run via `docker-entrypoint.sh`. |
| `Dockerfile` | Frontend build → nginx. |
| `deploy/nginx.conf` | SPA rewrite + cache/security headers. |
| `docker-compose.yml` | Single-box stack (Postgres included). |
| `render.yaml` | Worked Render blueprint: managed Postgres, pre-deploy migrations, static frontend. |
| `public/_redirects`, `vercel.json` | SPA rewrites for Netlify/Cloudflare and Vercel. |

Three things that catch people out, covered in detail in the runbook:

- **Deep links need an SPA rewrite.** `/student`, `/verify-email` and
  `/reset-password` have no file on disk. Without an `/index.html` fallback
  they 404 — and emailed verification and password-reset links land on exactly
  those paths.
- **`VITE_*` are baked in at build time.** Changing the API URL means a
  rebuild, not a restart. Never put a secret behind that prefix.
- **`WEB_CONCURRENCY` stays at 1** until rate limiting and the background
  pipeline move off in-process state.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
Run `uvicorn` from inside `backend/`, not the project root.

**`asyncpg.exceptions.ConnectionDoesNotExistError`**
PostgreSQL isn't running, or `DATABASE_URL` is wrong.

**Gemini `RESOURCE_EXHAUSTED`**
You've hit the free tier's daily quota (20 requests/day at time of writing). Wait it out or move to a paid tier.

**Frontend requests failing with a CORS error**
Add your frontend origin to `CORS_ORIGINS` in `backend/.env`.

**Alembic: "Can't locate revision"**
A migration's `down_revision` doesn't match the previous file's revision ID. Check the chain hasn't been broken.

**PowerShell won't run `Activate.ps1`**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## License

Proprietary. All rights reserved.
