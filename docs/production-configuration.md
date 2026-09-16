# Production configuration

Every environment variable Kio reads, what breaks without it, and which
development defaults must never survive into production.

Kio processes mental-health data belonging largely to minors. Several defaults
below are deliberately unsafe for production and are rejected at startup rather
than quietly accepted — the application refuses to boot instead of running in a
state that looks fine and is not.

---

## Refused at startup

The app raises on start if any of these hold. Each is a mistake that would
otherwise be invisible until it was exploited.

| Condition | Why it is fatal |
|---|---|
| `ENVIRONMENT=production` and `JWT_SECRET_KEY` is the dev default | The dev secret is in this repository. Anyone who has read it could mint a valid admin token. |
| `CORS_ORIGINS` contains `*` | Kio sends credentials. Browsers reject wildcard-plus-credentials outright, so this only produces a confusing failure while advertising that any site may call the API. |
| `ENVIRONMENT=production` and `CORS_ORIGINS` contains a loopback origin | A leftover `localhost` entry means the production config was never actually reviewed. |
| `ENVIRONMENT=production` and `DB_ECHO=true` | SQLAlchemy echo logs every statement **and its bound parameters** — which in Kio are message text, counselor notes and crisis assessments. Enabling it would copy protected content into the host's log drain. |

---

## Required in production

### Backend

| Variable | Notes |
|---|---|
| `ENVIRONMENT` | Must be `production`. Gates docs, HSTS, the seed guard, and the checks above. |
| `DATABASE_URL` | `postgres://` from Render/Railway/Heroku is coerced to `postgresql+asyncpg://` automatically. |
| `JWT_SECRET_KEY` | 32+ random bytes. Rotating it invalidates every access token and every refresh session immediately. |
| `CORS_ORIGINS` | JSON array of the real frontend origin(s), e.g. `["https://app.kio.example"]`. |
| `FRONTEND_URL` | Base for emailed links (verification, password reset, guardian consent). Wrong value = links that 404 or point at localhost. |
| `ALLOWED_HOSTS` | JSON array of the API's own hostname(s). Blocks Host-header spoofing, which otherwise turns password-reset links into an attacker's domain. |
| `EMAIL_PROVIDER` | `resend`. Leaving it `noop` means verification and reset emails are never delivered — signup appears to work and nobody can confirm an address. |
| `RESEND_API_KEY` | Required when `EMAIL_PROVIDER=resend`. A blank key degrades to `noop` with a warning rather than crashing. |
| `EMAIL_FROM` | Must be on a domain verified in Resend, or mail is rejected. |
| `GEMINI_API_KEY` | Without it Comrade cannot reply. The safety tripwire still runs. |

### Frontend (build-time)

`VITE_*` values are **inlined at build time**. Changing one requires a rebuild
and redeploy, not a restart.

| Variable | Notes |
|---|---|
| `VITE_API_BASE_URL` | The API origin. The frontend Dockerfile refuses to build without it rather than shipping a bundle that silently calls `localhost`. |
| `API_ORIGIN` | **Runtime**, on the web container. Substituted into the CSP's `connect-src`. Must match `VITE_API_BASE_URL`. If it does not, the browser blocks every API call *before sending it* — no server logs, no network activity, a page that simply does nothing. |
| `VITE_GOOGLE_CLIENT_ID` | Omit to hide the Google button entirely; the app works without it. |

---

## Optional

| Variable | Default | Notes |
|---|---|---|
| `SENTRY_DSN` | *(empty)* | Empty disables reporting. This is the switch — there is no separate boolean to forget. |
| `SENTRY_ENVIRONMENT` | `ENVIRONMENT` | Override to separate staging from production in one Sentry project. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Performance tracing off by default. |
| `VITE_SENTRY_DSN` | *(empty)* | Frontend equivalent, build-time. |
| `FORCE_HTTPS` | `false` | Leave **off** behind a TLS-terminating proxy: the container sees `http://` internally and would redirect forever. On only when the app is edge-facing. |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-scope default. See the topology note below. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access tokens are stateless; this is the window in which a stolen one still works. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh sessions are revocable, so this is a ceiling, not the exposure. |
| `AI_DAILY_MESSAGE_LIMIT` | `100` | Per student per day. Cost control. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `20` / `10` | Must fit inside the database's own connection limit. |
| `DB_ECHO` | `false` | Logs every statement **and its parameter values**. **Refused at startup in production** — see above. Remains available in development. |
| `KIO_ALLOW_PRODUCTION_SEED` | *(unset)* | Only `i-understand` permits seeding a production environment. See below. |

---

## SQL statement logging (`DB_ECHO`)

**`DB_ECHO=true` is refused at startup when `ENVIRONMENT=production`.**

SQLAlchemy's echo mode logs every statement *and its bound parameters* at INFO.
In most products that is a noisy convenience. In Kio the bound parameters of an
ordinary `INSERT` are a student's message to Comrade, a counselor's session
note, or a crisis assessment — so enabling echo in production would copy exactly
the content this product exists to protect into the host's log drain, where it
is retained on a schedule nobody chose for privacy reasons and readable by
anyone with log access.

The failure names the variable:

```
DB_ECHO must be false in production. SQLAlchemy echo logs SQL statement
parameters, which for Kio include conversation and message content.
Refusing to start.
```

**Refused, not silently forced to false.** This matches the other guards here.
An operator who set the flag meant to see something; quietly ignoring it would
leave them debugging why their change had no effect while believing it had
taken, and would mean production behaved differently from the configuration on
file. A startup failure is the faster route to the right outcome.

**Unchanged in development and test**, where echo is a genuinely useful tool.
Note that `is_production` is an exact match on `"production"`, so a `staging`
environment is treated as non-production here exactly as it is by every other
guard — set `ENVIRONMENT=production` on any deployment holding real student data.

### `echo` is the only route to statement logging

Raising the application's log level does **not** produce it. SQLAlchemy pins its
own `sqlalchemy` logger to `WARNING` when imported (`sqlalchemy/log.py`), so it
does not inherit the root logger's level — `DEBUG=true` or a verbose `LOG_LEVEL`
alone cannot emit statements or parameters. `database/session.py` sets no other
logging option (no `echo_pool`, no explicit `sqlalchemy.engine` level).

`backend/tests/test_config_db_echo.py` asserts all of this against SQLAlchemy
itself, so a dependency upgrade or a change to `main.py`'s logging setup that
opened a second route would fail the suite rather than ship.

---

## First-run bootstrap

`python -m database.bootstrap` creates the first school and platform admin from
`BOOTSTRAP_*` environment variables, and **refuses once any admin exists**. It
is the only supported way to get an admin account into a production database,
because seeding is refused there. Full steps: `docs/deployment.md` §5a.

It is not an HTTP endpoint and must not become one. The guard, the password
rules and the absence of a route are covered by `backend/tests/test_bootstrap.py`.

---

## Seeding

`database/seed.py` creates one account per role — platform admin included —
all sharing a password printed in this repository and its git history. Running
it against a live system hands an admin login to anyone who has read the source.

It is refused when `ENVIRONMENT=production`, both in `docker-entrypoint.sh` and
inside `seed.py` itself, because `python -m database.seed` is the obvious thing
to type and bypasses the shell script. The override exists only for a staging
stack deliberately labelled production, and must be exactly `i-understand`.

---

## Rate limiting topology

The limiter is **in-process** (`app/rate_limit.py`): a dictionary in the worker
that serves the request. This is correct and honest for the current
deployment, which runs **one worker per instance** — `render.yaml` and
`docker-compose.yml` define no `--workers` flag and no replica count.

**It is not distributed.** Run two workers or two replicas and each gets its
own counters, so the effective limit multiplies by the number of processes.
Before scaling out, either keep the limiter per-process and reduce the
per-worker limit accordingly, or move the store to Redis — the dependency
interface is unchanged either way.

Scopes with limits today: `login` (10/min), `refresh` (30/min), `verify`
(20/min), password reset, and chat. Normal student activity is well inside
these; the limits exist to slow credential stuffing, not to ration usage.

---

## Background work

Auxiliary work runs in FastAPI `BackgroundTasks`, in-process. If the process
dies mid-task, that task is lost. What that costs, per path:

| Task | Lost if the process dies | Acceptable for pilot? |
|---|---|---|
| Verification / reset / consent email | Yes — user can request another | Yes |
| Conversation title, memory extraction | Yes — cosmetic | Yes |
| Parent insight refresh | Yes — recomputed next time | Yes |
| **Intelligence pipeline** (risk + crisis) | Yes — that message is not analysed | **Yes, with the caveat below** |

The caveat: the **synchronous keyword tripwire runs before any background
work**, inside the request that produced the reply. Explicit self-harm,
suicidal ideation, abuse and violence language alerts a counselor even if the
process dies immediately afterwards. What the background pipeline adds is the
LLM's subtler judgement — real value, but not the last line of defence.

Failures are logged with a full traceback and reported to Sentry, with the
intelligence pipeline at `ERROR` and tagged `safety_relevant`. Before a pilot
at a scale where a lost evaluation matters, this is the first thing to move to
a durable queue.

---

## Secrets

No secret is committed. `.env` is gitignored; `.env.example` and
`.env.docker.example` are templates with placeholder values only.
`docker-compose.yml` requires `POSTGRES_PASSWORD` to be supplied — it has no
default, so the stack refuses to start rather than running on a known password.

---

## Audit logging

Full reference: **[`docs/audit-logging.md`](audit-logging.md)**. The operational
points that matter for a deployment:

- **Append-only is enforced by a Postgres trigger**, installed by migration 018
  and by an `after_create` hook on the model so it exists under `create_all`
  too. `UPDATE`, `DELETE` and `TRUNCATE` on `audit_logs` all raise.
- **Optional hardening:** if the deployment separates the migration role from
  the runtime role, restrict the runtime role to `INSERT, SELECT` on
  `audit_logs`. Not applied automatically — it needs two roles, which is a
  deployment decision.
- **Access is platform-admin only**, enforced server-side. School admins have
  no audit access; the tenant scoping exists and is tested if that changes.
- **Reads and exports are themselves audited.** Expect `admin.audit_log_viewed`
  volume proportional to how often the page is opened.
- **Correlation:** every audit row carries the same `request_id` as the
  structured logs and the Sentry event for that request. This is the join key
  during an incident.
- **No queue or broker** was introduced. Audit writes are single inserts at the
  service boundary; auth events use a short-lived second connection so an audit
  failure can never lock users out.

> ⚠️ **Retention is an open legal/product decision.** No automatic deletion is
> implemented and none should be added until a period is agreed — see
> [Retention](audit-logging.md#retention). This sits alongside the other open
> DPDP questions recorded in `app/consent/policy.py`.

---

## AI providers and runtime model switching

Full reference: **[`docs/ai-providers.md`](ai-providers.md)**. Deployment-relevant
points:

- **Only `GEMINI_API_KEY` is required today.** Gemini (`gemini-2.5-flash`) is
  primary; OpenAI (`gpt-5-mini`) is implemented but disabled. A missing
  `OPENAI_API_KEY` does not affect startup or Gemini. In production a missing
  credential for a provider that *is* in use refuses startup; outside
  production it warns.
- **API keys are environment-only.** Never in the database, the audit trail,
  usage telemetry, logs, or any response to the frontend — the admin UI receives
  only a boolean per provider.
- **A platform admin can switch provider/model at `/admin/ai`** with no deploy
  and no restart. Selections come from a backend allowlist; arbitrary strings
  are rejected. An invalid configuration is refused before anything is written,
  so the working provider keeps serving.
- **Switching does not touch authentication.** No session, token, or user row is
  read or written on that path; it is enforced structurally and tested.
- **A request timeout now exists** (`AI_REQUEST_TIMEOUT_SECONDS`, 30s). There
  was none before, so a hung provider hung a student's chat request with it.
- **Guardrails are per-process**, like the existing HTTP rate limiter: with
  `WEB_CONCURRENCY>1` each limit is effectively N times looser and each worker
  caches the configuration separately. Token ceilings are global (counted in
  SQL). See the multi-worker caveat in the reference doc.
- **Migration 019 deactivates five seeded per-feature routes** so platform-level
  switching actually applies. `memory_extraction` and `title_generation` move
  from `gemini-2.5-flash-lite` to the platform model as a result.

> ⚠️ **`DB_ECHO` cannot be enabled in production** — the app now refuses to
> start. Unrelated to the AI layer; see
> [SQL statement logging](#sql-statement-logging-db_echo) below.
