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
| `DB_ECHO` | `false` | **Never enable in production.** It logs every statement, including parameter values. |
| `KIO_ALLOW_PRODUCTION_SEED` | *(unset)* | Only `i-understand` permits seeding a production environment. See below. |

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
