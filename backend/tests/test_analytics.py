"""
School analytics tests.

This module had no coverage at all before, which is how four of the seven
overview fields came to be empty, hardcoded, or joined on a relationship that
migration 008 replaced.

The behaviours worth protecting: aggregates are scoped to one school, small
cohorts are suppressed, and "no data" is distinguishable from "zero".
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import MIN_COHORT_SIZE, TREND_MONTHS
from app.auth.utils import create_access_token, hash_password
from database.models import (
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

pytestmark = pytest.mark.asyncio


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

async def _make_school(db: AsyncSession, name: str = "Analytics High") -> Tenant:
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name=name,
        tenant_type="school",
        school_code=f"AN{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(tenant)
    await db.flush()
    return tenant


async def _add_students(
    db: AsyncSession,
    tenant: Tenant,
    count: int,
    *,
    risk_level: str = "green",
    wellness_score: float | None = None,
    is_active: bool = True,
) -> list[StudentProfile]:
    profiles = []
    for _ in range(count):
        user = User(
            user_id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            email=f"s_{uuid.uuid4().hex[:10]}@test.com",
            password_hash=hash_password("TestPassword123!"),
            role="student",
            first_name="Test",
            last_name="Student",
            is_active=is_active,
        )
        db.add(user)
        await db.flush()

        profile = StudentProfile(
            user_id=user.user_id,
            risk_level=risk_level,
            wellness_score=wellness_score,
        )
        db.add(profile)
        await db.flush()
        profiles.append(profile)
    return profiles


async def _school_admin_headers(db: AsyncSession, tenant: Tenant) -> dict[str, str]:
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=f"sa_{uuid.uuid4().hex[:10]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="school_admin",
        first_name="School",
        last_name="Admin",
    )
    db.add(user)
    await db.flush()
    token = create_access_token({
        "sub": str(user.user_id),
        "tenant_id": str(tenant.tenant_id),
        "role": "school_admin",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> Tenant:
    return await _make_school(db_session)


@pytest_asyncio.fixture
async def sa_headers(db_session: AsyncSession, school: Tenant) -> dict[str, str]:
    return await _school_admin_headers(db_session, school)


# -------------------------------------------------------------------
# Access control
# -------------------------------------------------------------------

async def test_students_cannot_read_school_analytics(
    client: AsyncClient, student_auth_headers
):
    resp = await client.get("/analytics/overview", headers=student_auth_headers)
    assert resp.status_code == 403


async def test_analytics_requires_auth(client: AsyncClient):
    resp = await client.get("/analytics/overview")
    assert resp.status_code == 403


# -------------------------------------------------------------------
# Small-cohort suppression
# -------------------------------------------------------------------

async def test_small_cohort_is_suppressed(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """Below the k-anonymity floor, no breakdown may be returned.

    A school admin knows the roster, so "1 student at critical risk" in a
    9-student school names them.
    """
    await _add_students(db_session, school, MIN_COHORT_SIZE - 1, risk_level="critical")

    resp = await client.get("/analytics/overview", headers=sa_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["cohort_suppressed"] is True
    assert body["total_students"] == MIN_COHORT_SIZE - 1
    assert body["risk_distribution"] == []
    assert body["stress_by_category"] == []
    assert body["wellness_trend"] == []
    # Staff coverage is not student data, so it survives suppression.
    assert "counselors" in body


async def test_cohort_at_threshold_is_reported(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    await _add_students(db_session, school, MIN_COHORT_SIZE)

    resp = await client.get("/analytics/overview", headers=sa_headers)
    body = resp.json()

    assert body["cohort_suppressed"] is False
    assert body["total_students"] == MIN_COHORT_SIZE
    assert len(body["risk_distribution"]) == 4


# -------------------------------------------------------------------
# Risk distribution
# -------------------------------------------------------------------

async def test_risk_distribution_counts_and_covers_all_tiers(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    await _add_students(db_session, school, 8, risk_level="green")
    await _add_students(db_session, school, 3, risk_level="yellow")
    await _add_students(db_session, school, 1, risk_level="red")

    resp = await client.get("/analytics/overview", headers=sa_headers)
    buckets = {b["level"]: b["value"] for b in resp.json()["risk_distribution"]}

    assert buckets == {"green": 8, "yellow": 3, "red": 1, "critical": 0}


async def test_inactive_students_are_excluded(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """A disabled account must not inflate the roster or the risk counts."""
    await _add_students(db_session, school, 10, risk_level="green")
    await _add_students(db_session, school, 4, risk_level="red", is_active=False)

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()
    buckets = {b["level"]: b["value"] for b in body["risk_distribution"]}

    assert body["total_students"] == 10
    assert buckets["red"] == 0


# -------------------------------------------------------------------
# Tenant isolation
# -------------------------------------------------------------------

async def test_other_schools_students_do_not_leak(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    other = await _make_school(db_session, "Other High")
    await _add_students(db_session, school, 10, risk_level="green")
    await _add_students(db_session, other, 25, risk_level="critical")

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()
    buckets = {b["level"]: b["value"] for b in body["risk_distribution"]}

    assert body["total_students"] == 10
    assert buckets["critical"] == 0


# -------------------------------------------------------------------
# Wellness score: absent vs zero
# -------------------------------------------------------------------

async def test_avg_wellness_is_null_when_nothing_recorded(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """No scores yet must read as null, never 0.0 — zero is a real score and
    would render as a school in total crisis."""
    await _add_students(db_session, school, 12, wellness_score=None)

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()

    assert body["avg_wellness_score"] is None
    assert body["students_with_wellness_data"] == 0


async def test_avg_wellness_averages_only_scored_students(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    await _add_students(db_session, school, 5, wellness_score=80)
    await _add_students(db_session, school, 5, wellness_score=60)
    await _add_students(db_session, school, 4, wellness_score=None)

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()

    assert body["total_students"] == 14
    assert body["students_with_wellness_data"] == 10
    assert body["avg_wellness_score"] == 70.0


# -------------------------------------------------------------------
# Engagement
# -------------------------------------------------------------------

async def test_participation_counts_only_official_checkins(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """mood_label marks an official daily check-in. Rows written by the legacy
    one-tap /wellness/mood endpoint have none and must not count."""
    students = await _add_students(db_session, school, 10)
    today = datetime.now(timezone.utc).date()

    for profile in students[:4]:
        db_session.add(WellnessRecord(
            student_id=profile.student_id,
            date_recorded=today,
            mood_label="happy",
        ))
    # Legacy sentiment row — no mood_label.
    db_session.add(WellnessRecord(
        student_id=students[5].student_id,
        date_recorded=today,
        mood_score=7,
    ))
    # Real check-in, but outside the 7-day window.
    db_session.add(WellnessRecord(
        student_id=students[6].student_id,
        date_recorded=today - timedelta(days=30),
        mood_label="sad",
    ))
    await db_session.flush()

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()

    assert body["checked_in_last_7d"] == 4
    assert body["checkin_participation"] == 40.0


# -------------------------------------------------------------------
# Wellness trend
# -------------------------------------------------------------------

async def test_trend_returns_fixed_window_with_gaps_as_null(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """A month with no recorded scores is a gap, not a score of zero.

    This also pins the month bucketing to UTC. `date_trunc` works in the
    database session's timezone, so on a non-UTC server (this test DB reports
    Asia/Calcutta) the current month's bucket lands in the previous month and
    every point silently reads null. Asserting the newest point is populated
    catches that regression.
    """
    students = await _add_students(db_session, school, 10)
    now = datetime.now(timezone.utc)

    for profile in students[:3]:
        db_session.add(WellnessScore(
            student_id=profile.student_id,
            overall_score=70,
            created_at=now,
        ))
    await db_session.flush()

    trend = (await client.get("/analytics/overview", headers=sa_headers)).json()["wellness_trend"]

    assert len(trend) == TREND_MONTHS
    # Oldest first, current month last.
    assert trend[-1]["score"] == 70.0
    assert trend[-1]["students"] == 3
    # Earlier months had no data at all.
    assert trend[0]["score"] is None
    assert trend[0]["students"] == 0


# -------------------------------------------------------------------
# Stress distribution
# -------------------------------------------------------------------

async def test_stress_uses_latest_row_per_student(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """One student, many messages, must still count once — and by their most
    recent dominant topic, not their first."""
    students = await _add_students(db_session, school, 10)
    now = datetime.now(timezone.utc)

    db_session.add(StressDistribution(
        student_id=students[0].student_id,
        categories={"Academic": 90, "Family": 10},
        created_at=now - timedelta(days=5),
    ))
    db_session.add(StressDistribution(
        student_id=students[0].student_id,
        categories={"Academic": 5, "Family": 80},
        created_at=now,
    ))
    db_session.add(StressDistribution(
        student_id=students[1].student_id,
        categories={"Academic": 70, "Friends": 20},
        created_at=now,
    ))
    await db_session.flush()

    stress = (await client.get("/analytics/overview", headers=sa_headers)).json()["stress_by_category"]
    tally = {row["category"]: row["students"] for row in stress}

    assert tally == {"Family": 1, "Academic": 1}


async def test_all_zero_distribution_is_not_counted(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """A flat all-zero distribution means nothing was detected. Taking max()
    would otherwise credit whichever key happened to sort first."""
    students = await _add_students(db_session, school, 10)
    db_session.add(StressDistribution(
        student_id=students[0].student_id,
        categories={"Academic": 0, "Family": 0},
        created_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()

    stress = (await client.get("/analytics/overview", headers=sa_headers)).json()["stress_by_category"]

    assert stress == []


# -------------------------------------------------------------------
# Counselor activity
# -------------------------------------------------------------------

async def test_counselors_counted_via_school_assignment(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    """Counselors are platform-wide since migration 008 and reach a school
    through counselor_school_assignments — not through users.tenant_id, which
    is what the previous implementation joined on."""
    other = await _make_school(db_session, "Unrelated High")
    await _add_students(db_session, school, 10)

    counselor_user = User(
        user_id=uuid.uuid4(),
        tenant_id=other.tenant_id,          # deliberately NOT the school we query
        email=f"c_{uuid.uuid4().hex[:10]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="counselor",
        first_name="Platform",
        last_name="Counselor",
    )
    db_session.add(counselor_user)
    await db_session.flush()

    counselor = CounselorProfile(user_id=counselor_user.user_id, is_verified=True)
    db_session.add(counselor)
    await db_session.flush()

    db_session.add(CounselorSchoolAssignment(
        counselor_id=counselor.counselor_id,
        tenant_id=school.tenant_id,
    ))
    await db_session.flush()

    body = (await client.get("/analytics/overview", headers=sa_headers)).json()

    assert body["counselors"]["active_counselors"] == 1


async def test_session_counts_split_completed_and_upcoming(
    client: AsyncClient, db_session: AsyncSession, school: Tenant, sa_headers
):
    students = await _add_students(db_session, school, 10)
    now = datetime.now(timezone.utc)

    counselor_user = User(
        user_id=uuid.uuid4(),
        tenant_id=school.tenant_id,
        email=f"c_{uuid.uuid4().hex[:10]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="counselor",
        first_name="C",
        last_name="One",
    )
    db_session.add(counselor_user)
    await db_session.flush()
    counselor = CounselorProfile(user_id=counselor_user.user_id, is_verified=True)
    db_session.add(counselor)
    await db_session.flush()

    # Two completed sessions for the same student inside the window: two
    # sessions, one student seen.
    for days_ago in (3, 10):
        db_session.add(CounselorSession(
            student_id=students[0].student_id,
            counselor_id=counselor.counselor_id,
            scheduled_at=now - timedelta(days=days_ago),
            status="completed",
        ))
    # Outside the 30-day window.
    db_session.add(CounselorSession(
        student_id=students[1].student_id,
        counselor_id=counselor.counselor_id,
        scheduled_at=now - timedelta(days=45),
        status="completed",
    ))
    # Future booking.
    db_session.add(CounselorSession(
        student_id=students[2].student_id,
        counselor_id=counselor.counselor_id,
        scheduled_at=now + timedelta(days=2),
        status="scheduled",
    ))
    await db_session.flush()

    counselors = (await client.get("/analytics/overview", headers=sa_headers)).json()["counselors"]

    assert counselors["sessions_last_30d"] == 2
    assert counselors["students_seen_last_30d"] == 1
    assert counselors["upcoming_sessions"] == 1


# -------------------------------------------------------------------
# Empty school
# -------------------------------------------------------------------

async def test_empty_school_returns_zeros_not_errors(
    client: AsyncClient, school: Tenant, sa_headers
):
    """A school on day one must render, not 500."""
    resp = await client.get("/analytics/overview", headers=sa_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 0
    assert body["cohort_suppressed"] is True
    assert body["avg_wellness_score"] is None
