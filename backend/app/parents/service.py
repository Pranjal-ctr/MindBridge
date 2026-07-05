"""
MindBridge Parents Service
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.parents.schemas import (
    ChildInsightResponse,
    ChildSummary,
    RecommendationResponse,
    StressFactor,
    WellnessTrendPoint,
)
from database.models import (
    ParentInsightHistory,
    ParentProfile,
    StudentParentLink,
    StudentProfile,
    User,
    WellnessRecord,
)


async def get_linked_children(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ChildSummary]:
    """Get all children linked to a parent."""
    # Get parent profile
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")

    # Get linked students
    links_result = await db.execute(
        select(StudentParentLink, StudentProfile, User)
        .join(StudentProfile, StudentParentLink.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentParentLink.parent_id == parent.parent_id)
    )
    rows = links_result.all()

    children = []
    for link, student, user in rows:
        children.append(
            ChildSummary(
                student_id=student.student_id,
                first_name=user.first_name,
                last_name=user.last_name,
                age=student.age,
                wellness_score=float(student.wellness_score) if student.wellness_score else None,
                risk_level=student.risk_level or "green",
                relationship=link.relationship_,
            )
        )

    return children


async def get_child_insights(
    db: AsyncSession, user_id: uuid.UUID, student_id: uuid.UUID
) -> ChildInsightResponse:
    """Get detailed insights for a parent's child."""
    # Verify parent-child link
    await _verify_parent_child_link(db, user_id, student_id)

    # Get student info
    result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.student_id == student_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    student, user = row

    # Get latest insight
    insight_result = await db.execute(
        select(ParentInsightHistory)
        .where(ParentInsightHistory.student_id == student_id)
        .order_by(ParentInsightHistory.generated_at.desc())
        .limit(1)
    )
    latest_insight = insight_result.scalar_one_or_none()

    # Get wellness trend (last 7 records)
    wellness_result = await db.execute(
        select(WellnessRecord)
        .where(WellnessRecord.student_id == student_id)
        .order_by(WellnessRecord.date_recorded.desc())
        .limit(7)
    )
    records = list(wellness_result.scalars().all())
    records.reverse()

    trend = [
        WellnessTrendPoint(
            date=r.date_recorded.strftime("%a"),
            score=float(
                (r.mood_score + r.energy_score + r.confidence_score) / 3 * 10
                if r.mood_score and r.energy_score and r.confidence_score
                else 0
            ),
        )
        for r in records
    ]

    return ChildInsightResponse(
        student_id=student.student_id,
        student_name=f"{user.first_name} {user.last_name}",
        wellness_score=float(student.wellness_score) if student.wellness_score else None,
        risk_level=student.risk_level or "green",
        summary=latest_insight.summary if latest_insight else None,
        wellness_trend=trend,
        recommendations=(
            latest_insight.recommendations.split("|") if latest_insight and latest_insight.recommendations else []
        ),
        last_updated=latest_insight.generated_at if latest_insight else None,
    )


async def _verify_parent_child_link(
    db: AsyncSession, user_id: uuid.UUID, student_id: uuid.UUID
) -> None:
    """Verify that the parent has a link to the child."""
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a parent")

    link_result = await db.execute(
        select(StudentParentLink).where(
            StudentParentLink.parent_id == parent.parent_id,
            StudentParentLink.student_id == student_id,
        )
    )
    if not link_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this student's data",
        )
