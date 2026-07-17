"""
Kio Linking Router
Endpoints for parent-student invite code system.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, require_role
from app.linking.schemas import (
    GuardianCreate,
    GuardianListResponse,
    GuardianResponse,
    GuardianUpdate,
    InviteCodeCreateResponse,
    InviteCodeResponse,
    LinkedChildrenListResponse,
    LinkedParentsListResponse,
    RedeemInviteRequest,
    RedeemInviteResponse,
)
from app.linking.service import (
    create_guardian,
    delete_guardian,
    generate_guardian_invite_code,
    generate_invite_code,
    get_active_invite_code,
    get_linked_children,
    get_linked_parents,
    list_guardians,
    redeem_invite_code,
    revoke_parent_link,
    update_guardian,
)
from database.session import get_db

router = APIRouter()


# -------------------------------------------------------------------
# Student: Invite Code Management
# -------------------------------------------------------------------

@router.post(
    "/invite-code",
    response_model=InviteCodeCreateResponse,
    status_code=201,
    dependencies=[Depends(require_role("student"))],
)
async def create_invite_code(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a new parent invite code. Invalidates any existing active codes."""
    return await generate_invite_code(db, current_user.user_id)


@router.get(
    "/invite-code",
    response_model=InviteCodeResponse | None,
    dependencies=[Depends(require_role("student"))],
)
async def get_invite_code(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the student's current active invite code, or null if none."""
    return await get_active_invite_code(db, current_user.user_id)


@router.delete(
    "/invite-code",
    response_model=InviteCodeCreateResponse,
    dependencies=[Depends(require_role("student"))],
)
async def regenerate_invite_code(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Revoke current invite code and generate a new one."""
    return await generate_invite_code(db, current_user.user_id)


# -------------------------------------------------------------------
# Parent: Redeem Invite Code
# -------------------------------------------------------------------

@router.post(
    "/redeem",
    response_model=RedeemInviteResponse,
    status_code=201,
    dependencies=[Depends(require_role("parent"))],
)
async def redeem_code(
    payload: RedeemInviteRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Redeem an invite code to link parent and student accounts."""
    return await redeem_invite_code(
        db,
        current_user.user_id,
        current_user.tenant_id,
        payload.invite_code,
        payload.relationship,
    )


# -------------------------------------------------------------------
# Student: Linked Parents Management
# -------------------------------------------------------------------

@router.get(
    "/parents",
    response_model=LinkedParentsListResponse,
    dependencies=[Depends(require_role("student"))],
)
async def list_linked_parents(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all parents linked to the current student."""
    parents = await get_linked_parents(db, current_user.user_id)
    return LinkedParentsListResponse(parents=parents)


@router.delete(
    "/parents/{link_id}",
    status_code=204,
    dependencies=[Depends(require_role("student"))],
)
async def revoke_parent(
    link_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Revoke a parent's access to the student's data."""
    await revoke_parent_link(db, current_user.user_id, link_id)


# -------------------------------------------------------------------
# Student: Guardian Management
# -------------------------------------------------------------------

@router.get(
    "/guardians",
    response_model=GuardianListResponse,
    dependencies=[Depends(require_role("student"))],
)
async def get_guardians(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List the student's guardian records."""
    return await list_guardians(db, current_user.user_id)


@router.post(
    "/guardians",
    response_model=GuardianResponse,
    status_code=201,
    dependencies=[Depends(require_role("student"))],
)
async def add_guardian(
    payload: GuardianCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a guardian (name, email, phone, relationship; optionally primary)."""
    return await create_guardian(db, current_user.user_id, payload)


@router.patch(
    "/guardians/{guardian_id}",
    response_model=GuardianResponse,
    dependencies=[Depends(require_role("student"))],
)
async def edit_guardian(
    guardian_id: uuid.UUID,
    payload: GuardianUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Edit a guardian record."""
    return await update_guardian(db, current_user.user_id, guardian_id, payload)


@router.delete(
    "/guardians/{guardian_id}",
    status_code=204,
    dependencies=[Depends(require_role("student"))],
)
async def remove_guardian(
    guardian_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a guardian record."""
    await delete_guardian(db, current_user.user_id, guardian_id)


@router.post(
    "/guardians/{guardian_id}/invite-code",
    response_model=InviteCodeCreateResponse,
    status_code=201,
    dependencies=[Depends(require_role("student"))],
)
async def create_guardian_invite_code(
    guardian_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate an invite code for this guardian to share with the parent."""
    return await generate_guardian_invite_code(db, current_user.user_id, guardian_id)


# -------------------------------------------------------------------
# Parent: Linked Children
# -------------------------------------------------------------------

@router.get(
    "/children",
    response_model=LinkedChildrenListResponse,
    dependencies=[Depends(require_role("parent"))],
)
async def list_linked_children(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all children linked to the current parent."""
    children = await get_linked_children(db, current_user.user_id)
    return LinkedChildrenListResponse(children=children)
