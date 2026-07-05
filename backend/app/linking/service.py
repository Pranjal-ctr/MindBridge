"""
MindBridge Linking Service
Business logic for parent-student invite code system.
"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.linking.schemas import (
    InviteCodeCreateResponse,
    InviteCodeResponse,
    LinkedChildResponse,
    LinkedParentResponse,
    RedeemInviteResponse,
)
from database.models import (
    ParentInviteCode,
    ParentProfile,
    StudentParentLink,
    StudentProfile,
    User,
)

# Code config
CODE_PREFIX = "MB"
CODE_LENGTH = 4  # -> "MB-XXXX"
CODE_EXPIRY_HOURS = 48
# Remove ambiguous chars: 0/O, 1/I/L
SAFE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _generate_code() -> str:
    """Generate a human-friendly invite code like MB-X7K9."""
    suffix = "".join(secrets.choice(SAFE_CHARS) for _ in range(CODE_LENGTH))
    return f"{CODE_PREFIX}-{suffix}"


# -------------------------------------------------------------------
# Student: Get Student Profile Helper
# -------------------------------------------------------------------

async def _get_student_profile(db: AsyncSession, user_id: uuid.UUID) -> StudentProfile:
    """Get student profile from user_id, raising 404 if not found."""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )
    return student


async def _get_parent_profile(db: AsyncSession, user_id: uuid.UUID) -> ParentProfile:
    """Get parent profile from user_id, raising 404 if not found."""
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent profile not found",
        )
    return parent


# -------------------------------------------------------------------
# Student: Generate Invite Code
# -------------------------------------------------------------------

async def generate_invite_code(db: AsyncSession, user_id: uuid.UUID) -> InviteCodeCreateResponse:
    """Generate a new invite code for a student. Invalidates any existing active codes."""
    student = await _get_student_profile(db, user_id)

    # Invalidate existing unused codes for this student
    existing = await db.execute(
        select(ParentInviteCode).where(
            ParentInviteCode.student_id == student.student_id,
            ParentInviteCode.is_used == False,  # noqa: E712
        )
    )
    for old_code in existing.scalars().all():
        old_code.is_used = True  # Mark as used to invalidate

    # Generate unique code (retry if collision)
    for _ in range(10):
        code = _generate_code()
        collision = await db.execute(
            select(ParentInviteCode).where(ParentInviteCode.code == code)
        )
        if not collision.scalar_one_or_none():
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate unique code. Try again.",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(hours=CODE_EXPIRY_HOURS)

    invite = ParentInviteCode(
        code_id=uuid.uuid4(),
        student_id=student.student_id,
        code=code,
        is_used=False,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()

    return InviteCodeCreateResponse(
        code=code,
        expires_at=expires_at,
    )


# -------------------------------------------------------------------
# Student: Get Active Invite Code
# -------------------------------------------------------------------

async def get_active_invite_code(db: AsyncSession, user_id: uuid.UUID) -> InviteCodeResponse | None:
    """Get the student's current active (unused, unexpired) invite code."""
    student = await _get_student_profile(db, user_id)

    result = await db.execute(
        select(ParentInviteCode).where(
            ParentInviteCode.student_id == student.student_id,
            ParentInviteCode.is_used == False,  # noqa: E712
            ParentInviteCode.expires_at > datetime.now(timezone.utc),
        ).order_by(ParentInviteCode.created_at.desc()).limit(1)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        return None

    return InviteCodeResponse.model_validate(invite)


# -------------------------------------------------------------------
# Parent: Redeem Invite Code
# -------------------------------------------------------------------

async def redeem_invite_code(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    invite_code: str,
    relationship: str,
) -> RedeemInviteResponse:
    """
    Parent redeems a student's invite code to link accounts.

    Validates:
    1. Code exists
    2. Code is not expired
    3. Code is not already used
    4. Student belongs to the same tenant
    5. Parent is not already linked to this student
    """
    parent = await _get_parent_profile(db, user_id)

    # 1. Find the invite code
    result = await db.execute(
        select(ParentInviteCode).where(
            ParentInviteCode.code == invite_code.upper().strip()
        )
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    # 2. Check expiry
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite code has expired. Ask the student to generate a new one.",
        )

    # 3. Check if already used
    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invite code has already been used",
        )

    # 4. Get student and verify same tenant
    student_result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.student_id == invite.student_id)
    )
    row = student_result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    student, student_user = row

    if student_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student belongs to a different institution",
        )

    # 5. Check if already linked
    existing_link = await db.execute(
        select(StudentParentLink).where(
            StudentParentLink.student_id == student.student_id,
            StudentParentLink.parent_id == parent.parent_id,
        )
    )
    if existing_link.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already linked to this student",
        )

    # All valid — create link and mark code as used
    link = StudentParentLink(
        link_id=uuid.uuid4(),
        student_id=student.student_id,
        parent_id=parent.parent_id,
        relationship_=relationship,
    )
    db.add(link)

    invite.is_used = True
    invite.used_by = parent.parent_id

    await db.flush()

    return RedeemInviteResponse(
        link_id=link.link_id,
        student_name=f"{student_user.first_name} {student_user.last_name}",
        relationship=relationship,
    )


# -------------------------------------------------------------------
# Student: List Linked Parents
# -------------------------------------------------------------------

async def get_linked_parents(db: AsyncSession, user_id: uuid.UUID) -> list[LinkedParentResponse]:
    """Get all parents linked to the student."""
    student = await _get_student_profile(db, user_id)

    result = await db.execute(
        select(StudentParentLink, ParentProfile, User)
        .join(ParentProfile, StudentParentLink.parent_id == ParentProfile.parent_id)
        .join(User, ParentProfile.user_id == User.user_id)
        .where(StudentParentLink.student_id == student.student_id)
    )

    parents = []
    for link, parent, user in result.all():
        parents.append(
            LinkedParentResponse(
                link_id=link.link_id,
                parent_id=parent.parent_id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                phone=user.phone,
                relationship=link.relationship_,
                linked_at=link.created_at,
            )
        )

    return parents


# -------------------------------------------------------------------
# Student: Revoke Parent Access
# -------------------------------------------------------------------

async def revoke_parent_link(db: AsyncSession, user_id: uuid.UUID, link_id: uuid.UUID) -> None:
    """Remove a parent's access to the student's data."""
    student = await _get_student_profile(db, user_id)

    result = await db.execute(
        select(StudentParentLink).where(
            StudentParentLink.link_id == link_id,
            StudentParentLink.student_id == student.student_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    await db.delete(link)
    await db.flush()


# -------------------------------------------------------------------
# Parent: List Linked Children
# -------------------------------------------------------------------

async def get_linked_children(db: AsyncSession, user_id: uuid.UUID) -> list[LinkedChildResponse]:
    """Get all children linked to the parent."""
    parent = await _get_parent_profile(db, user_id)

    result = await db.execute(
        select(StudentParentLink, StudentProfile, User)
        .join(StudentProfile, StudentParentLink.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentParentLink.parent_id == parent.parent_id)
    )

    children = []
    for link, student, user in result.all():
        children.append(
            LinkedChildResponse(
                link_id=link.link_id,
                student_id=student.student_id,
                first_name=user.first_name,
                last_name=user.last_name,
                age=student.age,
                wellness_score=float(student.wellness_score) if student.wellness_score else None,
                risk_level=student.risk_level or "green",
                relationship=link.relationship_,
                linked_at=link.created_at,
            )
        )

    return children
