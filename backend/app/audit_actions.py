"""
Canonical audit action names, severities and results.

Why constants rather than free strings: an audit trail is only searchable if
the same event is spelled the same way every time. A typo in a string literal
does not fail anywhere -- it just quietly creates an event class nobody will
ever filter for.

On naming: the values keep this repo's existing dotted-lowercase convention
(`tenant.create`, `user.delete`) rather than switching to CONSTANT_CASE. The
nine actions that were already being emitted before this module existed keep
their **exact** historical strings, marked below. Renaming them would orphan
every row written before this change and break the admin page's saved filters,
which is a real cost for a purely cosmetic gain.

Severity is about operator attention, not about how bad the user's day is:
    info     -- routine, expected, high volume (login, booking)
    notice   -- worth noticing in aggregate (role change, schedule edit)
    warning  -- probably wrong, or a failed attempt at something privileged
    critical -- safety-relevant, or a privileged escape hatch being used
"""

from __future__ import annotations


# actor_role for events raised by a pipeline rather than by a person. Without
# this, a background-generated row is indistinguishable from one where we
# simply failed to record who did it -- and on a crisis event, "the student
# did this" is an actively misleading reading.
SYSTEM_ACTOR_ROLE = "system"


class AuditResult:
    """Whether the audited action actually happened."""

    SUCCESS = "success"
    FAILURE = "failure"


class AuditSeverity:
    """Operator-attention level. See module docstring."""

    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditEntity:
    """entity_type values, so the admin filter has a closed vocabulary."""

    USER = "user"
    TENANT = "tenant"
    CONVERSATION = "conversation"
    SESSION = "session"
    COUNSELOR = "counselor"
    SCHEDULE = "schedule"
    SCHEDULE_EXCEPTION = "schedule_exception"
    RISK_ASSESSMENT = "risk_assessment"
    NOTIFICATION = "notification"
    CONFIG = "config"
    AI_CONFIG = "ai_config"
    AUDIT_LOG = "audit_log"
    REFRESH_SESSION = "refresh_session"


class AuditAction:
    """
    Every audited action in Kio.

    Entries marked `# pre-existing` keep a string that was already being
    written to the table before this module existed. Do not change those
    values -- historical rows use them.
    """

    # --- Authentication --------------------------------------------
    LOGIN_SUCCESS = "auth.login_success"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    GOOGLE_LOGIN = "auth.google_login"
    SIGNUP = "auth.signup"
    EMAIL_VERIFIED = "auth.email_verified"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    REFRESH_TOKEN_ROTATED = "auth.refresh_token_rotated"
    REFRESH_TOKEN_REVOKED = "auth.refresh_token_revoked"
    SESSION_REVOKED = "auth.session_revoked"

    # --- Accounts / RBAC -------------------------------------------
    USER_CREATED = "user.create"           # pre-existing
    USER_UPDATED = "user.update"
    USER_DEACTIVATED = "user.delete"       # pre-existing (soft-delete)
    USER_REACTIVATED = "user.reactivate"
    ROLE_CHANGED = "user.role_changed"
    PROFILE_UPDATED = "user.profile_updated"
    PASSWORD_RESET_BY_ADMIN = "user.password_reset"

    # --- School administration -------------------------------------
    SCHOOL_CREATED = "tenant.create"       # pre-existing
    SCHOOL_UPDATED = "tenant.update"
    SCHOOL_ACTIVATED = "tenant.activate"
    SCHOOL_SUSPENDED = "tenant.suspend"
    SCHOOL_ARCHIVED = "tenant.archive"     # pre-existing
    # The four below are declared but not yet emitted: the operations they
    # describe do not exist in the codebase. A user's school is set at
    # creation and never changed, and counselor_school_assignments is only
    # ever read (by analytics), never written through an endpoint. They are
    # kept here so that whoever builds those operations wires the event at the
    # same time, rather than inventing a fifth spelling. See
    # docs/audit-logging.md, "Declared but not emitted".
    USER_ASSIGNED_TO_SCHOOL = "tenant.user_assigned"
    USER_REMOVED_FROM_SCHOOL = "tenant.user_removed"
    COUNSELOR_ASSIGNED = "counselor.assigned"
    COUNSELOR_UNASSIGNED = "counselor.unassigned"
    COUNSELOR_REGISTERED = "counselor.register"
    COUNSELOR_VERIFIED = "counselor.verify"

    # --- Safety -----------------------------------------------------
    RISK_ASSESSMENT_CREATED = "risk.assessment_created"
    RISK_LEVEL_CHANGED = "risk.level_changed"
    CRISIS_EVENT_CREATED = "crisis_workflow_triggered"   # pre-existing
    CRISIS_NOTIFICATION_CREATED = "crisis.notification_created"
    CRISIS_NOTIFICATION_SENT = "crisis.notification_sent"
    CRISIS_NOTIFICATION_FAILED = "crisis.notification_failed"
    RISK_CASE_VIEWED = "risk.case_viewed"
    # Declared, not emitted: risk_assessments has no assignee column, so there
    # is no assignment operation to hang this on. See docs/audit-logging.md.
    RISK_CASE_ASSIGNED = "risk.case_assigned"
    # Resolution is recorded as `risk_review:<status>` (RISK_REVIEW_PREFIX),
    # the pre-existing spelling that carries the counselor verdict alongside it.
    RISK_CASE_RESOLVED = "risk.case_resolved"

    # --- Comrade ----------------------------------------------------
    # Session-level only. Individual messages are deliberately never audited:
    # the volume would be enormous and the row would point straight at what a
    # student was saying and when.
    COMRADE_SESSION_STARTED = "comrade.session_started"
    COMRADE_SESSION_ENDED = "comrade.session_ended"
    # NOTE: not emitted under this name. A safety tripwire is recorded
    # per-category as `safety_event:<category>` (see SAFETY_EVENT_PREFIX),
    # which predates this module and is what existing rows use. Emitting this
    # as well would mean two rows for one event; filter on the prefix instead.
    COMRADE_SAFETY_TRIGGERED = "comrade.safety_triggered"

    # --- Booking / scheduling ---------------------------------------
    BOOKING_CREATED = "counselor_session:book"       # pre-existing
    BOOKING_CANCELLED = "counselor_session:cancel"   # pre-existing
    BOOKING_RESCHEDULED = "booking.rescheduled"
    BOOKING_CONFLICT = "booking.conflict"
    COUNSELOR_SCHEDULE_CREATED = "schedule.created"
    COUNSELOR_SCHEDULE_UPDATED = "schedule.updated"
    COUNSELOR_SCHEDULE_DELETED = "schedule.deleted"
    COUNSELOR_SETTINGS_UPDATED = "schedule.settings_updated"
    TIME_OFF_CREATED = "schedule.time_off_created"
    TIME_OFF_DELETED = "schedule.time_off_deleted"

    # --- Platform admin ---------------------------------------------
    RISK_QUEUE_VIEWED = "admin.risk_queue_viewed"
    AUDIT_LOG_VIEWED = "admin.audit_log_viewed"
    AUDIT_LOG_EXPORTED = "admin.audit_log_exported"
    SETTINGS_CHANGED = "platform_config_update"      # pre-existing
    SAFETY_THRESHOLD_CHANGED = "admin.safety_threshold_changed"
    COMRADE_CONFIGURATION_CHANGED = "admin.comrade_config_changed"
    #: Which provider/model answers every student. Changing it is an
    #: administrative act with cost and safety weight, so it is audited even
    #: though ai_usage_logs already records each individual call.
    AI_CONFIGURATION_CHANGED = "admin.ai_configuration_changed"

    # --- AI operational events --------------------------------------
    # Deliberately sparse. Per-call telemetry lives in ai_usage_logs; these
    # exist for the handful of events an operator would want to find in the
    # audit trail months later, and are rate-limited by their own nature
    # (a breaker trips once, not once per request).
    AI_PROVIDER_FAILURE = "ai.provider_failure"
    AI_FALLBACK_USED = "ai.fallback_used"
    AI_USAGE_GUARDRAIL_BLOCKED = "ai.usage_guardrail_blocked"
    BREAK_GLASS_CHAT_ACCESS = "break_glass_chat_access"   # pre-existing prefix


# Actions whose historical string was built with a dynamic suffix. Kept as
# prefixes because rows already exist with the suffix attached.
SAFETY_EVENT_PREFIX = "safety_event:"           # pre-existing
SAFETY_SOFT_SIGNAL_PREFIX = "safety_soft_signal:"   # pre-existing
RISK_REVIEW_PREFIX = "risk_review:"             # pre-existing


def _all_actions() -> frozenset[str]:
    return frozenset(
        v for k, v in vars(AuditAction).items()
        if not k.startswith("_") and isinstance(v, str)
    )


KNOWN_ACTIONS = _all_actions()
