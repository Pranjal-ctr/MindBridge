# Kio — Deployment Runbook

How to get Kio into production, what to set, how to back it up, and how to get
back out when a release goes wrong.

Domain, Google OAuth and email-sender setup are a prerequisite for a working
deploy and live in their own guide: **[domain-google-auth-and-email.md](./domain-google-auth-and-email.md)**.

---

## 1. What gets deployed

Three pieces, deployable independently:

| Piece | Artifact | Notes |
|---|---|---|
| **API** | `backend/Dockerfile` → FastAPI on uvicorn | Stateless. Owns migrations. |
| **Web** | `Dockerfile` → static bundle (nginx image, or any static host) | Build-time config. Needs SPA rewrites. |
| **Database** | Managed PostgreSQL 15+ | The only stateful component. |

The API is stateless *with two asterisks* — see [§8 Known limits](#8-known-limits-at-mvp-scale)
before scaling it past one instance.

---

## 2. The three things that break first deploys

Read these before anything else; they account for most first-attempt failures.

**1. Deep links 404 on the frontend.** Kio uses `BrowserRouter`, so `/student`,
`/verify-email` and `/reset-password` are client-side routes with no matching
file on disk. A static host must rewrite *all* unmatched paths to `/index.html`,
with a **200 rewrite, not a redirect** — the original URL has to survive so
React Router can read `?token=` off it. Password-reset and email-verification
links land on exactly these paths, so getting this wrong breaks account
recovery specifically.

Config is provided for every common host — you need whichever matches yours:

| Host | File |
|---|---|
| nginx / Docker image | `deploy/nginx.conf` (`try_files $uri $uri/ /index.html`) |
| Netlify, Cloudflare Pages | `public/_redirects` |
| Vercel | `vercel.json` |
| Render static site | `routes:` block in `render.yaml` |

**2. `VITE_*` are compiled in, not read at runtime.** They are baked into the
JS bundle at build time. Changing `VITE_API_BASE_URL` requires a **rebuild and
redeploy**, not a restart. A corollary that matters: never put a secret in a
`VITE_*` variable — everything under that prefix ships to the browser.

**3. `postgres://` vs `postgresql+asyncpg://`.** Render, Railway, Heroku and Fly
all hand you a `postgres://` URL. SQLAlchemy routes that to psycopg2, which is
not installed, so the app dies at import with a `ModuleNotFoundError` that says
nothing about the database. `app/config.py` rewrites the scheme automatically,
so the platform's URL can be wired straight through — but if you see that error
on another host, this is why.

---

## 3. Environment variables

### API (required)

| Variable | Notes |
|---|---|
| `DATABASE_URL` | `postgres://` and `postgresql://` are normalised to asyncpg automatically. |
| `JWT_SECRET_KEY` | `openssl rand -hex 32`. **The app refuses to start in production if left at the dev default** — an intentional guard in `app/config.py`. |
| `ENVIRONMENT` | Set to `production`. Arms the guard above. |
| `CORS_ORIGINS` | JSON array of exact frontend origins, e.g. `["https://app.kio.com"]`. Scheme and port included; no trailing slash. |
| `FRONTEND_URL` | Public origin used to build links **inside emails**. Wrong value ⇒ verification and reset links point nowhere. |
| `GEMINI_API_KEY` | Chat degrades without it; the app still starts. |

### API (optional)

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_PROVIDER` | `noop` | `noop` logs the link instead of sending. Set `resend` for real delivery. |
| `RESEND_API_KEY` | — | Required when `EMAIL_PROVIDER=resend`. A blank key silently degrades to `noop`. |
| `EMAIL_FROM` / `EMAIL_REPLY_TO` | Resend shared sender | Must be on a domain verified with the provider. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | Blank disables Google sign-in cleanly (button hides, endpoint 503s). |
| `WEB_CONCURRENCY` | `1` | **Leave at 1.** See [§8](#8-known-limits-at-mvp-scale). |
| `RUN_MIGRATIONS` | `true` | Set `false` when a release job owns migrations (see [§5](#5-migrations)). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |

### Web (build-time only)

| Variable | Notes |
|---|---|
| `VITE_API_BASE_URL` | Public API origin. The frontend Dockerfile **fails the build** if unset, rather than shipping a bundle that quietly points at `localhost:8000`. |
| `VITE_GOOGLE_CLIENT_ID` | Public by design. Blank hides the Google button. Must match the API's `GOOGLE_CLIENT_ID`. |

---

## 4. Deployment options

### Option A — Single box, docker compose

Good for a pilot or a staging environment. One VM, everything on it.

```bash
cp .env.docker.example .env
# fill in POSTGRES_PASSWORD, JWT_SECRET_KEY, GEMINI_API_KEY, ...
docker compose up --build -d
docker compose run --rm api seed     # demo data; refuses if ENVIRONMENT=production
```

Web on `:8080`, API on `:8000`. Migrations run automatically on API start.

> The bundled `db` service has **no automated backups and no failover**. It is
> fine for staging. For real student data, delete that service and point
> `DATABASE_URL` at a managed instance — then follow [§6](#6-backups).

Put a TLS terminator (Caddy, nginx, or the platform's LB) in front. Nothing in
this stack terminates TLS itself.

### Option B — Render blueprint

`render.yaml` is a complete, working blueprint: managed Postgres with daily
backups, the API as a Docker service with migrations as a `preDeployCommand`,
and the frontend as a static site with rewrites and cache headers.

1. Push `render.yaml` to the default branch.
2. Render → **New → Blueprint** → select the repo.
3. Fill in the values marked `sync: false` (secrets; Render prompts, never stores them in git).
4. After the first deploy, update `CORS_ORIGINS`, `FRONTEND_URL` and
   `VITE_API_BASE_URL` to the real hostnames, then **redeploy the web service**
   (a restart will not pick up a `VITE_*` change).

### Option C — Split hosting

The most common production shape: static frontend on a CDN, API in a container.

- **Frontend** → Netlify / Vercel / Cloudflare Pages. Rewrite config already in
  the repo (see [§2](#2-the-three-things-that-break-first-deploys)). Set
  `VITE_API_BASE_URL` in the host's build environment.
- **API** → any container host (Railway, Fly.io, Cloud Run, ECS) using
  `backend/Dockerfile`. Set `RUN_MIGRATIONS=false` and run
  `alembic upgrade head` as a release/pre-deploy step.
- **Database** → managed Postgres 15+ (RDS, Cloud SQL, Neon, Supabase).

---

## 5. Migrations

The production schema is built **only** by the Alembic chain. Tests build
theirs from the SQLAlchemy models via `create_all` and never touch migrations,
so a missing revision is invisible to the test suite. CI now applies the chain
from scratch on every PR (`migrations` job) to close that gap.

Two supported patterns:

| Pattern | How | When |
|---|---|---|
| **Entrypoint** (default) | `RUN_MIGRATIONS=true`; the container migrates on boot | Single instance. Simplest. |
| **Release job** | `RUN_MIGRATIONS=false` + `alembic upgrade head` as a pre-deploy step | **Required for >1 instance** — concurrent `alembic upgrade` from N booting containers can deadlock on the version table. |

```bash
# Manual, against any environment
DATABASE_URL=... alembic upgrade head    # apply
DATABASE_URL=... alembic current         # what's applied
DATABASE_URL=... alembic heads           # must print exactly one head
```

Alembic reads `DATABASE_URL` through `app/config.py` (`migrations/env.py`
overrides `alembic.ini`'s placeholder), so no separate connection string.

**Migrations are not automatically reversible in practice.** Downgrades exist
but are not exercised. To undo a bad schema change, restore from backup
([§6](#6-backups)) rather than trusting `alembic downgrade`.

---

## 6. Backups

Kio stores mental-health records for minors. Treat the database as the only
thing that cannot be rebuilt from git.

### Policy

| | |
|---|---|
| **Automated daily snapshot** | Enable on the managed instance. Every provider offers this; it must be on before the first real user. |
| **Retention** | 30 days minimum. |
| **Point-in-time recovery** | Enable if the plan supports it. Daily snapshots alone mean up to 24h of loss. |
| **Pre-release manual dump** | Take one before any deploy containing a migration ([§7](#7-release-and-rollback)). |
| **Restore drill** | Restore into a scratch database **quarterly**. An untested backup is not a backup. |
| **Encryption** | At rest (provider setting) and in transit (`sslmode=require`). |

### Manual dump and restore

```bash
# Dump (custom format — required for parallel/selective restore)
pg_dump "$DATABASE_URL_LIBPQ" -Fc -f "kio-$(date +%Y%m%d-%H%M).dump"

# Restore into a fresh database
createdb kio_restore
pg_restore -d kio_restore --no-owner --clean --if-exists kio-20260907-1430.dump

# Verify before trusting it
psql -d kio_restore -c "select count(*) from users;"
psql -d kio_restore -c "select version_num from alembic_version;"
```

`DATABASE_URL_LIBPQ` is the URL **without** the `+asyncpg` driver suffix —
`pg_dump` is a libpq client and does not understand it:

```bash
DATABASE_URL_LIBPQ="${DATABASE_URL/postgresql+asyncpg/postgresql}"
```

Always check `alembic_version` after a restore: it tells you which code
revision that snapshot is compatible with.

> **Never run `python -m database.seed` against production.** It creates demo
> accounts that all share one password published in the README. The container
> entrypoint refuses when `ENVIRONMENT=production`, but nothing stops a direct
> invocation.

---

## 7. Release and rollback

**Release**

1. CI green on the commit (tests, migrations, typecheck, both image builds).
2. If the release contains a migration → take a manual dump ([§6](#6-backups)).
3. Deploy API (migrations run via entrypoint or release job).
4. Deploy web.
5. Smoke test ([§9](#9-smoke-test)).

**Rollback**

- *Code only, no migration* — redeploy the previous image. Done.
- *Contains a migration* — this is the case worth rehearsing. Rolling code back
  while the schema stays forward is usually survivable, because migrations are
  additive by convention (`013` and `014` are all-nullable adds). Restoring the
  database is the destructive option: it discards every write since the dump.
  Prefer rolling **forward** with a corrective migration. Restore only if the
  schema change actively corrupts data, and accept the write loss knowingly.

---

## 8. Known limits at MVP scale

Two subsystems keep state inside the worker process. Both are documented
constraints, not bugs — but they set a hard ceiling on how you scale today.

**Rate limiting is per-process.** `app/rate_limit.py` holds counters in an
in-memory dict. With N workers or N replicas, every limit is effectively N
times looser, and all counters reset on deploy. The login limit of 10/min is
the one that matters. Until this moves to Redis: keep `WEB_CONCURRENCY=1`, and
if you run multiple containers, put real rate limiting at the load balancer.

**Background work is in-process.** The intelligence and crisis pipelines run in
FastAPI `BackgroundTasks` inside the worker that served the request. A restart
mid-task drops it — which for the crisis path means a risk evaluation can be
lost. Mitigations in place: the synchronous keyword tripwire fires before any
background work, and the entrypoint `exec`s uvicorn with a 30s graceful
shutdown so in-flight tasks get a chance to finish. Proper fix is a job queue.

**Consequence:** scale vertically first. Horizontal scaling requires Redis-backed
rate limiting and a real queue, and — as soon as you have >1 instance —
switching migrations to the release-job pattern ([§5](#5-migrations)).

Also currently missing and worth adding before real traffic: error tracking
(no Sentry), a logging handler (module loggers exist but nothing configures
one, so warnings may go nowhere), and gating `/docs` + `/openapi.json`, which
are public on every environment.

---

## 9. Smoke test

Run against the deployed origins after every release.

```bash
API=https://api.example.com

curl -fsS "$API/health"        # {"status":"healthy",...}
curl -fsS "$API/health/db"     # {"status":"healthy","database":"connected"}
```

> `/health/db` returns **HTTP 200 even when the database is down** (the body
> says `unhealthy`). Do not wire a load balancer's readiness probe to its status
> code — check the body, or use `/health` for liveness only.

Then in a browser:

1. Load the site root — the landing page renders.
2. **Hard-refresh on a deep link** (`/login`, then `/verify-email`). A 404 here
   means the SPA rewrite is missing — go back to [§2](#2-the-three-things-that-break-first-deploys).
3. Sign up as a student. The response is fast (email sends in the background).
4. Verification email arrives; its link opens the deployed origin, not localhost
   — if it says localhost, `FRONTEND_URL` is wrong.
5. `/forgot-password` → email arrives → reset works → old password rejected.
6. Send a chat message; Comrade replies.
7. Sign out, sign back in.

If Google sign-in is enabled, also confirm the button appears (it hides when
`VITE_GOOGLE_CLIENT_ID` is blank) and completes a round trip.

---

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: psycopg2` | `DATABASE_URL` reached SQLAlchemy without the asyncpg driver. Should be handled automatically — check the value isn't malformed. |
| App exits at boot: "JWT_SECRET_KEY must be set" | `ENVIRONMENT=production` with the dev default secret. Working as designed. |
| CORS errors in the browser console | `CORS_ORIGINS` must contain the frontend origin **exactly** — scheme, host, port, no trailing slash — and be valid JSON. |
| Deep links 404; root works | SPA rewrite missing. [§2](#2-the-three-things-that-break-first-deploys). |
| Email links point at `localhost:5173` | `FRONTEND_URL` not set on the API. |
| No email arrives, no error | `EMAIL_PROVIDER` is `noop`, or `RESEND_API_KEY` is blank — both degrade silently by design. Check API logs for the logged link. |
| Frontend calls `localhost:8000` in production | `VITE_API_BASE_URL` missing at **build** time. Rebuild; a restart won't fix it. |
| Google button missing | `VITE_GOOGLE_CLIENT_ID` blank at build time. |
| Google sign-in 503 | `GOOGLE_CLIENT_ID` not set on the API. |
| 429s during testing | Rate limiter. Counters reset on restart. |
| `alembic heads` prints two heads | Branched migration chain; must be merged before deploying. CI fails on this. |
