"""
MindBridge Risk Service
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.risk.schemas import RiskAlertResponse, RiskAssessmentCreate, RiskAssessmentResponse
from database.models import RiskAssessment, StudentProfile, User


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
