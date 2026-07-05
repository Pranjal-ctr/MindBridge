"""
MindBridge Onboarding Router
Student first-login questionnaire endpoints.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import get_student_id_for_user
from app.dependencies import CurrentUser, require_role
from app.onboarding.schemas import OnboardingResponse, OnboardingSubmit
from app.onboarding.service import get_onboarding, submit_onboarding
from database.session import get_db

router = APIRouter()


@router.get(
    "/",
    response_model=OnboardingResponse | None,
    dependencies=[Depends(require_role("student"))],
)
async def read_onboarding(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the current student's onboarding responses, or null if not completed."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_onboarding(db, student_id)


@router.post(
    "/",
    response_model=OnboardingResponse,
    status_code=201,
    dependencies=[Depends(require_role("student"))],
)
async def create_onboarding(
    payload: OnboardingSubmit,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit the first-login questionnaire (idempotent)."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await submit_onboarding(db, student_id, payload)
