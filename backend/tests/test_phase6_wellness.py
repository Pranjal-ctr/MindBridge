"""
Phase 6 wellness intelligence: mandatory daily check-in (once per calendar day),
mood calendar, parent trend ranges, cached weekly reports (LLM + fallback),
personalized activities, and data-gated personal insights.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token, hash_password
from database.models import (
    ParentProfile,
    StudentParentLink,
    StudentProfile,
    Tenant,
    User,
    WeeklyReport,
    WellnessRecord,
    WellnessScore,
)

THIS_MONTH = date.today().strftime("%Y-%m")


async def _student_profile(db_session: AsyncSession, user: User) -> StudentProfile:
    return (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.user_id)
    )).scalar_one()


@pytest_asyncio.fixture
async def linked_parent(db_session: AsyncSession, test_tenant: Tenant, test_student_user: User):
    parent_user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"parent_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="parent",
        first_name="Pat", last_name="Parent",
    )
    db_session.add(parent_user)
    await db_session.flush()
    parent_profile = ParentProfile(user_id=parent_user.user_id)
    db_session.add(parent_profile)
    await db_session.flush()

    profile = await _student_profile(db_session, test_student_user)
    db_session.add(StudentParentLink(
        student_id=profile.student_id, parent_id=parent_profile.parent_id,
        relationship_="mother",
    ))
    await db_session.flush()

    token = create_access_token({
        "sub": str(parent_user.user_id),
        "tenant_id": str(parent_user.tenant_id),
        "role": "parent",
    })
    return profile, {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def counselor_auth_headers(db_session: AsyncSession, test_tenant: Tenant):
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"couns_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="counselor",
        first_name="Cass", last_name="Counselor",
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token({
        "sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": "counselor",
    })
    return {"Authorization": f"Bearer {token}"}


CHECKIN = {"mood": "good", "reason": "academics", "reflection": "Did well on the quiz."}


# -------------------------------------------------------------------
# Daily check-in flow
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkin_status_initially_incomplete(client: AsyncClient, student_auth_headers):
    response = await client.get("/wellness/checkin/today", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["completed_today"] is False
    assert data["checkin"] is None
    assert data["updates_remaining"] == 2
    assert data["window_ends_at"] is not None


@pytest.mark.asyncio
async def test_checkin_submit_then_status_complete(client: AsyncClient, student_auth_headers):
    response = await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["checkin"]["mood"] == "good"
    assert data["checkin"]["reason"] == "academics"
    assert data["checkin"]["reflection"] == "Did well on the quiz."
    assert data["updates_remaining"] == 1  # one update still allowed
    # The check-in itself is a signal, so the engine computes a score
    assert data["wellness"]["has_data"] is True

    status = (await client.get("/wellness/checkin/today", headers=student_auth_headers)).json()
    assert status["completed_today"] is True
    assert status["checkin"]["mood"] == "good"
    assert status["updates_remaining"] == 1
    assert status["checkin"]["created_at"] is not None


@pytest.mark.asyncio
async def test_checkin_max_two_per_window(client: AsyncClient, student_auth_headers):
    """Initial check-in + one update per 12-hour window; both stored, latest wins."""
    first = await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)
    assert first.status_code == 201

    # One update is allowed -- the latest mood becomes current
    second = await client.post(
        "/wellness/checkin",
        json={"mood": "low", "reason": "family"},
        headers=student_auth_headers,
    )
    assert second.status_code == 201
    assert second.json()["updates_remaining"] == 0

    status = (await client.get("/wellness/checkin/today", headers=student_auth_headers)).json()
    assert status["checkin"]["mood"] == "low"
    assert status["updates_remaining"] == 0

    # A third submission in the same window is rejected
    third = await client.post(
        "/wellness/checkin",
        json={"mood": "okay", "reason": "other"},
        headers=student_auth_headers,
    )
    assert third.status_code == 409


@pytest.mark.asyncio
async def test_checkin_requires_mood_and_reason(client: AsyncClient, student_auth_headers):
    no_reason = await client.post(
        "/wellness/checkin", json={"mood": "okay"}, headers=student_auth_headers
    )
    assert no_reason.status_code == 422

    bad_mood = await client.post(
        "/wellness/checkin",
        json={"mood": "meh", "reason": "academics"},
        headers=student_auth_headers,
    )
    assert bad_mood.status_code == 422

    bad_reason = await client.post(
        "/wellness/checkin",
        json={"mood": "okay", "reason": "homework"},
        headers=student_auth_headers,
    )
    assert bad_reason.status_code == 422


@pytest.mark.asyncio
async def test_checkin_reflection_is_optional(client: AsyncClient, student_auth_headers):
    response = await client.post(
        "/wellness/checkin",
        json={"mood": "very_difficult", "reason": "social_media"},
        headers=student_auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["checkin"]["reflection"] is None


@pytest.mark.asyncio
async def test_one_tap_mood_still_works_after_official_checkin(
    client: AsyncClient, student_auth_headers
):
    """Sentiment keeps updating during the day without disturbing the official check-in."""
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)

    tap = await client.post("/wellness/mood", json={"mood": "down"}, headers=student_auth_headers)
    assert tap.status_code == 201

    status = (await client.get("/wellness/checkin/today", headers=student_auth_headers)).json()
    assert status["completed_today"] is True
    assert status["checkin"]["mood"] == "good"  # official label preserved


# -------------------------------------------------------------------
# Mood calendar
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mood_calendar_shows_official_checkin(client: AsyncClient, student_auth_headers):
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)

    response = await client.get(
        f"/wellness/mood-calendar?month={THIS_MONTH}", headers=student_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["month"] == THIS_MONTH
    today_entry = next(d for d in data["days"] if d["date"] == date.today().isoformat())
    assert today_entry["mood"] == "good"
    assert today_entry["reason"] == "academics"


@pytest.mark.asyncio
async def test_mood_calendar_rejects_bad_month(client: AsyncClient, student_auth_headers):
    response = await client.get(
        "/wellness/mood-calendar?month=July-2026", headers=student_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_parent_mood_calendar_hides_reason(
    client: AsyncClient, student_auth_headers, linked_parent
):
    profile, parent_headers = linked_parent
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)

    response = await client.get(
        f"/parents/children/{profile.student_id}/mood-calendar?month={THIS_MONTH}",
        headers=parent_headers,
    )
    assert response.status_code == 200
    today_entry = next(
        d for d in response.json()["days"] if d["date"] == date.today().isoformat()
    )
    assert today_entry["mood"] == "good"
    assert today_entry["reason"] is None  # reasons stay private to the student


@pytest.mark.asyncio
async def test_parent_mood_calendar_requires_link(
    client: AsyncClient, db_session, test_tenant, linked_parent
):
    _, parent_headers = linked_parent
    other = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"other_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="student",
        first_name="Other", last_name="Kid",
    )
    db_session.add(other)
    await db_session.flush()
    other_profile = StudentProfile(user_id=other.user_id, age=15)
    db_session.add(other_profile)
    await db_session.flush()

    response = await client.get(
        f"/parents/children/{other_profile.student_id}/mood-calendar?month={THIS_MONTH}",
        headers=parent_headers,
    )
    assert response.status_code == 403


# -------------------------------------------------------------------
# Parent wellness trend ranges
# -------------------------------------------------------------------

async def _seed_scores(db_session: AsyncSession, student_id, days_ago_values: dict[int, float]):
    now = datetime.now(timezone.utc)
    for days_ago, value in days_ago_values.items():
        db_session.add(WellnessScore(
            student_id=student_id, overall_score=value, trend="stable",
            created_at=now - timedelta(days=days_ago),
        ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_parent_trend_respects_range(client: AsyncClient, db_session, linked_parent):
    profile, parent_headers = linked_parent
    await _seed_scores(db_session, profile.student_id, {1: 70, 3: 65, 20: 50, 60: 40})

    week = (await client.get(
        f"/parents/children/{profile.student_id}/wellness-trend?days=7",
        headers=parent_headers,
    )).json()
    month = (await client.get(
        f"/parents/children/{profile.student_id}/wellness-trend?days=30",
        headers=parent_headers,
    )).json()
    quarter = (await client.get(
        f"/parents/children/{profile.student_id}/wellness-trend?days=90",
        headers=parent_headers,
    )).json()

    assert len(week) == 2
    assert len(month) == 3
    assert len(quarter) == 4
    # oldest-first ISO dates with real scores
    assert quarter[0]["score"] == 40.0
    assert quarter[-1]["score"] == 70.0


# -------------------------------------------------------------------
# Weekly reports (student / parent / counselor)
# -------------------------------------------------------------------

WEEKLY_JSON = (
    '{"headline": "A steady, engaged week.", '
    '"summary": "Check-ins were consistent and mood held steady through the week.", '
    '"highlights": ["Checked in five days in a row"], '
    '"focus_areas": ["Keep the morning routine going"]}'
)


@pytest.mark.asyncio
async def test_student_weekly_report_llm_and_cache(
    client: AsyncClient, db_session, student_auth_headers, mock_ai
):
    # Give the student some signals so the LLM path is taken
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)
    mock_ai({"weekly_report": WEEKLY_JSON})

    first = await client.get("/wellness/weekly-report", headers=student_auth_headers)
    assert first.status_code == 200
    data = first.json()
    assert data["audience"] == "student"
    assert data["headline"] == "A steady, engaged week."
    assert data["generated_by"] == "llm"

    # Second call must hit the cache, not the model
    mock_ai({})  # any LLM call would now raise
    second = await client.get("/wellness/weekly-report", headers=student_auth_headers)
    assert second.status_code == 200
    assert second.json()["headline"] == "A steady, engaged week."


@pytest.mark.asyncio
async def test_weekly_report_fallback_without_llm(
    client: AsyncClient, student_auth_headers, mock_ai
):
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)
    mock_ai({})  # LLM unavailable -> deterministic fallback

    response = await client.get("/wellness/weekly-report", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["generated_by"] == "fallback"
    assert data["headline"]
    assert data["summary"]
    assert data["highlights"]


@pytest.mark.asyncio
async def test_weekly_report_role_versions_are_separate(
    client: AsyncClient, db_session, student_auth_headers, linked_parent,
    counselor_auth_headers, mock_ai,
):
    profile, parent_headers = linked_parent
    await client.post("/wellness/checkin", json=CHECKIN, headers=student_auth_headers)
    mock_ai({})  # use deterministic fallback for all three

    student = (await client.get("/wellness/weekly-report", headers=student_auth_headers)).json()
    parent = (await client.get(
        f"/parents/children/{profile.student_id}/weekly-report", headers=parent_headers
    )).json()
    counselor = (await client.get(
        f"/counselors/students/{profile.student_id}/weekly-report",
        headers=counselor_auth_headers,
    )).json()

    assert student["audience"] == "student"
    assert parent["audience"] == "parent"
    assert counselor["audience"] == "counselor"
    # student copy speaks in second person, parent/counselor in third
    assert student["summary"].startswith("You")
    assert parent["summary"].startswith("The student")

    rows = (await db_session.execute(
        select(WeeklyReport).where(WeeklyReport.student_id == profile.student_id)
    )).scalars().all()
    assert {r.audience for r in rows} == {"student", "parent", "counselor"}


@pytest.mark.asyncio
async def test_counselor_weekly_report_404_for_unknown_student(
    client: AsyncClient, counselor_auth_headers
):
    response = await client.get(
        f"/counselors/students/{uuid.uuid4()}/weekly-report",
        headers=counselor_auth_headers,
    )
    assert response.status_code == 404


# -------------------------------------------------------------------
# Personalized activities
# -------------------------------------------------------------------

ACTIVITIES_JSON = (
    '{"activities": ['
    '{"activity_id": "sketch-mood", "title": "Draw how you feel", '
    '"description": "Sketch your mood with shapes and colors.", "category": "creative", '
    '"duration_minutes": 10, "reason": "A gentle outlet for a low day."},'
    '{"activity_id": "walk-10", "title": "10-minute walk", '
    '"description": "Walk around the block without your phone.", "category": "physical", '
    '"duration_minutes": 10, "reason": "Movement lifts mood."},'
    '{"activity_id": "breathe", "title": "Slow breathing", '
    '"description": "Five rounds of 4-7-8 breathing.", "category": "mindfulness", '
    '"duration_minutes": 3, "reason": "Calms exam nerves."},'
    '{"activity_id": "gratitude", "title": "Gratitude note", '
    '"description": "Write three good things about today.", "category": "reflection", '
    '"duration_minutes": 5, "reason": "Builds perspective."},'
    '{"activity_id": "text-friend", "title": "Message a friend", '
    '"description": "Say hi to someone you trust.", "category": "social", '
    '"duration_minutes": 5, "reason": "Connection helps."},'
    '{"activity_id": "early-night", "title": "Early wind-down", '
    '"description": "Screens off 30 minutes before bed.", "category": "rest", '
    '"duration_minutes": 30, "reason": "Better sleep, better days."}]}'
)


@pytest.mark.asyncio
async def test_activities_personalized_by_llm(
    client: AsyncClient, student_auth_headers, mock_ai
):
    mock_ai({"activities": ACTIVITIES_JSON})
    response = await client.get("/wellness/activities", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["personalized"] is True
    # 6 weekly (from the LLM) + 1 deterministic daily pick
    assert len(data["activities"]) == 7
    titles = [a["title"] for a in data["activities"]]
    assert "Draw how you feel" in titles
    dailies = [a for a in data["activities"] if a["is_daily"]]
    assert len(dailies) == 1


@pytest.mark.asyncio
async def test_activities_persist_and_do_not_regenerate(
    client: AsyncClient, student_auth_headers, mock_ai
):
    """The weekly set is generated once and then served from the database."""
    mock_ai({"activities": ACTIVITIES_JSON})
    first = (await client.get("/wellness/activities", headers=student_auth_headers)).json()

    mock_ai({})  # any further LLM call would raise
    second = (await client.get("/wellness/activities", headers=student_auth_headers)).json()

    assert [a["activity_id"] for a in first["activities"]] == \
           [a["activity_id"] for a in second["activities"]]
    assert second["personalized"] is True  # source remembered from the stored set


@pytest.mark.asyncio
async def test_activities_fallback_uses_signals(
    client: AsyncClient, student_auth_headers, mock_ai
):
    # Low-mood check-in first; LLM unavailable
    await client.post(
        "/wellness/checkin", json={"mood": "low", "reason": "academics"},
        headers=student_auth_headers,
    )
    mock_ai({})

    response = await client.get("/wellness/activities", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["personalized"] is False
    assert len(data["activities"]) == 7  # 6 weekly + daily pick
    valid = {"mindfulness", "physical", "social", "reflection", "rest", "creative"}
    assert {a["category"] for a in data["activities"]} <= valid
    # every suggestion explains itself, and nothing repeats within the set
    assert all(a["reason"] for a in data["activities"])
    ids = [a["activity_id"] for a in data["activities"]]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_activity_completion_persists_and_blocks_double(
    client: AsyncClient, student_auth_headers, mock_ai
):
    mock_ai({})
    activities = (await client.get(
        "/wellness/activities", headers=student_auth_headers
    )).json()["activities"]
    target = activities[0]
    assert target["completed"] is False

    done = await client.post(
        "/wellness/activities/complete",
        json={"activity_id": target["activity_id"], "title": target["title"]},
        headers=student_auth_headers,
    )
    assert done.status_code == 201

    # Completion state survives a re-fetch (i.e. persists across sessions)
    refreshed = (await client.get(
        "/wellness/activities", headers=student_auth_headers
    )).json()["activities"]
    match = next(a for a in refreshed if a["activity_id"] == target["activity_id"])
    assert match["completed"] is True

    # Cannot complete the same activity twice
    again = await client.post(
        "/wellness/activities/complete",
        json={"activity_id": target["activity_id"], "title": target["title"]},
        headers=student_auth_headers,
    )
    assert again.status_code == 409


# -------------------------------------------------------------------
# Personal insights (data-sufficiency gating)
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_personal_insights_gated_without_history(
    client: AsyncClient, student_auth_headers
):
    response = await client.get("/wellness/insights", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sufficient_data"] is False
    assert data["insights"] == []


@pytest.mark.asyncio
async def test_personal_insights_surface_patterns(
    client: AsyncClient, db_session, test_student_user, student_auth_headers
):
    profile = await _student_profile(db_session, test_student_user)
    today = date.today()

    # 28 days of history: Mondays are rough (academics), Fridays are great (sports)
    for days_ago in range(1, 29):
        day = today - timedelta(days=days_ago)
        if day.weekday() == 0:
            mood, label, reason = 3, "low", "academics"
        elif day.weekday() == 4:
            mood, label, reason = 9, "amazing", "sports"
        else:
            mood, label, reason = 6, "okay", "friends"
        db_session.add(WellnessRecord(
            student_id=profile.student_id, mood_score=mood,
            mood_label=label, mood_reason=reason, date_recorded=day,
        ))
    await db_session.flush()

    response = await client.get("/wellness/insights", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sufficient_data"] is True
    assert data["checkin_days"] >= 28
    kinds = {i["kind"] for i in data["insights"]}
    assert "weekday_pattern" in kinds
    assert "reason_pattern" in kinds
    # every insight cites its evidence
    assert all(i["evidence"] for i in data["insights"])
