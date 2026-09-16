# Audit logging

> **Status:** production-ready as of migration 018.
> **Retention:** *not yet decided.* See [Retention](#retention) — this is a
> pending legal/product decision and no automatic deletion is implemented.

Kio's audit trail answers one question: **who did what, to which record, when,
and from where.** It is deliberately not able to answer "and what did the
student say" — that separation is the entire design.

---

## 1. What an audit record contains

One row per meaningful event, in `audit_logs`.

| Column | Meaning |
|---|---|
| `audit_id` | Primary key. |
| `created_at` | UTC, server-generated. |
| `user_id` | The actor. `NULL` for unattributable events (a failed login for an address matching no account) and for background pipelines. |
| `actor_role` | The actor's role **at the time of the event**, denormalised. A later role change must not rewrite what someone was permitted to do when they did it. `system` for background pipelines. |
| `tenant_id` | School scope. Denormalised, and **not always the actor's own school** — when a platform admin acts on a school, the event belongs to the school acted upon. |
| `action` | Canonical action name from `app/audit_actions.py`. |
| `entity_type` / `entity_id` | What was acted on. |
| `result` | `success` or `failure`. A refused action is often the more interesting record. |
| `severity` | `info` / `notice` / `warning` / `critical` — operator attention, not clinical severity. |
| `request_id` | Correlation id (see §5). `NULL` outside an HTTP request. |
| `ip_address` / `user_agent` | Request origin, both length-capped. |
| `details` | Structured JSONB metadata — references and short values only. |

`previous_state` / `new_state` columns were **deliberately not added.** For the
mutations Kio actually audits, a list of *changed field names* (which is what
`details.changed` carries) answers the operational question without turning the
audit table into a second copy of every record it describes — including records
that hold a child's date of birth, guardian details and risk level.

---

## 2. What it never contains

The following must never appear in any audit row, in any column:

- Comrade message text, or any conversation content
- Counselor session notes
- Crisis message contents
- Risk narratives or summaries (`risk_assessments.summary` is **not** copied)
- Passwords, password hashes, or password-reset tokens
- JWTs — access or refresh — or session tokens
- OTP values, OAuth authorization codes, API keys
- `Authorization` headers, or full request bodies

Three independent mechanisms enforce this:

1. **Call-site discipline.** Every `log_audit()` call passes references
   (ids, enums, counts), not content. This is the actual guarantee.
2. **`scrub_details()`** in `app/audit.py` — a backstop that redacts by key
   name (substring match on ~25 patterns, walked through nested dicts and
   lists), caps strings at 200 characters, and bounds key count.
3. **Tests.** `tests/test_audit.py` sweeps every row written during real
   login / refresh / logout / safety-scan flows and asserts that no JWT-shaped
   string, no login password, and no scanned message text is present.

A denylist alone would always be one new field name behind, which is why it is
the third line of defence rather than the first.

### Deliberate exceptions

Three pieces of free-ish text are recorded, each for a specific reason:

| Field | Why |
|---|---|
| `details.email` on failed logins and user administration | A failed-login trail that does not name the targeted account cannot show credential stuffing. |
| `details.reason` on break-glass access | Admin-typed justification for reading a student's conversations. This is the point of the record. |
| `details.reason` on booking cancellation | "Why was this cancelled" is the question the row exists to answer. |

All three are scrubbed and length-capped. Counselor schedule-exception reasons
are **not** recorded — those are the counselor's own private note (illness,
family), and the audit question is only that a date was blocked out.

---

## 3. Append-only

Audit records cannot be edited or deleted through the application, and this is
enforced by the **database**, not merely by the absence of code:

- A Postgres trigger (`kio_audit_logs_append_only`) raises on `UPDATE`,
  `DELETE`, and `TRUNCATE` against `audit_logs`.
- It is installed by **migration 018** *and* by an `after_create` hook in
  `database/models.py`, so it exists under `create_all` too — the test suite
  builds its schema from the models, so a migration-only trigger would leave
  the append-only test asserting against a table that has none.
- The HTTP surface has **no** `POST`/`PUT`/`PATCH`/`DELETE` under
  `/admin/audit-logs`. A test asserts this against the live route table, so
  adding one later fails CI rather than shipping quietly.
- There is **no** cleanup or purge endpoint, by design.

This is safe because user and tenant deletion in Kio are both *soft* deletes,
so the `ON DELETE SET NULL` on `user_id` never fires from the application path.
A hard delete of a user would now fail loudly rather than quietly rewriting
history — the correct outcome for an audit trail.

**Limitation:** the trigger protects against application bugs, not against a
database superuser, who can drop it. Defence in depth for that is a restricted
role for the application's connection:

```sql
-- Optional hardening: application role can append and read, nothing else.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM kio_app;
GRANT INSERT, SELECT ON audit_logs TO kio_app;
```

This is **not** applied automatically — it requires a separate migration role
from the runtime role, which is a deployment decision. `docs/deployment.md`
covers the connection setup.

---

## 4. Who can read it

**Platform admins only** (`role = "admin"`), enforced server-side by
`require_role("admin")` on both the list and export endpoints. Verified by a
parametrised test across student, parent, counselor and school_admin.

School admins **do not** currently have access. The `tenant_id` column and the
tenant-scoped query exist and are tested, so granting them a scoped view is a
one-line change — but it is a product decision, not a default. The reason for
caution: a school admin can already see their roster, and an audit row naming
which counselor opened which student's risk case is sensitive staff and student
data even inside a single school.

Reading and exporting the audit log are **themselves audited**
(`admin.audit_log_viewed`, `admin.audit_log_exported`). A log that does not
record its own readers has a hole exactly where it matters most.

---

## 5. Correlation: audit → logs → Sentry

Every audit event written during an HTTP request carries the `request_id`
generated by `RequestContextMiddleware` in `app/observability.py`. This is the
**same** id that appears in the `X-Request-ID` response header, in every
structured log line for that request, and on the Sentry event if one is raised.
No second correlation scheme was introduced.

`log_audit()` reads it from a `ContextVar`, so it is picked up automatically
rather than threaded through ~60 call sites.

To trace an incident:

```
audit row  ──request_id──▶  application logs  ──request_id──▶  Sentry event
```

The admin UI exposes a **Request** column and a request-id filter for exactly
this. Events written outside a request (background pipelines) have
`request_id = NULL` — distinguishable from a request whose id we failed to
record.

---

## 6. Failure policy

The two writers implement a deliberate split:

| Writer | Transaction | On audit failure |
|---|---|---|
| `log_audit()` | Joins the caller's | **Fails closed** — the mutation rolls back too |
| `log_audit_detached()` | Its own, committed immediately | **Fails open** — logged and reported, never raised |

**Fail closed** for admin mutations, RBAC changes, school administration,
break-glass, config and prompt changes, scheduling and booking. For these, an
unrecorded change is worse than a failed one.

**Fail open** for authentication events, safety/crisis events, and booking
conflicts. Two reasons: these paths frequently *raise* (a failed login rolls
back its session, so a row written there would vanish exactly when it becomes
evidence), and an audit-table problem must never lock every user out or block a
crisis alert from reaching a counselor.

Fail-open gaps are not silent: the failure is logged with the request id, so
the hole is itself traceable.

**Performance.** Every audit write is a single INSERT at the authoritative
service boundary. No queue, broker, or background worker was introduced. The
detached writer costs one extra short-lived connection on auth paths, which are
not hot. `REFRESH_TOKEN_ROTATED` is the highest-volume event (one per refresh
per active user) and is kept at `info` severity for that reason.

---

## 7. Event coverage

Canonical names live in `backend/app/audit_actions.py`. Values keep this repo's
existing dotted-lowercase convention; the nine actions that predate that module
keep their **exact** historical strings so old rows and saved filters still work.

**Authentication** — `auth.login_success`, `auth.login_failed`, `auth.logout`,
`auth.google_login`, `auth.signup`, `auth.email_verified`,
`auth.password_reset_requested`, `auth.password_reset_completed`,
`auth.refresh_token_rotated`, `auth.refresh_token_revoked`,
`auth.session_revoked`

**Accounts / RBAC** — `user.create`, `user.update`, `user.delete` (soft),
`user.reactivate`, `user.password_reset`

**Schools** — `tenant.create`, `tenant.update`, `tenant.activate`,
`tenant.suspend`, `tenant.archive`

**Counselors** — `counselor.register`, `counselor.verify`

**Safety** — `risk.assessment_created`, `risk.level_changed`,
`crisis_workflow_triggered`, `crisis.notification_created`,
`crisis.notification_sent`, `crisis.notification_failed`, `risk.case_viewed`,
`risk_review:<status>`, `safety_event:<category>`,
`safety_soft_signal:<category>`

**Comrade** — `comrade.session_started`, `comrade.session_ended`.
Individual messages are **never** audited: the volume would dwarf every other
event, and a row per message is a minute-by-minute record of when a child was
distressed.

**Booking / scheduling** — `counselor_session:book`,
`counselor_session:cancel`, `booking.conflict`, `schedule.created`,
`schedule.deleted`, `schedule.time_off_created`, `schedule.time_off_deleted`

**Platform admin** — `admin.risk_queue_viewed`, `admin.audit_log_viewed`,
`admin.audit_log_exported`, `platform_config_update`,
`admin.safety_threshold_changed`, `admin.comrade_config_changed`,
`break_glass_chat_access`

### Declared but not emitted

These constants exist so that whoever builds the corresponding operation wires
the event at the same time, rather than inventing a fifth spelling. **The
operations themselves do not exist in the codebase yet:**

| Constant | Why not emitted |
|---|---|
| `USER_ASSIGNED_TO_SCHOOL`, `USER_REMOVED_FROM_SCHOOL` | A user's school is set at creation and never changed. There is no reassignment endpoint. |
| `COUNSELOR_ASSIGNED`, `COUNSELOR_UNASSIGNED` | `counselor_school_assignments` is only ever *read* (by analytics). No endpoint writes it. |
| `RISK_CASE_ASSIGNED` | `risk_assessments` has no assignee column. |
| `BOOKING_RESCHEDULED` | Rescheduling is done as cancel + book; both halves are already audited. |
| `COMRADE_SAFETY_TRIGGERED` | Realised as `safety_event:<category>`, which predates this module and is what existing rows use. Emitting both would mean two rows for one event. |
| `RISK_CASE_RESOLVED` | Realised as `risk_review:<status>`, which carries the counselor verdict alongside it. |

---

## 8. CSV export

`GET /admin/audit-logs/export`, platform admin only.

- **Streamed**, 500 rows per round trip, so peak memory is flat in the size of
  the export rather than proportional to it.
- **Capped** at `AUDIT_EXPORT_MAX_ROWS` (10,000). The cap is echoed in the
  `X-Export-Max-Rows` response header — a silently truncated audit export is a
  compliance problem, not a UX one.
- Uses the **same filters** as the on-screen list. An export that covered a
  different set than the screen it was taken from would be worse than none.
- Filename: `kio-audit-logs-YYYYMMDD-HHMMSSZ.csv` (UTC).
- The export event is written **and committed before the first byte streams** —
  the body is produced lazily after the endpoint returns, so a row written
  alongside it would only commit if the download completed. Taking a copy of
  the audit trail off the platform must be recorded whether or not it finished.
- Contains no secrets: `details` was scrubbed on the way *in*, and a test
  asserts the caller's own bearer token never appears in the output.

---

## 9. Retention

**Kio has no audit-log retention period, and implements no automatic deletion.**

This is a pending **legal and product decision**, not an oversight, and it is
deliberately not guessed at. Deciding it requires answers Kio does not yet have:

- DPDP obligations for behavioural records concerning minors — the same open
  question already recorded in `app/consent/policy.py`.
- Whether audit records concerning a student are in scope for a data-subject
  erasure request, or are exempt as security records.
- Any contractual retention floor a school district imposes.

Until that is settled, records accumulate. Two consequences to plan for:

1. **Growth.** The highest-volume events are `auth.refresh_token_rotated` and
   `comrade.session_started`. Indexes on `(action, created_at)` and
   `(tenant_id, created_at)` keep the admin page fast as the table grows.
2. **Deletion will be hard by construction.** The append-only trigger blocks
   `DELETE`. Any future retention policy must ship as a migration that drops
   the trigger, purges, and reinstalls it — deliberately awkward, so that
   deleting audit history is always an explicit, reviewed act.

> ⚠️ Do not implement a retention job, a purge endpoint, or a "cleanup" command
> until a retention period has been agreed with legal. See
> `docs/production-configuration.md`.

---

## 10. Relationship to structured logs and Sentry

Three systems, three jobs. They are not substitutes for each other.

| | Audit log | Structured logs | Sentry |
|---|---|---|---|
| **Question** | Who did what, to which record | What the system did, and how fast | What broke, and where |
| **Store** | Postgres `audit_logs` | stdout → host log drain | Sentry project (absent DSN = disabled) |
| **Lifetime** | Indefinite (see §9) | Host retention, typically days | Sentry retention |
| **Mutable** | No — append-only | Rotated/dropped by host | Resolvable/deletable |
| **Contains PII** | Actor identity, IP, target ids | Request metadata only | Deliberately narrow — no conversation content |
| **Audience** | Platform admin, incident review, compliance | Operators | Engineers |

The `request_id` is the join key across all three. An audit row is evidence; a
log line is context; a Sentry event is a defect. Do not use the audit log for
debugging volume, and do not rely on application logs as an audit trail — they
are mutable, and the host drops them on a schedule nobody chose for compliance
reasons.
