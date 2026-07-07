"""
Combined post-message analysis: persistence of all four sinks, server-side
level derivation, de-escalation policy, stress smoothing, keyword tripwire.
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.safety import _raise_keyword_tripwire, detect_safety_events
from app.intelligence.analysis import run_message_analysis
from app.intelligence.schemas import STRESS_CATEGORIES
from database.models import (
    Conversation,
    EmotionSnapshot,
    Message,
    Notification,
    RiskAssessment,
    StressDistribution,
    StudentProfile,
    Tenant,
    User,
)
from tests.conftest import hash_password


def analysis_json(overall=81, emotion="Anxious", sentiment="negative", stress=None) -> str:
    return json.dumps({
        "risk": {
            "overall": overall,
            "confidence": 0.94,
            "categories": {"self_harm": 20, "family_conflict": 78, "academic_pressure": 62},
            "summary": "Student shows persistent stress linked to family pressure.",
        },
        "emotion": {"current": emotion, "intensity": 70, "confidence": 0.9, "secondary": ["Sad"]},
        "sentiment": sentiment,
        "stress": stress or {"Academic": 62, "Family": 78},
    })


@pytest_asyncio.fixture
async def student_conversation(db_session: AsyncSession, test_student_user: User):
    """A conversation with one student message, plus the student profile."""
    result = await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )
    profile = result.scalar_one()

    conversation = Conversation(student_id=profile.student_id, title="Test chat")
    db_session.add(conversation)
    await db_session.flush()

    message = Message(
        conversation_id=conversation.conversation_id,
        sender_type="user",
        sender_id=test_student_user.user_id,
        message_text="I'm really stressed about exams and my parents keep fighting.",
    )
    db_session.add(message)
    await db_session.flush()

    return profile, conversation, message


@pytest.mark.asyncio
async def test_analysis_persists_all_sinks(
    db_session: AsyncSession, student_conversation, mock_ai
):
    profile, conversation, message = student_conversation
    mock_ai({"risk_detection": analysis_json()})

    outcome = await run_message_analysis(
        db_session,
        conversation_id=conversation.conversation_id,
        student_id=profile.student_id,
        student_message_id=message.message_id,
    )

    # Risk assessment (level derived server-side: 81 is in the red band)
    assessment = outcome.assessment
    assert float(assessment.risk_score) == 81
    assert assessment.risk_level == "red"
    assert assessment.categories["family_conflict"] == 78
    assert float(assessment.confidence) == 0.94
    assert assessment.generated_by == "ai_pipeline"
    assert assessment.message_id == message.message_id

    # Profile escalated immediately
    assert profile.risk_level == "red"
    assert outcome.previous_profile_level == "green"
    assert outcome.new_profile_level == "red"

    # Emotion snapshot
    emotion = (await db_session.execute(
        select(EmotionSnapshot).where(EmotionSnapshot.student_id == profile.student_id)
    )).scalar_one()
    assert emotion.current_emotion == "Anxious"
    assert emotion.secondary_emotions == ["Sad"]

    # Stress distribution: all 10 categories present, smoothed from zero baseline
    stress = (await db_session.execute(
        select(StressDistribution).where(StressDistribution.student_id == profile.student_id)
    )).scalar_one()
    assert set(stress.categories) == set(STRESS_CATEGORIES)
    assert stress.categories["Family"] == round(0.6 * 78)
    assert stress.categories["Health"] == 0

    # Sentiment written onto the student message
    await db_session.refresh(message)
    assert message.sentiment == "negative"


@pytest.mark.asyncio
async def test_analysis_critical_band(db_session, student_conversation, mock_ai):
    profile, conversation, message = student_conversation
    mock_ai({"risk_detection": analysis_json(overall=90)})

    outcome = await run_message_analysis(
        db_session,
        conversation_id=conversation.conversation_id,
        student_id=profile.student_id,
        student_message_id=message.message_id,
    )
    assert outcome.assessment.risk_level == "critical"


@pytest.mark.asyncio
async def test_analysis_garbage_response_raises(db_session, student_conversation, mock_ai):
    profile, conversation, message = student_conversation
    mock_ai({"risk_detection": "sorry, I cannot help with that"})

    with pytest.raises(ValueError):
        await run_message_analysis(
            db_session,
            conversation_id=conversation.conversation_id,
            student_id=profile.student_id,
            student_message_id=message.message_id,
        )

    # Nothing persisted
    rows = (await db_session.execute(
        select(RiskAssessment).where(RiskAssessment.student_id == profile.student_id)
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_deescalation_requires_consecutive_lows(
    db_session, student_conversation, mock_ai
):
    profile, conversation, message = student_conversation
    profile.risk_level = "red"
    await db_session.flush()

    mock_ai({"risk_detection": analysis_json(overall=10, emotion="Calm", sentiment="positive")})

    # First two low assessments: profile must stay red (deescalate_after=3)
    for _ in range(2):
        await run_message_analysis(
            db_session,
            conversation_id=conversation.conversation_id,
            student_id=profile.student_id,
            student_message_id=message.message_id,
        )
        assert profile.risk_level == "red"

    # Third consecutive low reading de-escalates
    outcome = await run_message_analysis(
        db_session,
        conversation_id=conversation.conversation_id,
        student_id=profile.student_id,
        student_message_id=message.message_id,
    )
    assert profile.risk_level == "green"
    assert outcome.previous_profile_level == "red"
    assert outcome.new_profile_level == "green"


@pytest.mark.asyncio
async def test_stress_smoothing_uses_previous_row(db_session, student_conversation, mock_ai):
    profile, conversation, message = student_conversation
    db_session.add(StressDistribution(
        student_id=profile.student_id,
        categories={c: (100 if c == "Academic" else 0) for c in STRESS_CATEGORIES},
    ))
    await db_session.flush()

    mock_ai({"risk_detection": analysis_json(stress={"Academic": 0, "Family": 50})})
    await run_message_analysis(
        db_session,
        conversation_id=conversation.conversation_id,
        student_id=profile.student_id,
        student_message_id=message.message_id,
    )

    latest = (await db_session.execute(
        select(StressDistribution)
        .where(StressDistribution.student_id == profile.student_id)
        .order_by(StressDistribution.created_at.desc())
        .limit(1)
    )).scalar_one()
    # new = 0.6*analysis + 0.4*previous
    assert latest.categories["Academic"] == round(0.6 * 0 + 0.4 * 100)
    assert latest.categories["Family"] == round(0.6 * 50)


# -------------------------------------------------------------------
# Keyword tripwire
# -------------------------------------------------------------------

def test_detect_safety_events_matches_categories():
    assert detect_safety_events("sometimes I want to die") == ["self_harm"]
    assert detect_safety_events("my stepdad hits me") == ["abuse"]
    assert detect_safety_events("the weather is nice today") == []


@pytest.mark.asyncio
async def test_tripwire_creates_pending_assessment_and_notifies(
    db_session: AsyncSession, test_student_user: User, test_tenant: Tenant, student_conversation
):
    profile, conversation, _message = student_conversation

    counselor = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"counselor_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="counselor",
        first_name="Coun",
        last_name="Selor",
    )
    db_session.add(counselor)
    await db_session.flush()

    await _raise_keyword_tripwire(
        db_session, conversation.conversation_id, test_student_user.user_id, {"self_harm"}
    )

    assessment = (await db_session.execute(
        select(RiskAssessment).where(
            RiskAssessment.student_id == profile.student_id,
            RiskAssessment.generated_by == "keyword_tripwire",
        )
    )).scalar_one()
    assert assessment.review_status == "pending"
    assert assessment.risk_level == "red"  # crisis.tripwire_level default
    assert "self_harm" in assessment.trigger_reason

    # Profile escalated, counselor notified (content-free)
    assert profile.risk_level == "red"
    notification = (await db_session.execute(
        select(Notification).where(Notification.user_id == counselor.user_id)
    )).scalar_one()
    assert "review required" in notification.message
    assert "want to die" not in notification.message


@pytest.mark.asyncio
async def test_tripwire_dedupes_within_window(
    db_session: AsyncSession, test_student_user: User, student_conversation
):
    profile, conversation, _message = student_conversation

    await _raise_keyword_tripwire(
        db_session, conversation.conversation_id, test_student_user.user_id, {"self_harm"}
    )
    await _raise_keyword_tripwire(
        db_session, conversation.conversation_id, test_student_user.user_id, {"self_harm"}
    )

    rows = (await db_session.execute(
        select(RiskAssessment).where(
            RiskAssessment.conversation_id == conversation.conversation_id,
            RiskAssessment.generated_by == "keyword_tripwire",
        )
    )).scalars().all()
    assert len(rows) == 1
