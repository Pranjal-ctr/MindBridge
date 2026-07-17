"""
Kio Auth Router
Authentication endpoints: signup, login, refresh, and current user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    AuthResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleCompleteRequest,
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import (
    authenticate_user,
    google_authenticate,
    google_complete_registration,
    refresh_access_token,
    register_user,
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Register a new user account.

    - Creates user with hashed password
    - Creates role-specific profile (student/parent/counselor/school_admin)
    - Returns JWT tokens + user info
    """
    user, tokens = await register_user(db, payload)
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Finish a Google signup (student/parent only) with mobile + institution code."""
    user, tokens = await google_complete_registration(db, payload)
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


@router.post("/verify")
async def verify_email_endpoint(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verify a user's email address from a verification token."""
    await verify_email(db, token)
    return {"status": "verified"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser):
    """
    Get the authenticated user's profile.

    Requires a valid access token in the Authorization header.
    """
    return UserResponse.model_validate(current_user)
