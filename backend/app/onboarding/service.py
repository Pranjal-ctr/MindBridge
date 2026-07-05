"""
MindBridge Onboarding Service
Store and fetch the student first-login questionnaire.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.onboarding.schemas import OnboardingResponse, OnboardingSubmit
from database.models import StudentOnboarding


async def get_onboarding(db: AsyncSession, student_id: uuid.UUID) -> OnboardingResponse | None:
    """Return the student's onboarding responses, or None if not completed yet."""
    result = await db.execute(
        select(StudentOnboarding).where(StudentOnboarding.student_id == student_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return OnboardingResponse.model_validate(row)


async def submit_onboarding(
    db: AsyncSession, student_id: uuid.UUID, payload: OnboardingSubmit
) -> OnboardingResponse:
    """Create or replace the student's onboarding responses (idempotent upsert)."""
    result = await db.execute(
        select(StudentOnboarding).where(StudentOnboarding.student_id == student_id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = StudentOnboarding(student_id=student_id)
        db.add(row)

    row.class_level = payload.class_level
    row.help_goals = payload.help_goals
    row.hobbies = payload.hobbies
    row.strengths = payload.strengths
    row.interaction_style = payload.interaction_style

    await db.flush()
    await db.refresh(row)
    return OnboardingResponse.model_validate(row)
