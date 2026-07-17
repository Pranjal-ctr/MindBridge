"""
Kio Users Router
User profile management endpoints.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, CurrentTenant, require_role
from app.users.schemas import UserListResponse, UserProfileResponse, UserUpdate
from app.users.service import get_user_profile, list_tenant_users, update_user_profile
from database.session import get_db

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the authenticated user's full profile with role-specific data."""
    return await get_user_profile(db, current_user.user_id)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update the authenticated user's profile."""
    return await update_user_profile(db, current_user.user_id, payload)


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_role("admin", "school_admin", "counselor"))],
)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get a specific user's profile.
    Restricted to admins, school admins, and counselors.
    """
    return await get_user_profile(db, user_id)


@router.get(
    "/",
    response_model=UserListResponse,
    dependencies=[Depends(require_role("admin", "school_admin"))],
)
async def list_users(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = Query(None, pattern=r"^(student|parent|counselor|school_admin|admin)$"),
):
    """
    List users within the current tenant.
    Restricted to admins and school admins.
    """
    users, total = await list_tenant_users(db, tenant_id, page, page_size, role)
    return UserListResponse(users=users, total=total, page=page, page_size=page_size)
