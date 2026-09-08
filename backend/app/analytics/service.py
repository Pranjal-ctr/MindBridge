"""
Kio Analytics Service

School-wide aggregates for the school-admin dashboard.

Two rules shape everything here:

1. **Real numbers or no numbers.** Every field is derived from a table the app
   actually writes to. A metric with no data returns None/empty and the UI says
   so — it never falls back to a plausible-looking constant. (The previous
   version returned a hardcoded 0.0 utilisation and read `analytics_snapshots`,
   a table only the demo seeder ever populated.)

2. **Aggregates must not identify a student.** A school admin can see the
   roster, so "1 student at critical risk" plus a small cohort is effectively a
   name. Below MIN_COHORT_SIZE every breakdown is suppressed — see
   `_suppressed_overview`.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    AnalyticsOverview,
    CounselorActivity,
    RiskBucket,
    SnapshotResponse,
    StressCategory,
    WellnessTrendPoint,
)
from database.models import (
    AnalyticsSnapshot,
    CounselorProfile,
    CounselorSchoolAssignment,
    CounselorSession,
    StressDistribution,
    StudentProfile,
    Tenant,
    User,
    WellnessRecord,
    WellnessScore,
)

# -------------------------------------------------------------------
# Privacy
# -------------------------------------------------------------------
# Minimum cohort size before any distribution is returned. A school admin can
# already see who is enrolled, so a per-tier count over a handful of students
# re-identifies them. 10 is the common k-anonymity floor for education
# reporting.
#
# Known residual: above the threshold, a tier containing a single student is
# still returned. Fixing that properly needs per-bucket suppression with
# complement-masking (otherwise the hidden bucket is recoverable by
# subtraction), which is worth doing before this ships to small schools.
MIN_COHORT_SIZE = 10

# Trailing window for "is this student still engaging"
ENGAGEMENT_WINDOW_DAYS = 7

# Months of history on the wellness trend chart
TREND_MONTHS = 6

_RISK_TIERS: list[tuple[str, str, str]] = [
    ("green", "Low Risk", "#10b981"),
    ("yellow", "Moderate", "#f59e0b"),
    ("red", "High Risk", "#ef4444"),
    ("critical", "Critical", "#dc2626"),
]


def _tenant_student_ids(tenant_id: uuid.UUID) -> Select:
    """Subquery: student_ids of every active student in this school.

    Used by every aggregate below, so tenant scoping lives in exactly one place.
    """
    return (
        select(StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )


def _month_starts(today: date, count: int) -> list[date]:
    """The first day of each of the last `count` months, oldest first."""
    months: list[date] = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


async def get_analytics_overview(
    db: AsyncSession, tenant_id: uuid.UUID
) -> AnalyticsOverview:
    """Build the school-wide overview."""
    now = datetime.now(timezone.utc)
    student_ids = _tenant_student_ids(tenant_id)

    school_name = (
        await db.execute(
            select(Tenant.tenant_name).where(Tenant.tenant_id == tenant_id)
        )
    ).scalar() or ""

    total_students = (
        await db.execute(select(func.count()).select_from(student_ids.subquery()))
    ).scalar() or 0

    counselors = await _counselor_activity(db, tenant_id, student_ids, now)

    if total_students < MIN_COHORT_SIZE:
        return _suppressed_overview(school_name, total_students, counselors, now)

    # --- Wellness score (current) -----------------------------------
    wellness_row = (
        await db.execute(
            select(
                func.avg(StudentProfile.wellness_score),
                func.count(StudentProfile.wellness_score),
            ).where(StudentProfile.student_id.in_(student_ids))
        )
    ).one()
    avg_score, scored_count = wellness_row

    # --- Engagement: completed a daily check-in in the window -------
    # mood_label is the marker of an official check-in; the legacy one-tap
    # mood endpoint writes rows without it and must not count here.
    window_start = now.date() - timedelta(days=ENGAGEMENT_WINDOW_DAYS - 1)
    checked_in = (
        await db.execute(
            select(func.count(func.distinct(WellnessRecord.student_id))).where(
                WellnessRecord.student_id.in_(student_ids),
                WellnessRecord.date_recorded >= window_start,
                WellnessRecord.mood_label.is_not(None),
            )
        )
    ).scalar() or 0

    return AnalyticsOverview(
        school_name=school_name,
        total_students=total_students,
        students_with_wellness_data=scored_count or 0,
        avg_wellness_score=round(float(avg_score), 1) if avg_score is not None else None,
        checked_in_last_7d=checked_in,
        checkin_participation=round(checked_in / total_students * 100, 1),
        counselors=counselors,
        risk_distribution=await _risk_distribution(db, student_ids),
        wellness_trend=await _wellness_trend(db, student_ids, now.date()),
        stress_by_category=await _stress_by_category(db, student_ids),
        cohort_suppressed=False,
        min_cohort_size=MIN_COHORT_SIZE,
        generated_at=now,
    )


def _suppressed_overview(
    school_name: str,
    total_students: int,
    counselors: CounselorActivity,
    now: datetime,
) -> AnalyticsOverview:
    """Headline counts only — the cohort is too small to break down safely.

    Counselor activity is kept: it describes staff coverage, not students.
    """
    return AnalyticsOverview(
        school_name=school_name,
        total_students=total_students,
        counselors=counselors,
        cohort_suppressed=True,
        min_cohort_size=MIN_COHORT_SIZE,
        generated_at=now,
    )


async def _risk_distribution(db: AsyncSession, student_ids: Select) -> list[RiskBucket]:
    """Students per risk tier. Always returns all four tiers, zeros included."""
    rows = (
        await db.execute(
            select(StudentProfile.risk_level, func.count().label("count"))
            .where(StudentProfile.student_id.in_(student_ids))
            .group_by(StudentProfile.risk_level)
        )
    ).all()
    counts = {row.risk_level: row.count for row in rows}

    return [
        RiskBucket(level=level, name=name, color=color, value=counts.get(level, 0))
        for level, name, color in _RISK_TIERS
    ]


async def _wellness_trend(
    db: AsyncSession, student_ids: Select, today: date
) -> list[WellnessTrendPoint]:
    """Monthly mean wellness score from the append-only wellness_scores history.

    Months with no recorded scores return score=None rather than 0 — a school
    with a quiet month has no data, not a catastrophic wellbeing collapse, and
    the chart must render that as a gap.
    """
    months = _month_starts(today, TREND_MONTHS)
    period_start = months[0]

    # `date_trunc('month', <timestamptz>)` truncates in the SESSION timezone,
    # not UTC. On a server set to Asia/Calcutta that puts the September bucket
    # at 2026-08-31T18:30Z, which matches no month key here — and the chart
    # comes back silently empty rather than erroring. Converting to UTC first
    # (`created_at AT TIME ZONE 'UTC'`) yields a naive UTC timestamp and makes
    # the bucketing independent of however the database is configured.
    bucket = func.date_trunc(
        "month", func.timezone("UTC", WellnessScore.created_at)
    ).label("bucket")
    rows = (
        await db.execute(
            select(
                bucket,
                func.avg(WellnessScore.overall_score).label("avg_score"),
                func.count(func.distinct(WellnessScore.student_id)).label("students"),
            )
            .where(
                WellnessScore.student_id.in_(student_ids),
                WellnessScore.created_at >= period_start,
            )
            .group_by(bucket)
        )
    ).all()

    by_month = {row.bucket.date(): row for row in rows}

    return [
        WellnessTrendPoint(
            month=m.strftime("%b"),
            month_start=m,
            score=round(float(by_month[m].avg_score), 1) if m in by_month else None,
            students=by_month[m].students if m in by_month else 0,
        )
        for m in months
    ]


async def _stress_by_category(
    db: AsyncSession, student_ids: Select
) -> list[StressCategory]:
    """How many students have each topic as their dominant stress source.

    Only each student's most recent distribution counts, so a student is
    represented once regardless of how much they chat. The dominant category is
    picked in Python rather than SQL: ranking keys inside a JSONB object is
    ugly in SQL, and this runs over one row per student at school scale.
    """
    rows = (
        await db.execute(
            select(StressDistribution.student_id, StressDistribution.categories)
            .where(StressDistribution.student_id.in_(student_ids))
            .order_by(
                StressDistribution.student_id,
                StressDistribution.created_at.desc(),
            )
            .distinct(StressDistribution.student_id)  # DISTINCT ON — latest per student
        )
    ).all()

    tally: Counter[str] = Counter()
    for _student_id, categories in rows:
        if not categories:
            continue
        numeric = {
            k: v for k, v in categories.items() if isinstance(v, (int, float))
        }
        if not numeric:
            continue
        top, score = max(numeric.items(), key=lambda kv: kv[1])
        # A flat all-zero distribution means "nothing detected", not "Academic".
        if score > 0:
            tally[top] += 1

    return [
        StressCategory(category=category, students=count)
        for category, count in tally.most_common()
    ]


async def _counselor_activity(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    student_ids: Select,
    now: datetime,
) -> CounselorActivity:
    """Counselling coverage for this school.

    Counselors are platform-wide (migration 008) and reach a school through
    counselor_school_assignments. The previous implementation joined
    counselor_profiles on users.tenant_id, which has not described the
    relationship since that migration and returned ~0 for every school.
    """
    active_counselors = (
        await db.execute(
            select(func.count(func.distinct(CounselorSchoolAssignment.counselor_id)))
            .select_from(CounselorSchoolAssignment)
            .join(
                CounselorProfile,
                CounselorProfile.counselor_id == CounselorSchoolAssignment.counselor_id,
            )
            .join(User, User.user_id == CounselorProfile.user_id)
            .where(
                CounselorSchoolAssignment.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
    ).scalar() or 0

    since = now - timedelta(days=30)
    completed = (
        select(
            func.count().label("sessions"),
            func.count(func.distinct(CounselorSession.student_id)).label("students"),
        )
        .where(
            CounselorSession.student_id.in_(student_ids),
            CounselorSession.scheduled_at >= since,
            CounselorSession.status == "completed",
        )
    )
    sessions, students_seen = (await db.execute(completed)).one()

    upcoming = (
        await db.execute(
            select(func.count()).where(
                CounselorSession.student_id.in_(student_ids),
                CounselorSession.scheduled_at >= now,
                CounselorSession.status == "scheduled",
            )
        )
    ).scalar() or 0

    return CounselorActivity(
        active_counselors=active_counselors,
        sessions_last_30d=sessions or 0,
        students_seen_last_30d=students_seen or 0,
        upcoming_sessions=upcoming,
    )


async def list_snapshots(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[SnapshotResponse], int]:
    """List stored analytics snapshots for a tenant.

    NOTE: nothing in the application writes `analytics_snapshots` — only
    database/seed.py does. Until a periodic job populates it this returns empty
    outside the demo tenant. The overview above deliberately no longer depends
    on it.
    """
    total = (
        await db.execute(
            select(func.count())
            .select_from(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.tenant_id == tenant_id)
        )
    ).scalar() or 0

    result = await db.execute(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.tenant_id == tenant_id)
        .order_by(AnalyticsSnapshot.snapshot_month.desc())
    )
    snapshots = result.scalars().all()

    return [SnapshotResponse.model_validate(s) for s in snapshots], total
