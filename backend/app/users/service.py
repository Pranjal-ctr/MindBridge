"""
MindBridge Users Service
Business logic for user profile retrieval and updates.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.users.schemas import UserProfileResponse, UserUpdate
from database.models import User


async def get_user_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfileResponse:
    """Fetch user with their role-specific profile."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.parent_profile),
            selectinload(User.counselor_profile),
            selectinload(User.school_admin_profile),
        )
        .where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _build_profile_response(user)


async def update_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    payload: UserUpdate,
) -> UserProfileResponse:
    """Update basic user fields."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.parent_profile),
            selectinload(User.counselor_profile),
            selectinload(User.school_admin_profile),
        )
        .where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apply updates
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    return _build_profile_response(user)


async def list_tenant_users(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
) -> tuple[list[UserProfileResponse], int]:
    """List users within a tenant with optional role filter."""
    query = (
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.parent_profile),
            selectinload(User.counselor_profile),
            selectinload(User.school_admin_profile),
        )
        .where(User.tenant_id == tenant_id)
    )

    count_query = select(func.count()).select_from(User).where(User.tenant_id == tenant_id)

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    return [_build_profile_response(u) for u in users], total


def _build_profile_response(user: User) -> UserProfileResponse:
    """Build a UserProfileResponse from a User ORM object."""
    from app.users.schemas import (
        CounselorProfileData,
        ParentProfileData,
        SchoolAdminProfileData,
        StudentProfileData,
    )

    response = UserProfileResponse.model_validate(user)

    if user.student_profile:
        response.student_profile = StudentProfileData.model_validate(user.student_profile)
    if user.parent_profile:
        response.parent_profile = ParentProfileData.model_validate(user.parent_profile)
    if user.counselor_profile:
        response.counselor_profile = CounselorProfileData.model_validate(user.counselor_profile)
    if user.school_admin_profile:
        response.school_admin_profile = SchoolAdminProfileData.model_validate(user.school_admin_profile)

    return response
