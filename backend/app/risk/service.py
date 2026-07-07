"""
MindBridge Risk Service
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.risk.schemas import (
    RiskAlertResponse,
    RiskAssessmentCreate,
    RiskAssessmentResponse,
    RiskQueueItem,
    RiskReviewUpdate,
)
from database.models import AuditLog, RiskAssessment, StudentProfile, User


async def create_risk_assessment(
    db: AsyncSession, payload: RiskAssessmentCreate
) -> RiskAssessmentResponse:
    """Create a new risk assessment."""
    assessment = RiskAssessment(
        student_id=payload.student_id,
        conversation_id=payload.conversation_id,
        risk_score=payload.risk_score,
        risk_level=payload.risk_level,
        trigger_reason=payload.trigger_reason,
        generated_by=payload.generated_by,
    )
    db.add(assessment)

    # Update student risk level
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == payload.student_id)
    )
    student = result.scalar_one_or_none()
    if student:
        student.risk_level = payload.risk_level

    await db.flush()
    await db.refresh(assessment)
    return RiskAssessmentResponse.model_validate(assessment)


async def list_risk_assessments(
    db: AsyncSession, student_id: uuid.UUID
) -> tuple[list[RiskAssessmentResponse], int]:
    """List risk assessments for a student."""
    count_result = await db.execute(
        select(func.count()).select_from(RiskAssessment).where(
            RiskAssessment.student_id == student_id
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id)
        .order_by(RiskAssessment.created_at.desc())
    )
    assessments = result.scalars().all()

    return [RiskAssessmentResponse.model_validate(a) for a in assessments], total


async def get_active_risk_alerts(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[RiskAlertResponse], int]:
    """Get active high-risk alerts for a tenant (counselor view)."""
    query = (
        select(RiskAssessment, StudentProfile, User)
        .join(StudentProfile, RiskAssessment.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(
            User.tenant_id == tenant_id,
            RiskAssessment.risk_level.in_(["red", "critical"]),
        )
        .order_by(RiskAssessment.created_at.desc())
    )

    result = await db.execute(query)
    rows = result.all()

    alerts = []
    for assessment, student, user in rows:
        alerts.append(
            RiskAlertResponse(
                risk_id=assessment.risk_id,
                student_id=assessment.student_id,
                student_name=f"{user.first_name} {user.last_name}",
                risk_level=assessment.risk_level,
                risk_score=float(assessment.risk_score) if assessment.risk_score else None,
                trigger_reason=assessment.trigger_reason,
                created_at=assessment.created_at,
            )
        )

    return alerts, len(alerts)


# -------------------------------------------------------------------
# Counselor review queue
# -------------------------------------------------------------------

_LEVEL_SEVERITY = case(
    (RiskAssessment.risk_level == "critical", 3),
    (RiskAssessment.risk_level == "red", 2),
    (RiskAssessment.risk_level == "yellow", 1),
    else_=0,
)


async def get_risk_queue(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[RiskQueueItem], int]:
    """Pending assessments for the tenant, most severe first, then newest."""
    result = await db.execute(
        select(RiskAssessment, User)
        .join(StudentProfile, RiskAssessment.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(
            User.tenant_id == tenant_id,
            RiskAssessment.review_status == "pending",
        )
        .order_by(_LEVEL_SEVERITY.desc(), RiskAssessment.created_at.desc())
    )
    rows = result.all()

    items = [
        RiskQueueItem(
            risk_id=assessment.risk_id,
            student_id=assessment.student_id,
            student_name=f"{user.first_name} {user.last_name}",
            risk_level=assessment.risk_level,
            risk_score=float(assessment.risk_score) if assessment.risk_score is not None else None,
            categories=assessment.categories,
            summary=assessment.summary,
            trigger_reason=assessment.trigger_reason,
            generated_by=assessment.generated_by,
            created_at=assessment.created_at,
        )
        for assessment, user in rows
    ]
    return items, len(items)


async def review_risk_assessment(
    db: AsyncSession,
    risk_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    payload: RiskReviewUpdate,
) -> RiskAssessmentResponse:
    """Acknowledge or resolve a queued assessment (tenant-scoped, audit-logged)."""
    result = await db.execute(
        select(RiskAssessment)
        .join(StudentProfile, RiskAssessment.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(RiskAssessment.risk_id == risk_id, User.tenant_id == tenant_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    if assessment.review_status is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Assessment is not in the review queue"
        )

    assessment.review_status = payload.review_status
    assessment.reviewed_by = reviewer_user_id
    assessment.reviewed_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        user_id=reviewer_user_id,
        action=f"risk_review:{payload.review_status}",
        entity_type="risk_assessment",
        entity_id=risk_id,
    ))
    await db.flush()
    await db.refresh(assessment)
    return RiskAssessmentResponse.model_validate(assessment)
