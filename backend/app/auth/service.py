"""
Kio Auth Service
Business logic for registration, login, and token management.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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

    # 2b. Seat enforcement: student signups are capped by the school's seat limit
    if payload.role == "student":
        await _enforce_student_seat_limit(db, tenant)

    # 3. Check duplicate email (normalized to lowercase)
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # 4. Create user
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=email,
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

    # 7. Issue email-verification token (link logged until SMTP is wired up)
    _issue_verification_link(user)

    # 8. Generate tokens
    tokens = _generate_tokens(user)

    return user, tokens


def _issue_verification_link(user: User) -> None:
    """Create a 24h verification token and log the link (SMTP delivery is a follow-up)."""
    from datetime import timedelta

    token = create_access_token(
        {"sub": str(user.user_id), "purpose": "email_verify"},
        expires_delta=timedelta(hours=24),
    )
    logger.info("Email verification link for %s: /auth/verify?token=%s", user.email, token)


async def verify_email(db: AsyncSession, token: str) -> None:
    """Mark a user's email as verified from a verification token."""
    from jose import JWTError

    try:
        payload = decode_token(token)
        if payload.get("purpose") != "email_verify":
            raise ValueError("wrong purpose")
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_verified = True
    await db.flush()


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
    result = await db.execute(select(User).where(User.email == email.lower()))
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


async def google_authenticate(db: AsyncSession, google_id_token: str):
    """
    Authenticate (or begin registration) via a Google ID token.

    Returns a GoogleAuthResponse:
    - existing google_sub -> login
    - existing email (password account) -> link google_sub, then login
    - new user -> registration_required + short-lived registration token
    """
    from datetime import timedelta

    from app.auth.google import verify_google_id_token
    from app.auth.schemas import GoogleAuthResponse, UserResponse

    info = verify_google_id_token(google_id_token)

    # 1. Existing Google-linked account
    result = await db.execute(select(User).where(User.google_sub == info["sub"]))
    user = result.scalar_one_or_none()

    # 2. Existing email/password account -> link Google to it
    if user is None:
        result = await db.execute(select(User).where(User.email == info["email"]))
        user = result.scalar_one_or_none()
        if user is not None:
            user.google_sub = info["sub"]
            if not user.profile_image and info.get("picture"):
                user.profile_image = info["picture"]
            user.is_verified = True

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your administrator.",
            )
        user.last_login = datetime.now(timezone.utc)
        await db.flush()
        tokens = _generate_tokens(user)
        return GoogleAuthResponse(
            status="authenticated",
            tokens=tokens,
            user=UserResponse.model_validate(user),
        )

    # 3. New user -> issue a short-lived registration token carrying verified profile
    name_parts = (info.get("name") or "").strip().split(" ", 1)
    first_name = name_parts[0] or info["email"].split("@")[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    registration_token = create_access_token(
        {
            "sub": info["sub"],
            "email": info["email"],
            "first_name": first_name,
            "last_name": last_name,
            "picture": info.get("picture") or "",
            "purpose": "google_registration",
        },
        expires_delta=timedelta(minutes=30),
    )
    return GoogleAuthResponse(
        status="registration_required",
        registration_token=registration_token,
        email=info["email"],
        first_name=first_name,
        last_name=last_name,
        profile_image=info.get("picture"),
    )


async def google_complete_registration(db: AsyncSession, payload) -> tuple[User, TokenResponse]:
    """
    Finish a Google signup. Only student/parent self-signup is allowed.
    Reuses tenant resolution, seat enforcement, profile creation, and invite auto-redeem.
    """
    from jose import JWTError

    from app.auth.schemas import GoogleCompleteRequest  # noqa: F401 (type hint clarity)

    try:
        claims = decode_token(payload.registration_token)
        if claims.get("purpose") != "google_registration":
            raise ValueError("wrong purpose")
        google_sub = claims["sub"]
        email = claims["email"].lower()
        first_name = claims.get("first_name") or email.split("@")[0]
        last_name = claims.get("last_name") or ""
        picture = claims.get("picture") or None
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Google registration session. Please try again.",
        )

    # Role is validated by the schema to student|parent; school_code required for both
    roles_requiring_school_code = {"student", "parent"}
    if payload.role in roles_requiring_school_code and not payload.school_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"School code is required for {payload.role} accounts",
        )

    tenant = await _resolve_tenant(db, payload.school_code)

    if payload.role == "student":
        await _enforce_student_seat_limit(db, tenant)

    # Guard against a race / double submit
    existing = await db.execute(
        select(User).where((User.email == email) | (User.google_sub == google_sub))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try signing in instead.",
        )

    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=email,
        password_hash=None,
        google_sub=google_sub,
        auth_provider="google",
        role=payload.role,
        first_name=first_name,
        last_name=last_name,
        phone=payload.phone,
        profile_image=picture,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()

    await _create_role_profile(db, user)

    if payload.role == "parent" and payload.invite_code:
        await _auto_redeem_invite(db, user, payload.invite_code)

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

async def _enforce_student_seat_limit(db: AsyncSession, tenant: Tenant) -> None:
    """Raise 403 if the tenant has reached its active-student seat limit."""
    seat_count = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.tenant_id == tenant.tenant_id,
            User.role == "student",
            User.is_active == True,  # noqa: E712
        )
    )
    if (seat_count.scalar() or 0) >= tenant.student_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your school has reached its student seat limit. "
                   "Please contact your school administrator.",
        )


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
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent signup created it first (school_code is unique) -- re-select
            await db.rollback()
            result = await db.execute(
                select(Tenant).where(Tenant.school_code == "DEFAULT")
            )
            tenant = result.scalar_one()

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
