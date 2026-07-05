"""
MindBridge Auth Service
Business logic for registration, login, and token management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import SignupRequest, TokenResponse
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from database.models import (
    CounselorProfile,
    ParentProfile,
    SchoolAdminProfile,
    StudentProfile,
    Tenant,
    User,
)


async def register_user(db: AsyncSession, payload: SignupRequest) -> tuple[User, TokenResponse]:
    """
    Register a new user with role-specific profile creation.

    Steps:
    1. Validate school_code per role
    2. Resolve tenant from school_code
    3. Check for duplicate email
    4. Create user + role-specific profile
    5. If parent with invite_code, auto-redeem and link accounts
    6. Generate JWT tokens
    """
    # 1. Validate school_code requirement per role
    roles_requiring_school_code = {"student", "parent", "school_admin"}
    if payload.role in roles_requiring_school_code and not payload.school_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"School code is required for {payload.role} accounts",
        )

    # 2. Resolve tenant (counselors get default tenant if no school_code)
    tenant = await _resolve_tenant(db, payload.school_code)

    # 3. Check duplicate email
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # 4. Create user
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # Get user_id

    # 5. Create role-specific profile
    await _create_role_profile(db, user)

    # 6. If parent with invite_code, auto-redeem
    if payload.role == "parent" and payload.invite_code:
        await _auto_redeem_invite(db, user, payload.invite_code)

    # 7. Generate tokens
    tokens = _generate_tokens(user)

    return user, tokens


async def _auto_redeem_invite(db: AsyncSession, user: User, invite_code: str) -> None:
    """Auto-redeem an invite code during parent signup."""
    from app.linking.service import redeem_invite_code

    try:
        await redeem_invite_code(
            db,
            user.user_id,
            user.tenant_id,
            invite_code,
            "parent",
        )
    except HTTPException:
        # Don't block signup if invite code is invalid — parent can redeem later
        pass


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[User, TokenResponse]:
    """
    Authenticate user with email/password.

    Returns:
        Tuple of (user, tokens).

    Raises:
        HTTPException 401 if credentials are invalid.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    tokens = _generate_tokens(user)
    return user, tokens


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """
    Validate refresh token and issue new access token.
    """
    from jose import JWTError

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return _generate_tokens(user)


# -------------------------------------------------------------------
# Private helpers
# -------------------------------------------------------------------

async def _resolve_tenant(db: AsyncSession, school_code: str | None) -> Tenant:
    """Look up tenant by school code, or use a default."""
    if school_code:
        result = await db.execute(
            select(Tenant).where(Tenant.school_code == school_code)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No school found with code '{school_code}'",
            )
        return tenant

    # If no school_code, try to find or create a default tenant
    result = await db.execute(
        select(Tenant).where(Tenant.school_code == "DEFAULT")
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Default Organization",
            tenant_type="organization",
            school_code="DEFAULT",
            status="active",
        )
        db.add(tenant)
        await db.flush()

    return tenant


async def _create_role_profile(db: AsyncSession, user: User) -> None:
    """Create the role-specific profile for a new user."""
    if user.role == "student":
        db.add(StudentProfile(user_id=user.user_id))
    elif user.role == "parent":
        db.add(ParentProfile(user_id=user.user_id))
    elif user.role == "counselor":
        db.add(CounselorProfile(user_id=user.user_id))
    elif user.role == "school_admin":
        db.add(SchoolAdminProfile(user_id=user.user_id))

    await db.flush()


def _generate_tokens(user: User) -> TokenResponse:
    """Create access + refresh token pair for a user."""
    token_data = {
        "sub": str(user.user_id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
