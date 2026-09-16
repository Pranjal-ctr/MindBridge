"""
Crisis workflow: when an AI assessment crosses the configured threshold,
queue the assessment for counselor review, write a timeline event, fan out
content-free notifications (counselors/school admins always; linked parents
when allowed), force a parent-insight refresh, and audit-log the trigger.

Parents NEVER receive message content or risk categories -- only that the
risk level changed and where to look.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_audit
from app.audit_actions import (
    SYSTEM_ACTOR_ROLE,
    AuditAction,
    AuditEntity,
    AuditResult,
    AuditSeverity,
)
from app.intelligence.analysis import AnalysisOutcome
from app.intelligence.config import load_config
from app.notifications.service import notify_users
from database.models import (
    ParentProfile,
    RiskAssessment,
    SchoolSettings,
    StudentParentLink,
    StudentProfile,
    StudentTimeline,
    User,
)

logger = logging.getLogger(__name__)

# Suppress repeat notification fan-outs for the same student inside this window
# (the queue entry and timeline event are still always created).
_NOTIFY_SUPPRESSION_WINDOW = timedelta(hours=1)


async def _email_staff_alert(
    db: AsyncSession,
    staff_ids: list[uuid.UUID],
    student_name: str,
    risk_level: str,
) -> None:
    """Email the on-call staff about a queued high-risk assessment.

    An in-app notification only reaches someone already signed in and looking.
    Email is what reaches a counselor who is not currently in Kio — which, out
    of school hours, is all of them.

    Best-effort throughout: `try_send` never raises, and this whole call is
    wrapped by the caller. A mail outage must never stop the assessment from
    being queued, which is the part that cannot be lost.
    """
    from app.config import settings
    from app.email.service import try_send
    from app.email.templates import crisis_alert_email

    rows = (await db.execute(
        select(User.email, User.first_name).where(User.user_id.in_(staff_ids))
    )).all()

    link = f"{settings.FRONTEND_URL.rstrip('/')}/counselor"

    for email, first_name in rows:
        if not email:
            continue
        subject, text, html = crisis_alert_email(
            staff_first_name=first_name or "",
            student_name=student_name,
            risk_level=risk_level,
            link=link,
        )
        await try_send(to=email, subject=subject, body=text, html=html)


async def _linked_parent_user_ids(db: AsyncSession, student_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(ParentProfile.user_id)
        .join(StudentParentLink, StudentParentLink.parent_id == ParentProfile.parent_id)
        .where(StudentParentLink.student_id == student_id)
    )
    return [row[0] for row in result.all()]


async def _recently_alerted(
    db: AsyncSession, student_id: uuid.UUID, exclude_risk_id: uuid.UUID
) -> bool:
    cutoff = datetime.now(timezone.utc) - _NOTIFY_SUPPRESSION_WINDOW
    result = await db.execute(
        select(RiskAssessment.risk_id).where(
            RiskAssessment.student_id == student_id,
            RiskAssessment.review_status.isnot(None),
            RiskAssessment.risk_id != exclude_risk_id,
            RiskAssessment.created_at >= cutoff,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def evaluate_and_trigger_crisis(
    db: AsyncSession,
    student_id: uuid.UUID,
    student_user_id: uuid.UUID,
    outcome: AnalysisOutcome,
) -> bool:
    """Run the crisis workflow if the assessment crosses the threshold.

    Returns True when triggered. Flushes but does not commit.
    """
    crisis_cfg = await load_config(db, "crisis")
    assessment = outcome.assessment

    over_threshold = outcome.analysis.risk.overall >= float(crisis_cfg["trigger_score"])
    severe_level = assessment.risk_level in ("red", "critical")
    if not (over_threshold or severe_level):
        return False

    # 1. Queue for counselor review (this IS the queue entry)
    if assessment.review_status is None:
        assessment.review_status = "pending"

    # 2. Timeline event (neutral wording)
    db.add(StudentTimeline(
        student_id=student_id,
        event_type="risk_alert",
        reference_id=assessment.risk_id,
        event_description=f"Risk level {assessment.risk_level} -- queued for counselor review",
    ))

    # School scope for the audit row. One indexed primary-key lookup; the
    # notification fan-out below re-reads the same user, but only on the
    # branch that is not suppressed, so this cannot be folded into it.
    tenant_id = (await db.execute(
        select(User.tenant_id).where(User.user_id == student_user_id)
    )).scalar_one_or_none()

    # 3. Audit log
    #
    # The actor is the student only in the sense that the assessment is about
    # them -- nobody *performed* this action. It is raised by the analysis
    # pipeline, so actor_role records that rather than leaving a reader to
    # assume a student triggered their own crisis workflow.
    #
    # risk_level is recorded because the whole point of the row is which
    # threshold was crossed. The narrative that produced it is not: the
    # assessment is reachable by id for anyone with clinical standing to read it.
    await log_audit(
        db,
        user_id=student_user_id,
        action=AuditAction.CRISIS_EVENT_CREATED,
        entity_type=AuditEntity.RISK_ASSESSMENT,
        entity_id=assessment.risk_id,
        details={"risk_level": assessment.risk_level},
        actor_role=SYSTEM_ACTOR_ROLE,
        tenant_id=tenant_id,
        severity=AuditSeverity.CRITICAL,
    )

    # 4. Notification fan-out (suppressed if we alerted for this student recently)
    if not await _recently_alerted(db, student_id, assessment.risk_id):
        student_user = (await db.execute(
            select(User).where(User.user_id == student_user_id)
        )).scalar_one_or_none()

        if student_user is not None:
            staff_ids = [
                row[0] for row in (await db.execute(
                    select(User.user_id).where(
                        User.tenant_id == student_user.tenant_id,
                        User.role.in_(["counselor", "school_admin"]),
                        User.is_active == True,  # noqa: E712
                    )
                )).all()
            ]
            student_name = f"{student_user.first_name} {student_user.last_name}".strip()

            if staff_ids:
                await notify_users(
                    db, staff_ids,
                    title="High-risk alert",
                    message=f"High-risk alert: {student_name} -- review required.",
                )
                # Recipient *count*, never the names: this row exists to prove
                # the alert fanned out, and reconstructing who was told what
                # about which student is not what an audit trail is for.
                await log_audit(
                    db,
                    user_id=student_user_id,
                    action=AuditAction.CRISIS_NOTIFICATION_CREATED,
                    entity_type=AuditEntity.NOTIFICATION,
                    entity_id=assessment.risk_id,
                    details={"channel": "in_app", "recipient_count": len(staff_ids)},
                    actor_role=SYSTEM_ACTOR_ROLE,
                    tenant_id=tenant_id,
                    severity=AuditSeverity.CRITICAL,
                )

                # Email as well as in-app: the in-app badge only reaches staff
                # who are already signed in. Non-fatal — the queue entry above
                # is the durable part and must survive a mail failure.
                if crisis_cfg.get("email_staff", True):
                    try:
                        await _email_staff_alert(
                            db, staff_ids, student_name, assessment.risk_level
                        )
                        email_error = None
                    except Exception as e:  # noqa: BLE001
                        email_error = e
                        logger.warning(
                            "Crisis staff email failed (non-fatal): %s", str(e)
                        )

                    # A crisis alert that never reached anyone is the single
                    # most important thing this table can tell an operator, so
                    # the failure is recorded as loudly as the success.
                    await log_audit(
                        db,
                        user_id=student_user_id,
                        action=(
                            AuditAction.CRISIS_NOTIFICATION_FAILED
                            if email_error is not None
                            else AuditAction.CRISIS_NOTIFICATION_SENT
                        ),
                        entity_type=AuditEntity.NOTIFICATION,
                        entity_id=assessment.risk_id,
                        details={
                            "channel": "email",
                            "recipient_count": len(staff_ids),
                            # Exception *type* only. The message can carry an
                            # SMTP transcript, which can carry an address.
                            **({"error_type": type(email_error).__name__}
                               if email_error is not None else {}),
                        },
                        actor_role=SYSTEM_ACTOR_ROLE,
                        tenant_id=tenant_id,
                        result=(
                            AuditResult.FAILURE if email_error is not None
                            else AuditResult.SUCCESS
                        ),
                        severity=AuditSeverity.CRITICAL,
                    )

            # Parents: content-free, gated by school settings + platform config
            if crisis_cfg.get("notify_parents", True):
                settings_row = (await db.execute(
                    select(SchoolSettings).where(
                        SchoolSettings.tenant_id == student_user.tenant_id
                    )
                )).scalar_one_or_none()
                parents_allowed = settings_row is None or settings_row.allow_parent_notifications

                if parents_allowed:
                    parent_ids = await _linked_parent_user_ids(db, student_id)
                    if parent_ids:
                        await notify_users(
                            db, parent_ids,
                            title="Wellness update",
                            message=(
                                f"{student_user.first_name}'s risk level has changed -- "
                                "please check today's insights."
                            ),
                        )

    # 5. Force a parent-insight refresh so the dashboard reflects the change
    try:
        from app.intelligence.insights import maybe_refresh_parent_insight

        await maybe_refresh_parent_insight(db, student_id, force=True)
    except Exception as e:
        logger.warning("Crisis insight refresh failed (non-fatal): %s", str(e))

    logger.info(
        "Crisis workflow triggered for student %s (risk %.0f, level %s)",
        student_id, outcome.analysis.risk.overall, assessment.risk_level,
    )
    return True
