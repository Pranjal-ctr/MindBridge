"""
Kio Auth Router
Authentication endpoints: signup, login, refresh, and current user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleCompleteRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.auth.service import (
    authenticate_user,
    google_authenticate,
    google_complete_registration,
    refresh_access_token,
    register_user,
    request_password_reset,
    resend_verification,
    reset_password,
    verify_email,
)
from app.dependencies import CurrentUser
from app.rate_limit import rate_limit
from database.session import get_db

router = APIRouter()


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("signup", 10))],
)
async def signup(
    payload: SignupRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Register a new user account.

    - Runs the age gate (under 13 refused; 13-17 held for guardian consent)
    - Creates user with hashed password
    - Creates role-specific profile (student/parent/counselor/school_admin)
    - Records terms/privacy consent with IP and user agent
    - Sends the email-verification link in the background
    - Returns JWT tokens + user info
    """
    user, tokens = await register_user(db, payload, background_tasks, request)
    return AuthResponse(
        tokens=tokens,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("login", 10))],
)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Authenticate with email and password.

    Returns JWT access & refresh tokens with user profile.
    """
    user, tokens = await authenticate_user(db, payload.email, payload.password)
    return AuthResponse(
        tokens=tokens,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/google",
    response_model=GoogleAuthResponse,
    dependencies=[Depends(rate_limit("login", 10))],
)
async def google_auth(
    payload: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Sign in / sign up / link with Google (ID-token flow).

    Returns either the normal token pair (existing or linked account) or a
    registration_required result carrying a short-lived registration token for
    new users, who then call /auth/google/complete with mobile + institution code.
    """
    return await google_authenticate(db, payload.id_token)


@router.post(
    "/google/complete",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("signup", 10))],
)
async def google_complete(
    payload: GoogleCompleteRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Finish a Google signup (student/parent only).

    Requires the same date of birth and consent as password signup — Google
    verifies an email address, not an age.
    """
    user, tokens = await google_complete_registration(db, payload, request)
    return AuthResponse(
        tokens=tokens,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Refresh an expired access token using a valid refresh token.
    """
    return await refresh_access_token(db, payload.refresh_token)


@router.post("/verify", dependencies=[Depends(rate_limit("verify", 20))])
async def verify_email_endpoint(
    payload: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Verify a user's email address from a verification token.

    Called by the frontend /verify-email page with the token from the email link.
    Idempotent — re-clicking a still-valid link succeeds again.
    """
    await verify_email(db, payload.token)
    return {"status": "verified"}


@router.post("/verify/resend", dependencies=[Depends(rate_limit("verify_resend", 3))])
async def resend_verification_endpoint(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Re-send the verification email to the signed-in user (409 if already verified)."""
    await resend_verification(db, current_user, background_tasks)
    return {"status": "sent"}


@router.post("/password/forgot", dependencies=[Depends(rate_limit("password_forgot", 5))])
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Email a password-reset link.

    Always returns the same response whether or not the address exists — this
    endpoint must not reveal which emails have accounts.
    """
    await request_password_reset(db, payload.email, background_tasks)
    return {"status": "sent"}


@router.post("/password/reset", dependencies=[Depends(rate_limit("password_reset", 5))])
async def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Set a new password using a token from a reset email. Links are single-use."""
    await reset_password(db, payload.token, payload.password)
    return {"status": "reset"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser):
    """
    Get the authenticated user's profile.

    Requires a valid access token in the Authorization header.
    """
    return UserResponse.model_validate(current_user)
