"""
Kio Auth Service
Business logic for registration, login, and token management.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_audit, log_audit_detached
from app.audit_actions import (
    AuditAction,
    AuditEntity,
    AuditResult,
    AuditSeverity,
)
from app.auth.schemas import SignupRequest, TokenResponse
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.auth.sessions import (
    REASON_LOGOUT,
    REASON_LOGOUT_ALL,
    consume_session,
    create_session,
    revoke_all_for_user,
    revoke_family,
)
from app.config import settings
from app.rate_limit import clear_failures, note_failure
from app.consent.service import (
    enforce_age_gate,
    record_signup_consent,
    sync_student_age,
)
from app.email.service import try_send
from app.email.templates import password_reset_email, verification_email
from database.models import (
    CounselorProfile,
    ParentProfile,
    SchoolAdminProfile,
    StudentProfile,
    Tenant,
    User,
)

logger = logging.getLogger(__name__)


async def register_user(
    db: AsyncSession,
    payload: SignupRequest,
    background_tasks: BackgroundTasks | None = None,
    request: Request | None = None,
) -> tuple[User, TokenResponse]:
    """
    Register a new user with role-specific profile creation.

    Steps:
    0. Age gate (refuses under-13 outright; flags 13-17 for guardian consent)
    1. Validate school_code per role
    2. Resolve tenant from school_code
    3. Check for duplicate email
    4. Create user + role-specific profile
    5. If parent with invite_code, auto-redeem and link accounts
    6. Record the terms/privacy consent that Pydantic already required
    7. Generate JWT tokens
    """
    # 0. Age gate first: an under-13 signup must be refused before a row, a
    # tenant seat, or a verification email is spent on it.
    guardian_status = enforce_age_gate(payload.date_of_birth)

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
        date_of_birth=payload.date_of_birth,
        guardian_consent_status=guardian_status,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # Get user_id

    # 5. Create role-specific profile
    await _create_role_profile(db, user)
    await sync_student_age(db, user)

    # 6. If parent with invite_code, auto-redeem
    if payload.role == "parent" and payload.invite_code:
        await _auto_redeem_invite(db, user, payload.invite_code)

    # 7. Record consent. The schema already refused false values, so reaching
    # here means both were accepted; this writes the auditable evidence.
    await record_signup_consent(db, user.user_id, request=request)

    # 8. Send the email-verification link (background when the router supplies a queue)
    await dispatch_verification_email(user, background_tasks)

    # 9. Generate tokens
    tokens = await _generate_tokens(db, user, request=request)

    # Role and school are the load-bearing facts here: this is the record of
    # an account coming into existence with a given level of access. The
    # guardian-consent state is included because for a 13-17 signup it is the
    # difference between an active account and one awaiting approval.
    await log_audit(
        db,
        user_id=user.user_id,
        action=AuditAction.SIGNUP,
        entity_type=AuditEntity.USER,
        entity_id=user.user_id,
        details={
            "role": user.role,
            "guardian_consent_status": user.guardian_consent_status,
            "self_signup": True,
        },
        request=request,
        actor=user,
        severity=AuditSeverity.NOTICE,
    )

    return user, tokens


# -------------------------------------------------------------------
# Emailed one-time links (verification + password reset)
# -------------------------------------------------------------------

def _link(path: str, token: str) -> str:
    """Build an absolute frontend URL carrying a one-time token."""
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}?token={token}"


def _password_fingerprint(password_hash: str) -> str:
    """
    Short digest of the current password hash, embedded in reset tokens.

    This makes a reset link genuinely single-use with no extra table: once the
    password changes the stored hash changes, so the fingerprint in any
    previously issued token no longer matches and the link is dead. It also
    invalidates outstanding reset links whenever the password changes by any
    other route.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def _decode_purpose_token(token: str, expected_purpose: str, error_detail: str) -> dict:
    """Decode a JWT and assert its `purpose` claim, or raise 400."""
    from jose import JWTError

    try:
        payload = decode_token(token)
        if payload.get("purpose") != expected_purpose:
            raise ValueError("wrong purpose")
        uuid.UUID(payload["sub"])  # validate shape early
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    return payload


async def dispatch_verification_email(
    user: User,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """
    Mint a verification token and send the link.

    Message fields are snapshotted into plain strings before scheduling so the
    background task never touches a detached ORM instance after the request's
    session closes.
    """
    token = create_access_token(
        {"sub": str(user.user_id), "purpose": "email_verify"},
        expires_delta=timedelta(hours=settings.EMAIL_VERIFY_TOKEN_HOURS),
    )
    link = _link("/verify-email", token)
    subject, text, html = verification_email(
        first_name=user.first_name,
        link=link,
        expires_hours=settings.EMAIL_VERIFY_TOKEN_HOURS,
    )
    # Logged so local development works with EMAIL_PROVIDER=noop.
    logger.info("Email verification link for %s: %s", user.email, link)

    message = {"to": user.email, "subject": subject, "body": text, "html": html}
    if background_tasks is not None:
        background_tasks.add_task(try_send, **message)
    else:
        await try_send(**message)


async def verify_email(db: AsyncSession, token: str) -> None:
    """Mark a user's email as verified from a verification token."""
    payload = _decode_purpose_token(
        token, "email_verify", "This verification link is invalid or has expired."
    )

    result = await db.execute(select(User).where(User.user_id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_verified = True
    await db.flush()
    await log_audit(
        db,
        user_id=user.user_id,
        action=AuditAction.EMAIL_VERIFIED,
        entity_type=AuditEntity.USER,
        entity_id=user.user_id,
        actor=user,
        severity=AuditSeverity.INFO,
    )


async def resend_verification(
    db: AsyncSession,
    user: User,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Re-send the verification link for an authenticated, still-unverified user."""
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your email address is already verified.",
        )
    await dispatch_verification_email(user, background_tasks)


async def request_password_reset(
    db: AsyncSession,
    email: str,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """
    Email a password-reset link.

    Always completes silently, whether or not the address belongs to an account:
    reporting "no such user" here would turn this endpoint into an account
    enumeration oracle. Google-only accounts have no password to reset, so they
    are skipped too — the caller still sees the same generic response.
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not user.password_hash:
        logger.info("Password reset requested for non-resettable address %s (no email sent)", email)
        return

    token = create_access_token(
        {
            "sub": str(user.user_id),
            "purpose": "password_reset",
            "pwf": _password_fingerprint(user.password_hash),
        },
        expires_delta=timedelta(hours=settings.PASSWORD_RESET_TOKEN_HOURS),
    )
    link = _link("/reset-password", token)
    subject, text, html = password_reset_email(
        first_name=user.first_name,
        link=link,
        expires_hours=settings.PASSWORD_RESET_TOKEN_HOURS,
    )
    logger.info("Password reset link for %s: %s", user.email, link)

    message = {"to": user.email, "subject": subject, "body": text, "html": html}
    if background_tasks is not None:
        background_tasks.add_task(try_send, **message)
    else:
        await try_send(**message)

    # Only the branch that really sent a link is audited. The early return
    # above is anti-enumeration by design; writing a row for an address with
    # no account would accumulate exactly the list this endpoint refuses to
    # confirm. The reset token itself is never recorded -- it is a password
    # equivalent for as long as it is valid.
    await log_audit(
        db,
        user_id=user.user_id,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        entity_type=AuditEntity.USER,
        entity_id=user.user_id,
        actor=user,
        severity=AuditSeverity.NOTICE,
    )


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """Consume a reset token and set a new password."""
    expired_detail = "This reset link is invalid or has expired. Please request a new one."
    payload = _decode_purpose_token(token, "password_reset", expired_detail)

    result = await db.execute(select(User).where(User.user_id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=expired_detail)

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account signs in with Google. Use 'Continue with Google' instead.",
        )

    # Single-use enforcement: the fingerprint stops matching once the password changes.
    if payload.get("pwf") != _password_fingerprint(user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=expired_detail)

    user.password_hash = hash_password(new_password)
    # A completed reset proves control of the inbox.
    user.is_verified = True
    await log_audit(
        db,
        user_id=user.user_id,
        action=AuditAction.PASSWORD_RESET_COMPLETED,
        entity_type=AuditEntity.USER,
        entity_id=user.user_id,
        actor=user,
        severity=AuditSeverity.NOTICE,
    )
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


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    request: Request | None = None,
) -> tuple[User, TokenResponse]:
    """
    Authenticate user with email/password.

    Returns:
        Tuple of (user, tokens).

    Raises:
        HTTPException 401 if credentials are invalid.
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    # Every failure path below raises, which rolls back this session -- so a
    # failed-login row added to it would vanish exactly when it matters most.
    # log_audit_detached() commits in its own session, and swallows its own
    # errors: an audit problem must never be the reason nobody can sign in.
    #
    # The attempted email is recorded because a failed-login trail that does
    # not say which account was targeted cannot show credential stuffing. The
    # submitted password is of course never touched.
    if user is None or not verify_password(password, user.password_hash):
        # Counted per account, not per IP: a shared school IP must not let a
        # classroom throttle each other, nor let an attacker hide in the crowd.
        # Raises 429 once the account is over its limit; the audit row below is
        # written first so the attempt is recorded either way.
        note_failure(
            "login", email.lower(), settings.AUTH_FAILED_LOGINS_PER_MINUTE
        )
        await log_audit_detached(
            user_id=user.user_id if user else None,
            action=AuditAction.LOGIN_FAILED,
            entity_type=AuditEntity.USER,
            entity_id=user.user_id if user else None,
            details={
                "email": email.lower()[:200],
                "reason": "unknown_email" if user is None else "bad_password",
            },
            request=request,
            actor_role=user.role if user else None,
            tenant_id=user.tenant_id if user else None,
            result=AuditResult.FAILURE,
            severity=AuditSeverity.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        await log_audit_detached(
            user_id=user.user_id,
            action=AuditAction.LOGIN_FAILED,
            entity_type=AuditEntity.USER,
            entity_id=user.user_id,
            details={"email": user.email[:200], "reason": "account_deactivated"},
            request=request,
            actor_role=user.role,
            tenant_id=user.tenant_id,
            result=AuditResult.FAILURE,
            severity=AuditSeverity.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    await _ensure_tenant_not_suspended(db, user)

    # Signed in successfully: drop this account's failure count so a student
    # who mistyped their password twice is not throttled afterwards.
    clear_failures("login", email.lower())

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    tokens = await _generate_tokens(db, user, request=request)

    await log_audit_detached(
        user_id=user.user_id,
        action=AuditAction.LOGIN_SUCCESS,
        entity_type=AuditEntity.USER,
        entity_id=user.user_id,
        details={"method": "password"},
        request=request,
        actor_role=user.role,
        tenant_id=user.tenant_id,
        severity=AuditSeverity.INFO,
    )
    return user, tokens


async def google_authenticate(
    db: AsyncSession, google_id_token: str, request: Request | None = None
):
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
            await log_audit_detached(
                user_id=user.user_id,
                action=AuditAction.LOGIN_FAILED,
                entity_type=AuditEntity.USER,
                entity_id=user.user_id,
                details={"method": "google", "reason": "account_deactivated"},
                request=request,
                actor_role=user.role,
                tenant_id=user.tenant_id,
                result=AuditResult.FAILURE,
                severity=AuditSeverity.WARNING,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your administrator.",
            )
        await _ensure_tenant_not_suspended(db, user)
        user.last_login = datetime.now(timezone.utc)
        await db.flush()
        tokens = await _generate_tokens(db, user, request=request)
        # The Google subject identifier is deliberately not recorded: it is a
        # stable cross-service identifier for a person, and the local user id
        # already names them here.
        await log_audit_detached(
            user_id=user.user_id,
            action=AuditAction.GOOGLE_LOGIN,
            entity_type=AuditEntity.USER,
            entity_id=user.user_id,
            details={"method": "google"},
            request=request,
            actor_role=user.role,
            tenant_id=user.tenant_id,
            severity=AuditSeverity.INFO,
        )
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


async def google_complete_registration(
    db: AsyncSession, payload, request: Request | None = None
) -> tuple[User, TokenResponse]:
    """
    Finish a Google signup. Only student/parent self-signup is allowed.
    Reuses tenant resolution, seat enforcement, profile creation, and invite auto-redeem.

    Runs the same age gate and records the same consent as password signup:
    Google verifies an email address, not an age, so skipping either here
    would make "Continue with Google" a way around both.
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

    guardian_status = enforce_age_gate(payload.date_of_birth)

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
        date_of_birth=payload.date_of_birth,
        guardian_consent_status=guardian_status,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()

    await _create_role_profile(db, user)
    await sync_student_age(db, user)

    if payload.role == "parent" and payload.invite_code:
        await _auto_redeem_invite(db, user, payload.invite_code)

    await record_signup_consent(db, user.user_id, request=request)

    tokens = await _generate_tokens(db, user, request=request)
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
        # Tokens issued before refresh sessions existed carry no sid. They are
        # refused rather than honoured: accepting them would leave a window in
        # which the un-revocable tokens this change exists to kill still work.
        session_id = uuid.UUID(payload["sid"])
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

    await _ensure_tenant_not_suspended(db, user)

    # Spend the presented session and issue its successor in the same family.
    # consume_session raises if it is unknown, expired, or already spent -- and
    # in the last case revokes the whole family, because a spent token being
    # presented again means a copy of it is in circulation.
    session = await consume_session(db, session_id)
    if session.user_id != user.user_id:
        # The token's subject and its session disagree: a forged or tampered
        # payload. Nothing about this is recoverable.
        await revoke_family(db, session.family_id, "mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return await _generate_tokens(db, user, family_id=session.family_id)


async def logout(
    db: AsyncSession,
    refresh_token: str,
    *,
    all_devices: bool = False,
    request: Request | None = None,
) -> dict[str, str]:
    """
    Revoke the session behind a refresh token.

    Deliberately forgiving: an unreadable or already-dead token still returns
    success. Logout is the one action that must never appear to fail -- a
    student on a shared machine who sees "logout failed" has no next move, and
    the desired end state (that token being useless) already holds.
    """
    from jose import JWTError

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            return {"status": "logged_out"}
        family_id = uuid.UUID(payload["fam"])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return {"status": "logged_out"}

    if all_devices:
        await revoke_all_for_user(db, user_id, REASON_LOGOUT_ALL)
    else:
        await revoke_family(db, family_id, REASON_LOGOUT)

    # Detached, to match this function's contract: logout must never appear to
    # fail, so an audit problem cannot be allowed to turn it into a 500. The
    # unreadable-token branches above return early and write nothing -- there
    # is no identity to attribute the event to.
    await log_audit_detached(
        user_id=user_id,
        action=AuditAction.LOGOUT,
        entity_type=AuditEntity.REFRESH_SESSION,
        details={"all_devices": all_devices},
        request=request,
        severity=AuditSeverity.INFO,
    )
    return {"status": "logged_out"}



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


async def _ensure_tenant_not_suspended(db: AsyncSession, user: User) -> None:
    """Block login/refresh for users of suspended or archived schools.
    Platform admins are exempt so the school can always be reactivated."""
    if user.role == "admin":
        return
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is not None and (tenant.deleted_at is not None or tenant.status == "suspended"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your school's access is currently suspended. Contact Kio support.",
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
        if tenant.deleted_at is not None or tenant.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This school is not accepting registrations right now.",
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


async def _generate_tokens(
    db: AsyncSession,
    user: User,
    *,
    family_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> TokenResponse:
    """
    Create an access + refresh pair, recording the refresh side server-side.

    The refresh token carries the session row's id (`sid`) and its family, so
    it can be revoked. The access token is unchanged: still stateless, still
    short-lived, still carrying only sub/tenant/role.
    """
    token_data = {
        "sub": str(user.user_id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }

    session = await create_session(db, user.user_id, family_id=family_id, request=request)

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(
        {**token_data, "sid": str(session.session_id), "fam": str(session.family_id)}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
