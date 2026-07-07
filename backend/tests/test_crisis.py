"""
Crisis workflow: threshold trigger -> queue + timeline + audit + notifications,
notification suppression, parent gating, below-threshold no-op.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.analysis import run_message_analysis
from app.intelligence.crisis import evaluate_and_trigger_crisis
from database.models import (
    AuditLog,
    Conversation,
    Message,
    Notification,
    ParentProfile,
    RiskAssessment,
    SchoolSettings,
    StudentParentLink,
    StudentProfile,
    StudentTimeline,
    Tenant,
    User,
)
from tests.conftest import hash_password
from tests.test_intelligence_analysis import analysis_json


@pytest_asyncio.fixture
async def crisis_setup(db_session: AsyncSession, test_tenant: Tenant, test_student_user: User):
    """Student + conversation + counselor + linked parent in one tenant."""
    profile = (await db_session.execute(
        select(StudentProfile).where(StudentProfile.user_id == test_student_user.user_id)
    )).scalar_one()

    conversation = Conversation(student_id=profile.student_id, title="Chat")
    db_session.add(conversation)
    await db_session.flush()
    message = Message(
        conversation_id=conversation.conversation_id,
        sender_type="user",
        sender_id=test_student_user.user_id,
        message_text="things feel hopeless",
    )
    db_session.add(message)

    counselor = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"coun_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="counselor",
        first_name="Cora", last_name="Counselor",
    )
    parent_user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"parent_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"), role="parent",
        first_name="Pat", last_name="Parent",
    )
    db_session.add_all([counselor, parent_user])
    await db_session.flush()

    parent_profile = ParentProfile(user_id=parent_user.user_id)
    db_session.add(parent_profile)
    await db_session.flush()
    db_session.add(StudentParentLink(
        student_id=profile.student_id, parent_id=parent_profile.parent_id,
        relationship_="mother",
    ))
    await db_session.flush()

    return profile, conversation, message, counselor, parent_user


async def _high_risk_outcome(db_session, profile, conversation, message, mock_ai, overall=88):
    mock_ai({"risk_detection": analysis_json(overall=overall, emotion="Hopeless")})
    return await run_message_analysis(
        db_session,
        conversation_id=conversation.conversation_id,
        student_id=profile.student_id,
        student_message_id=message.message_id,
    )


@pytest.mark.asyncio
async def test_crisis_triggers_full_workflow(db_session, crisis_setup, mock_ai, test_student_user):
    profile, conversation, message, counselor, parent_user = crisis_setup
    outcome = await _high_risk_outcome(db_session, profile, conversation, message, mock_ai)

    triggered = await evaluate_and_trigger_crisis(
        db_session, profile.student_id, test_student_user.user_id, outcome
    )
    assert triggered is True

    # Queued for review
    assert outcome.assessment.review_status == "pending"

    # Timeline event
    timeline = (await db_session.execute(
        select(StudentTimeline).where(
            StudentTimeline.student_id == profile.student_id,
            StudentTimeline.event_type == "risk_alert",
        )
    )).scalar_one()
    assert "counselor review" in timeline.event_description

    # Audit log
    audit = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "crisis_workflow_triggered")
    )).scalars().all()
    assert len(audit) == 1

    # Counselor notified; parent notified content-free
    counselor_note = (await db_session.execute(
        select(Notification).where(Notification.user_id == counselor.user_id)
    )).scalar_one()
    assert "review required" in counselor_note.message

    parent_note = (await db_session.execute(
        select(Notification).where(Notification.user_id == parent_user.user_id)
    )).scalar_one()
    assert "risk level has changed" in parent_note.message
    assert "hopeless" not in parent_note.message.lower()
    assert "self_harm" not in parent_note.message


@pytest.mark.asyncio
async def test_below_threshold_does_not_trigger(db_session, crisis_setup, mock_ai,
                                                test_student_user):
    profile, conversation, message, counselor, _parent = crisis_setup
    outcome = await _high_risk_outcome(db_session, profile, conversation, message, mock_ai,
                                       overall=30)

    triggered = await evaluate_and_trigger_crisis(
        db_session, profile.student_id, test_student_user.user_id, outcome
    )
    assert triggered is False
    assert outcome.assessment.review_status is None
    notifications = (await db_session.execute(
        select(Notification).where(Notification.user_id == counselor.user_id)
    )).scalars().all()
    assert notifications == []


@pytest.mark.asyncio
async def test_repeat_crisis_suppresses_notifications(db_session, crisis_setup, mock_ai,
                                                      test_student_user):
    profile, conversation, message, counselor, _parent = crisis_setup

    first = await _high_risk_outcome(db_session, profile, conversation, message, mock_ai)
    await evaluate_and_trigger_crisis(
        db_session, profile.student_id, test_student_user.user_id, first
    )
    second = await _high_risk_outcome(db_session, profile, conversation, message, mock_ai)
    await evaluate_and_trigger_crisis(
        db_session, profile.student_id, test_student_user.user_id, second
    )

    # Both queued, but only one notification wave
    pending = (await db_session.execute(
        select(RiskAssessment).where(
            RiskAssessment.student_id == profile.student_id,
            RiskAssessment.review_status == "pending",
        )
    )).scalars().all()
    assert len(pending) == 2

    notifications = (await db_session.execute(
        select(Notification).where(Notification.user_id == counselor.user_id)
    )).scalars().all()
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_parent_notification_respects_school_setting(
    db_session, crisis_setup, mock_ai, test_tenant, test_student_user
):
    profile, conversation, message, counselor, parent_user = crisis_setup
    db_session.add(SchoolSettings(
        tenant_id=test_tenant.tenant_id, allow_parent_notifications=False
    ))
    await db_session.flush()

    outcome = await _high_risk_outcome(db_session, profile, conversation, message, mock_ai)
    await evaluate_and_trigger_crisis(
        db_session, profile.student_id, test_student_user.user_id, outcome
    )

    parent_notes = (await db_session.execute(
        select(Notification).where(Notification.user_id == parent_user.user_id)
    )).scalars().all()
    assert parent_notes == []
    # Counselors still alerted
    counselor_notes = (await db_session.execute(
        select(Notification).where(Notification.user_id == counselor.user_id)
    )).scalars().all()
    assert len(counselor_notes) == 1
