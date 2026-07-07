"""
Deterministic wellness engine: component math, renormalization, trend,
explanation, and the /wellness/score, /wellness/mood, /wellness/emotions APIs.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.wellness import compute_wellness_score
from database.models import (
    EmotionSnapshot,
    StudentProfile,
    StudentTimeline,
    User,
    WellnessRecord,
    WellnessScore,
)


@pytest_asyncio.fixture
async def student_profile(db_session: AsyncSession, test_student_user: User) -> StudentProfile:
    result = await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )
    return result.scalar_one()


def _record(student_id, days_ago=0, mood=7, stress=4, anxiety=3, energy=7, confidence=6):
    return WellnessRecord(
        student_id=student_id,
        mood_score=mood,
        stress_score=stress,
        anxiety_score=anxiety,
        energy_score=energy,
        confidence_score=confidence,
        date_recorded=date.today() - timedelta(days=days_ago),
    )


@pytest.mark.asyncio
async def test_score_computed_from_checkins(db_session, student_profile):
    for days_ago in range(3):
        db_session.add(_record(student_profile.student_id, days_ago))
    await db_session.flush()

    score = await compute_wellness_score(db_session, student_profile.student_id, "checkin")

    assert score is not None
    assert 0 <= float(score.overall_score) <= 100
    assert score.trigger_source == "checkin"
    # Components with data are present, others dropped
    assert "mood_level" in score.components
    assert "stress_trend" in score.components
    assert "conversation_sentiment" not in score.components
    # Confidence = share of weights with data (partial here)
    assert 0 < float(score.confidence) < 1
    # Profile synced for backward compat
    assert float(student_profile.wellness_score) == float(score.overall_score)
    # Explanation is templated from actual components
    assert "Wellness is" in score.explanation


@pytest.mark.asyncio
async def test_missing_components_renormalized(db_session, student_profile):
    # Only mood-bearing data: overall must equal the weighted average of the
    # present components alone (renormalized), not be dragged down by absent ones.
    db_session.add(_record(student_profile.student_id, mood=10, stress=1, anxiety=1,
                           energy=10, confidence=10))
    await db_session.flush()

    score = await compute_wellness_score(db_session, student_profile.student_id, "checkin")

    assert score is not None
    weights = {name: c["weight"] for name, c in score.components.items()}
    normalized = {name: c["normalized"] for name, c in score.components.items()}
    expected = sum(normalized[n] * weights[n] for n in weights) / sum(weights.values())
    assert abs(float(score.overall_score) - expected) < 0.1


@pytest.mark.asyncio
async def test_no_data_returns_none(db_session, student_profile):
    score = await compute_wellness_score(db_session, student_profile.student_id, "manual")
    assert score is None
    rows = (await db_session.execute(
        select(WellnessScore).where(WellnessScore.student_id == student_profile.student_id)
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_trend_improving_vs_week_ago(db_session, student_profile):
    db_session.add(WellnessScore(
        student_id=student_profile.student_id,
        overall_score=40,
        trend="stable",
        components={},
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    ))
    for days_ago in range(3):
        db_session.add(_record(student_profile.student_id, days_ago, mood=9, stress=2,
                               anxiety=2, energy=9, confidence=8))
    await db_session.flush()

    score = await compute_wellness_score(db_session, student_profile.student_id, "checkin")
    assert score is not None
    assert float(score.overall_score) > 43
    assert score.trend == "improving"
    # Momentum component appears once history exists
    assert "improvement_delta" in score.components


# -------------------------------------------------------------------
# API endpoints
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_endpoint_empty_state(client: AsyncClient, student_auth_headers):
    resp = await client.get("/wellness/score", headers=student_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is False
    assert body["streak_days"] == 0


@pytest.mark.asyncio
async def test_mood_checkin_persists_and_scores(
    client: AsyncClient, student_auth_headers, db_session, student_profile
):
    resp = await client.post(
        "/wellness/mood", headers=student_auth_headers, json={"mood": "happy"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["record"]["mood_score"] == 8
    assert body["wellness"]["has_data"] is True
    assert body["wellness"]["streak_days"] == 1

    # Second tap the same day updates, not duplicates
    resp2 = await client.post(
        "/wellness/mood", headers=student_auth_headers, json={"mood": "down"}
    )
    assert resp2.json()["record"]["record_id"] == body["record"]["record_id"]
    assert resp2.json()["record"]["mood_score"] == 2

    records = (await db_session.execute(
        select(WellnessRecord).where(WellnessRecord.student_id == student_profile.student_id)
    )).scalars().all()
    assert len(records) == 1

    timeline = (await db_session.execute(
        select(StudentTimeline).where(
            StudentTimeline.student_id == student_profile.student_id,
            StudentTimeline.event_type == "mood_log",
        )
    )).scalars().all()
    assert len(timeline) == 2


@pytest.mark.asyncio
async def test_checkin_triggers_recalc(client: AsyncClient, student_auth_headers, db_session,
                                        student_profile):
    resp = await client.post("/wellness/records", headers=student_auth_headers, json={
        "mood_score": 7, "stress_score": 4, "confidence_score": 6,
        "anxiety_score": 3, "energy_score": 7,
    })
    assert resp.status_code == 201

    score = (await db_session.execute(
        select(WellnessScore).where(WellnessScore.student_id == student_profile.student_id)
    )).scalar_one()
    assert score.trigger_source == "checkin"


@pytest.mark.asyncio
async def test_score_history_endpoint(client: AsyncClient, student_auth_headers, db_session,
                                       student_profile):
    for i, value in enumerate([50, 60, 70]):
        db_session.add(WellnessScore(
            student_id=student_profile.student_id,
            overall_score=value,
            trend="improving",
            components={},
            created_at=datetime.now(timezone.utc) - timedelta(days=3 - i),
        ))
    await db_session.flush()

    resp = await client.get("/wellness/score/history?days=30", headers=student_auth_headers)
    assert resp.status_code == 200
    points = resp.json()["points"]
    assert [p["score"] for p in points] == [50, 60, 70]  # oldest first


@pytest.mark.asyncio
async def test_emotion_summary(client: AsyncClient, student_auth_headers, db_session,
                               student_profile):
    now = datetime.now(timezone.utc)
    for i, emotion in enumerate(["Anxious", "Anxious", "Sad", "Anxious"]):
        db_session.add(EmotionSnapshot(
            student_id=student_profile.student_id,
            current_emotion=emotion,
            intensity=60,
            confidence=0.9,
            secondary_emotions=[],
            created_at=now - timedelta(days=i),
        ))
    await db_session.flush()

    resp = await client.get("/wellness/emotions", headers=student_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is True
    assert body["current_emotion"] == "Anxious"
    assert body["dominant_emotion"] == "Anxious"
    assert body["stability"] == 0.75
    assert len(body["timeline"]) == 4
    assert len(body["weekly_trend"]) >= 1


@pytest.mark.asyncio
async def test_emotion_summary_empty(client: AsyncClient, student_auth_headers):
    resp = await client.get("/wellness/emotions", headers=student_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["has_data"] is False
