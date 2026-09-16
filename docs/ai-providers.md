# AI providers, models, and runtime configuration

> **Current state:** Google Gemini (`gemini-2.5-flash`) is the primary
> provider. OpenAI (`gpt-5-mini`) is fully implemented but **disabled**,
> because this deployment has no OpenAI credentials. Kio requires only
> `GEMINI_API_KEY` today.

---

## 1. Architecture

```
Kio feature (chat, risk detection, insights, reports, activities)
        │
        ▼
ai_router.run()                 ← the single entry point; guardrails applied here
        │
        ▼
Route resolution (once per call, then frozen for that call)
        │
        ▼
Provider registry  → app/ai/registry.py     (which pairs are SUPPORTED)
Provider factory   → app/ai/factory.py      (name → adapter instance)
        │
        ▼
GeminiProvider  │  OpenAIProvider           (all provider-specific code)
        │
        ▼
ProviderResponse                            (normalized: text + tokens + model)
        │
        ▼
EXISTING Kio pipeline: parse → schema validate → safety floor → derive level → crisis
        │
        ▼
final response
```

Nothing above the adapters imports a provider SDK, knows what a
`response_format` is, or branches on which provider answered. Adapters raise
`app.ai.errors` types rather than SDK exceptions, so retry and fallback are
decided by error *class*, never by string-matching a message a provider could
reword.

| File | Role |
|---|---|
| `app/ai/registry.py` | The allowlist of supported provider/model pairs, and whether each provider's key is present |
| `app/ai/errors.py` | Provider-neutral error taxonomy; carries `retryable` and `fallback_eligible` |
| `app/ai/factory.py` | Provider id → adapter instance |
| `app/ai/providers/base.py` | The `AIProvider` interface and `ProviderResponse` |
| `app/ai/providers/gemini.py` | Gemini adapter (google-genai) |
| `app/ai/providers/openai.py` | OpenAI adapter (httpx — no new dependency) |
| `app/ai/runtime_config.py` | The active platform configuration: resolution, cache, validation |
| `app/ai/config_loader.py` | Per-call route resolution across the three layers |
| `app/ai/guardrails.py` | Timeout, token/input bounds, rate ceilings, concurrency, circuit breaker |
| `app/ai/router.py` | Guardrails → resolve → retry → bounded fallback → telemetry |
| `app/ai/usage.py` | One `ai_usage_logs` row per attempt, with redaction |

**Why OpenAI uses httpx rather than the `openai` SDK:** httpx is already a
declared Kio dependency (Resend, Google token verification), the Chat
Completions surface Kio needs is a single POST, and an SDK would bring its own
retry and timeout behaviour that would overlap with `AIRouter`'s — the
duplicated-retry problem this design exists to avoid. No package was added.

---

## 2. Supported providers and models

The **code** decides what is supported. Environment and database decide which
supported combination is **active**.

| Provider | Model | Structured output |
|---|---|---|
| `gemini` (Google Gemini) | `gemini-2.5-flash` | yes |
| `openai` (OpenAI) | `gpt-5-mini` | yes |

Adding a model is a deliberate code change to `app/ai/registry.py`, not a text
field. `risk_detection` asks a model to judge whether a teenager is in danger,
and "whatever string someone pasted into a box" is not an acceptable answer to
"which model made that judgement". It also closes the obvious injection route:
a model id flows into an outbound API call.

Arbitrary provider/model strings are rejected server-side at **three** places —
the platform config endpoint, the per-feature route endpoint, and the
playground — and the admin UI has no free-text model field at all.

---

## 3. Configuration precedence

Highest first:

1. **Active per-feature override** (`ai_feature_routes` where `is_active`)
2. **Platform runtime config** (`ai_runtime_config`, set from the admin UI)
3. **Environment defaults** (`AI_PRIMARY_*` in settings)

Resolution happens **once per AI call**. A request that has begun keeps the
provider it started with; an admin change applies to the next request. There is
no restart and nothing in flight is disturbed.

If the database row is removed, the environment defaults apply again. If the
stored row becomes unusable (a model dropped from the registry in a later
release, or a key removed from the environment), it is logged and the
environment defaults are used — Kio keeps answering rather than failing every
AI request because a stored preference went stale.

### The per-feature layer, and what migration 019 changed

`ai_feature_routes` predates this work and is kept: running risk detection on a
different model than chat is a real need. But migrations 005 and 009 seeded five
rows as *defaults*, not as anybody's decision — and with the platform config now
below them in precedence, leaving them active would have meant an admin
switching the platform provider changed **nothing at all**, because every
feature was pinned by a row nobody remembered creating.

Migration 019 therefore sets `is_active = false` on exactly those five seeded
rows. Nothing is deleted and the capability remains; an override is now
something an admin turns on deliberately, and the admin UI labels each feature
as *Uses platform default* or *Override*.

> **Consequence worth knowing:** `memory_extraction` and `title_generation` were
> seeded on `gemini-2.5-flash-lite` for cost. They now follow the platform model
> (`gemini-2.5-flash`) unless re-enabled. That is a small cost increase on two
> cheap, non-safety-critical features, in exchange for the platform switch
> meaning what it says. Re-enable those two overrides if the cost matters more.

---

## 4. Credentials

API keys are **server-side environment secrets only**. They are never:

- stored in the database (`ai_runtime_config` has no credential column, and a
  test asserts no AI table has one)
- returned to the frontend (the admin UI receives `credential_configured: true|false`
  and the env var *name*, never any part of a value)
- written to logs, audit rows, or usage telemetry
- committed (`.env` is gitignored; the examples hold placeholders only)

Only the credential for a provider actually in use is required:

| Situation | Required |
|---|---|
| primary = gemini | `GEMINI_API_KEY`. **`OPENAI_API_KEY` is not required.** |
| primary = openai | `OPENAI_API_KEY` |
| fallback enabled | that provider's key as well |

In **production** a missing required credential refuses startup. Outside
production it logs a warning and continues — the test suite and a fresh
checkout both run with no AI credentials at all, and a hard failure there would
make the app un-runnable while working on anything unrelated.

---

## 5. Changing the provider at runtime

`/admin/ai` → **Platform AI configuration**. Platform admin only, enforced
server-side.

Before anything is written, the backend validates:

1. provider is in the registry
2. model is in the registry
3. the model belongs to that provider
4. that provider's API key is present on this server
5. the same three checks for the fallback, when enabled
6. primary and fallback are not the identical pair
7. an enabled fallback is fully specified

**Fail-safe by construction.** Validation runs before any write, so a rejected
configuration leaves the stored row, the in-process cache, and the provider
currently serving traffic untouched. There is no partial save — it is one row
in one transaction. Selecting OpenAI without `OPENAI_API_KEY` returns:

> OpenAI is supported, but OPENAI_API_KEY is not configured on this server.

…and Gemini keeps serving. Both successful and refused changes are audited as
`admin.ai_configuration_changed`.

### Sessions are unaffected — by construction

Changing the AI configuration does **not** log anyone out, revoke an access or
refresh token, touch `refresh_sessions` or `users`, alter JWT or Google OAuth
configuration, clear browser state, or restart anything.

The guarantee is structural, not incidental: `app/ai/runtime_config.py` imports
nothing from `app.auth` and touches no authentication table, and a test parses
its import graph to keep it that way. Behavioural tests additionally sign a
student in, switch Gemini → OpenAI → Gemini, and assert the access token still
authenticates, the refresh token still rotates, and every row in
`refresh_sessions` and `users` is byte-identical.

---

## 6. Fallback

Disabled by default, because this deployment has no OpenAI key.

When enabled: **PRIMARY → bounded retries → FALLBACK → bounded retries → stop.**
Never back to the primary; there is no loop.

Fallback is a *cost* decision as much as an availability one, so eligibility is
per error class:

| Failure | Retry same provider | Fall back |
|---|---|---|
| timeout | yes | **yes** |
| provider 5xx / unreachable | yes | **yes** |
| circuit open (cooldown) | no | **yes** |
| rate limit (429) | yes | **no** |
| invalid / missing API key | no | no |
| unsupported model, config error | no | no |
| malformed or unusable response | no | **no** |
| Kio guardrail refusal | no | no |

Two of those deserve their reasoning stated:

- **429 does not fail over.** A rate limit usually means Kio is sending more
  traffic than planned. Redirecting that flood at a second paid provider turns
  a throttle into a bill.
- **A malformed response does not fail over.** "The model said something we
  could not use, so ask a different model and take that instead" is exactly the
  pattern that would let a provider swap become a way around validation. Kio's
  existing safe-failure behaviour handles it.

Retries are capped by the router at 3 regardless of what a route requests, so a
database row asking for 99 cannot bill the platform.

---

## 7. Guardrails

Applied in `ai_router.run()` **before a provider is selected**, so the fallback
cannot be used to get around a ceiling the primary hit. All are settings, not
constants scattered across feature files.

| Guardrail | Setting | Default |
|---|---|---|
| Request timeout | `AI_REQUEST_TIMEOUT_SECONDS` | 30s |
| Max output tokens | `AI_MAX_OUTPUT_TOKENS_CEILING` | 4096 (clamps, never unbounded) |
| Max input size | `AI_MAX_INPUT_CHARS` | 60,000 |
| Per-user rate | `AI_USER_REQUESTS_PER_MINUTE` | 20 |
| Per-feature rate | `AI_FEATURE_REQUESTS_PER_MINUTE` | 120 |
| Global rate | `AI_GLOBAL_REQUESTS_PER_MINUTE` | 300 |
| Concurrent per user | `AI_MAX_CONCURRENT_PER_USER` | 3 |
| Daily token ceiling | `AI_DAILY_TOKEN_CEILING` | 0 (disabled) |
| Monthly token ceiling | `AI_MONTHLY_TOKEN_CEILING` | 0 (disabled) |
| Circuit breaker | `AI_CIRCUIT_FAILURE_THRESHOLD` / `_COOLDOWN_SECONDS` | 5 / 60s |

Notes:

- **There was previously no timeout at all.** A hung provider hung the
  student's chat request with it, indefinitely.
- **Oversized input is refused, not truncated.** Silently dropping part of a
  conversation could remove the very message that indicates danger while still
  returning a confident low-risk score. A refusal reaches the caller's existing
  safe-failure path, which is visible.
- **Token ceilings count only tokens providers actually reported.** Usage is
  never estimated — a ceiling enforced against invented numbers is worse than
  no ceiling.
- **The circuit breaker counts only transient failures.** Five configuration
  errors in a row are still a configuration error, and a cooldown for them
  would outlast the operator's fix.
- The pre-existing per-student daily chat cap (`AI_DAILY_MESSAGE_LIMIT`, 100)
  and the HTTP rate limiter are unchanged and still apply.

### Multi-worker caveat

Rate windows, concurrency counts and breaker state are **in-process**. Kio runs
`WEB_CONCURRENCY=1` by default and its HTTP rate limiter already has the same
property and the same caveat. With N workers each limit is effectively N times
looser and each worker keeps its own breaker and its own config cache — meaning
an admin's change would reach one worker immediately and the others on their
next cache miss. Making these global needs shared state (Redis), at which point
the existing rate limiter should move at the same time. **Token ceilings are
already global**, being counted in SQL against `ai_usage_logs`.

---

## 8. Safety — unchanged

The provider abstraction does not touch Kio's safety architecture. The flow is
exactly as before:

```
ai_router.run() → parse_json_response → MessageAnalysis.model_validate
                → _apply_safety_floor → derive_risk_level → crisis workflow
```

- Safety decisions live in `app/intelligence/`, never in an adapter.
- `app/ai/router.py` imports nothing from `app.intelligence` and nothing with
  "safety" in the name — asserted by a test that parses its import graph. If
  the router could see risk scores it could, one refactor later, pick a
  provider based on them.
- A fallback response takes the **identical** path, including the deterministic
  safety floor.
- Provider selection never depends on user risk.
- The synchronous keyword tripwire is untouched and still runs before any
  model call.
- OpenAI's own `content_filter` finish reason is treated as an *unusable
  response*, not as a Kio safety verdict.

---

## 9. Telemetry and observability

One `ai_usage_logs` row per attempt: feature, provider, model, success,
`failure_category`, latency, input/output tokens, estimated cost,
`fallback_used`, and `request_id` — the same correlation id as the structured
logs, the audit trail, and Sentry.

One structured log line per attempt, for example:

```
ai_call provider=gemini model=gemini-2.5-flash feature=comrade_chat success=false
        failure_category=rate_limit fallback_used=False latency_ms=7625 request_id=aiverify1
```

Never recorded anywhere: API keys, authorization headers, prompts, responses,
Comrade conversation content, crisis text, or student information.
`error_message` is redacted on the way in — a mapped `AIError` carries a message
an adapter constructed, and an *unmapped* exception stores only its type name,
because its text is unreviewed and could quote the request (and the request is
the prompt).

**Admin health** is derived from this telemetry plus the in-process breaker,
never by calling a provider. Polling a paid API on a schedule to colour a badge
would cost money to answer a question real traffic already answers. A provider
with no credentials shows *Credentials unavailable* — that is the expected
state for OpenAI here, not a fault, and Kio is not unhealthy because of it.

---

## 10. Activating OpenAI later

1. Add `OPENAI_API_KEY=sk-...` to the deployment's secret store (Render
   environment group, Docker secret, etc.). Never to a committed file.
2. Restart or redeploy **once**, so the process sees the new variable. This is
   the only restart involved — it is required because API keys are read from
   the environment at process start, by design.
3. Open `/admin/ai`. OpenAI is now selectable; the health line reads
   *Configured* instead of *Credentials unavailable*.
4. Either:
   - set **Primary** to OpenAI / GPT-5 mini, or
   - leave Gemini primary and switch **Fallback** on with OpenAI / GPT-5 mini.
5. Save. Takes effect for new AI requests immediately. No deploy, no restart,
   nobody signed out.

To test a real key locally without committing it:

```bash
# PowerShell — set for this process only; never written to a file
$env:OPENAI_API_KEY = "sk-..."
cd backend; .\venv\Scripts\python.exe -m uvicorn main:app --reload
```

```bash
# bash
OPENAI_API_KEY="sk-..." ./venv/Scripts/python.exe -m uvicorn main:app --reload
```

The normal test suite never calls a real provider; both adapters are driven
through mocked transports.
