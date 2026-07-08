"""
Parent insights v2: live wellness/risk/mood/stress data, debounced AI
narrative regeneration, and the privacy guarantee that no student message
content ever reaches the parent-facing response or the model input.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token, hash_password
from app.intelligence.insights import _build_signal_summary, maybe_refresh_parent_insight
from database.models import (
    Conversation,
    EmotionSnapshot,
    Message,
    ParentInsightHistory,
    ParentProfile,
    RiskAssessment,
    StressDistribution,
    StudentParentLink,
    StudentProfile,
    Tenant,
    User,
    WellnessScore,
)

SECRET_MESSAGE = "I have been cutting myself with a razor blade every night"


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

    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
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


def insight_json():
    return (
        '{"summary": "Sarah has discussed exam pressure this week but remains engaged.", '
        '"recommendations": ["Ask about her exam schedule", "Plan a low-key weekend activity"], '
        '"today_insights": [{"type": "caution", "title": "Elevated stress", '
        '"body": "Academic pressure has been a recurring theme."}], '
        '"improvements": ["More consistent check-ins"], "concerns": ["Exam stress"]}'
    )


@pytest.mark.asyncio
async def test_no_signals_skips_generation(db_session: AsyncSession, test_student_user, mock_ai):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    mock_ai({"parent_insight": insight_json()})

    result = await maybe_refresh_parent_insight(db_session, profile.student_id, force=True)
    assert result is None  # no wellness/risk/emotion data at all


@pytest.mark.asyncio
async def test_generates_when_forced_with_data(db_session: AsyncSession, test_student_user, mock_ai):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=65, trend="stable", components={},
    ))
    await db_session.flush()
    mock_ai({"parent_insight": insight_json()})

    insight = await maybe_refresh_parent_insight(db_session, profile.student_id, force=True)
    assert insight is not None
    assert "exam pressure" in insight.summary
    assert insight.recommendations.count("|") == 1
    assert insight.insights_json["today_insights"][0]["type"] == "caution"
    assert insight.insights_json["concerns"] == ["Exam stress"]


@pytest.mark.asyncio
async def test_not_forced_and_fresh_skips_regen(db_session: AsyncSession, test_student_user, mock_ai):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=65, trend="stable", components={},
    ))
    db_session.add(ParentInsightHistory(
        student_id=profile.student_id, risk_level="green",
        summary="Existing summary.", recommendations="A|B",
        generated_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()
    mock_ai({"parent_insight": insight_json()})  # would raise if called unexpectedly

    result = await maybe_refresh_parent_insight(db_session, profile.student_id, force=False)
    assert result is None


@pytest.mark.asyncio
async def test_stale_and_active_triggers_regen(db_session: AsyncSession, test_student_user, mock_ai):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    old = datetime.now(timezone.utc) - timedelta(hours=10)
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=65, trend="stable", components={},
    ))
    db_session.add(ParentInsightHistory(
        student_id=profile.student_id, risk_level="green",
        summary="Old.", recommendations="A", generated_at=old,
    ))
    await db_session.flush()

    conversation = Conversation(student_id=profile.student_id, title="Chat")
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(Message(
        conversation_id=conversation.conversation_id, sender_type="user",
        sender_id=test_student_user.user_id, message_text="hi",
        created_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()
    mock_ai({"parent_insight": insight_json()})

    result = await maybe_refresh_parent_insight(db_session, profile.student_id, force=False)
    assert result is not None


@pytest.mark.asyncio
async def test_risk_level_change_forces_regen(db_session: AsyncSession, test_student_user, mock_ai):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    profile.risk_level = "red"
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=40, trend="declining", components={},
    ))
    db_session.add(ParentInsightHistory(
        student_id=profile.student_id, risk_level="green",  # stale relative to profile
        summary="Old.", recommendations="A", generated_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()
    mock_ai({"parent_insight": insight_json()})

    result = await maybe_refresh_parent_insight(db_session, profile.student_id, force=False)
    assert result is not None


# -------------------------------------------------------------------
# Privacy: no student message content ever reaches the model input or
# the parent-facing API response.
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signal_summary_never_contains_message_text(db_session, test_student_user):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    conversation = Conversation(student_id=profile.student_id, title="Chat")
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(Message(
        conversation_id=conversation.conversation_id, sender_type="user",
        sender_id=test_student_user.user_id, message_text=SECRET_MESSAGE,
    ))
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=30, trend="declining", components={},
    ))
    db_session.add(RiskAssessment(
        student_id=profile.student_id, risk_level="red", risk_score=80,
        summary="Student shows signs of self-harm behavior.", generated_by="ai_pipeline",
    ))
    await db_session.flush()

    summary = await _build_signal_summary(db_session, profile.student_id)
    assert summary is not None
    assert SECRET_MESSAGE not in summary
    assert "razor" not in summary.lower()


@pytest.mark.asyncio
async def test_insights_endpoint_never_leaks_message_content(
    client: AsyncClient, linked_parent, db_session, test_student_user, mock_ai
):
    profile, parent_headers = linked_parent
    conversation = Conversation(student_id=profile.student_id, title="Chat")
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(Message(
        conversation_id=conversation.conversation_id, sender_type="user",
        sender_id=test_student_user.user_id, message_text=SECRET_MESSAGE,
    ))
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=55, trend="stable",
        components={"mood_level": {"normalized": 60, "weight": 0.15, "contribution": 9, "detail": "ok"}},
        explanation="Wellness is 55 and stable.",
    ))
    await db_session.flush()

    resp = await client.get(
        f"/parents/children/{profile.student_id}/insights", headers=parent_headers
    )
    assert resp.status_code == 200
    assert SECRET_MESSAGE not in resp.text
    assert "razor" not in resp.text.lower()


@pytest.mark.asyncio
async def test_insights_endpoint_returns_live_breakdown(
    client: AsyncClient, linked_parent, db_session
):
    profile, parent_headers = linked_parent
    db_session.add(WellnessScore(
        student_id=profile.student_id, overall_score=72, trend="improving",
        confidence=0.8,
        components={"mood_level": {"normalized": 80, "weight": 0.15, "contribution": 12, "detail": "good"}},
        explanation="Wellness is 72 and improving.",
    ))
    db_session.add(StressDistribution(
        student_id=profile.student_id,
        categories={"Academic": 60, "Family": 20, "Friends": 0, "Relationships": 0,
                   "Health": 0, "Career": 0, "Future": 0, "Identity": 0,
                   "Financial": 0, "Self-Confidence": 0},
    ))
    db_session.add(EmotionSnapshot(
        student_id=profile.student_id, current_emotion="Anxious", intensity=50, confidence=0.8,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/parents/children/{profile.student_id}/insights", headers=parent_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["wellness_score"] == 72
    assert body["wellness_breakdown"]["trend"] == "improving"
    assert body["stress_factors"][0]["name"] == "Academic"
    assert body["emotional_state"] == "Anxious"
    assert "weekly_progress" in body


@pytest.mark.asyncio
async def test_unlinked_parent_forbidden(client: AsyncClient, db_session, test_student_user,
                                         test_tenant):
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()
    stranger = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"stranger_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="parent",
        first_name="No", last_name="Link",
    )
    db_session.add(stranger)
    await db_session.flush()
    db_session.add(ParentProfile(user_id=stranger.user_id))
    await db_session.flush()
    token = create_access_token({
        "sub": str(stranger.user_id), "tenant_id": str(test_tenant.tenant_id), "role": "parent",
    })

    resp = await client.get(
        f"/parents/children/{profile.student_id}/insights",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
