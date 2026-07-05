"""
MindBridge Analytics Service
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    AnalyticsOverview,
    RiskBucket,
    SnapshotResponse,
    WellnessTrendPoint,
)
from database.models import (
    AnalyticsSnapshot,
    CounselorProfile,
    CounselorSession,
    StudentProfile,
    User,
)


async def get_analytics_overview(
    db: AsyncSession, tenant_id: uuid.UUID
) -> AnalyticsOverview:
    """Generate school-wide analytics overview."""

    # Total students
    student_count = await db.execute(
        select(func.count())
        .select_from(StudentProfile)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id, User.is_active == True)  # noqa: E712
    )
    total_students = student_count.scalar() or 0

    # Average wellness
    avg_wellness = await db.execute(
        select(func.avg(StudentProfile.wellness_score))
        .join(User, StudentProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id)
    )
    avg_score = avg_wellness.scalar() or 0

    # Active counselors
    counselor_count = await db.execute(
        select(func.count())
        .select_from(CounselorProfile)
        .join(User, CounselorProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id, User.is_active == True)  # noqa: E712
    )
    active_counselors = counselor_count.scalar() or 0

    # Risk distribution
    risk_query = await db.execute(
        select(
            StudentProfile.risk_level,
            func.count().label("count"),
        )
        .join(User, StudentProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id)
        .group_by(StudentProfile.risk_level)
    )
    risk_rows = risk_query.all()

    color_map = {"green": "#10b981", "yellow": "#f59e0b", "red": "#ef4444", "critical": "#dc2626"}
    label_map = {"green": "Low Risk", "yellow": "Moderate", "red": "High Risk", "critical": "Critical"}

    risk_distribution = [
        RiskBucket(
            name=label_map.get(row.risk_level, row.risk_level),
            value=row.count,
            color=color_map.get(row.risk_level, "#6b7280"),
        )
        for row in risk_rows
    ]

    # Wellness trend from snapshots
    trend_result = await db.execute(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.tenant_id == tenant_id)
        .order_by(AnalyticsSnapshot.snapshot_month.asc())
        .limit(12)
    )
    snapshots = trend_result.scalars().all()

    wellness_trend = [
        WellnessTrendPoint(
            month=s.snapshot_month.strftime("%b"),
            score=float(s.avg_wellness) if s.avg_wellness else 0,
        )
        for s in snapshots
    ]

    return AnalyticsOverview(
        total_students=total_students,
        avg_wellness_score=float(avg_score),
        active_counselors=active_counselors,
        counselor_utilization=0.0,  # Would need booking data
        risk_distribution=risk_distribution,
        wellness_trend=wellness_trend,
    )


async def list_snapshots(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[SnapshotResponse], int]:
    """List analytics snapshots for a tenant."""
    count_result = await db.execute(
        select(func.count())
        .select_from(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.tenant_id == tenant_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.tenant_id == tenant_id)
        .order_by(AnalyticsSnapshot.snapshot_month.desc())
    )
    snapshots = result.scalars().all()

    return [SnapshotResponse.model_validate(s) for s in snapshots], total
