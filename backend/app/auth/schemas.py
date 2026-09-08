"""
Kio Auth Schemas
Pydantic v2 models for authentication requests and responses.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# Shared validators --------------------------------------------------

# A plausible phone number: optional leading "+" then 7-15 digits (E.164 range).
# Formatting characters (spaces, dashes, dots, parens) are stripped first, so a
# 10-digit local number and an international "+<cc>..." number both validate.
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _normalize_phone(value: str) -> str:
    cleaned = re.sub(r"[\s\-().]", "", value or "")
    if not _PHONE_RE.match(cleaned):
        raise ValueError("Enter a valid mobile number (7-15 digits).")
    return cleaned


# Requests -----------------------------------------------------------

class SignupRequest(BaseModel):
    """New user registration payload."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(
        ...,
        pattern=r"^(student|parent)$",
        description="Self-signup is limited to student/parent. Staff accounts are provisioned by a platform admin.",
    )
    phone: str = Field(..., min_length=5, max_length=20, description="Contact number (required)")
    date_of_birth: date = Field(
        ...,
        description=(
            "Required. Drives the age gate: under 13 is refused outright, "
            "13-17 needs verified guardian consent before the account is usable."
        ),
    )
    accept_terms: bool = Field(
        ...,
        description="Must be true. Recorded against the current terms version.",
    )
    accept_privacy: bool = Field(
        ...,
        description="Must be true. Recorded against the current privacy version.",
    )
    school_code: str | None = Field(None, max_length=50, description="Required for student, parent, school_admin")
    invite_code: str | None = Field(None, max_length=10, description="Parent invite code from student (parent signup only)")

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("accept_terms", "accept_privacy")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        # Rejected here rather than in the service so the API contract states
        # it: there is no code path that creates an account without consent.
        if not v:
            raise ValueError(
                "You must accept the Terms of Service and Privacy Policy to create an account."
            )
        return v


class LoginRequest(BaseModel):
    """Login credentials."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh payload."""
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    """Token from a verification email link."""
    token: str = Field(..., min_length=10)


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset link."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Set a new password using a token from a reset email."""
    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=8, max_length=128)


# Responses ----------------------------------------------------------

class TokenResponse(BaseModel):
    """JWT token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class UserResponse(BaseModel):
    """User profile response (used after auth)."""
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    first_name: str
    last_name: str
    phone: str | None = None
    profile_image: str | None = None
    is_active: bool
    is_verified: bool = False
    last_login: datetime | None = None
    created_at: datetime
    # Age gate (migration 015). Additive and nullable: accounts created before
    # the consent layer have neither, and "unknown" is the honest answer for
    # them rather than assuming they are adults.
    date_of_birth: date | None = None
    guardian_consent_status: str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Combined auth response with tokens and user info."""
    tokens: TokenResponse
    user: UserResponse


# Google Sign-In ----------------------------------------------------

class GoogleAuthRequest(BaseModel):
    """Frontend posts a Google ID token obtained via Google Identity Services."""
    id_token: str = Field(..., min_length=10)


class GoogleAuthResponse(BaseModel):
    """
    Result of /auth/google.

    - status="authenticated": existing/linked account -> tokens + user present.
    - status="registration_required": new Google user -> registration_token +
      prefilled Google profile; frontend collects role + mobile + institution
      code and calls /auth/google/complete.
    """
    status: str  # "authenticated" | "registration_required"
    tokens: TokenResponse | None = None
    user: UserResponse | None = None
    registration_token: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profile_image: str | None = None


class GoogleCompleteRequest(BaseModel):
    """Complete a Google signup with the only fields Google can't provide.

    Date of birth and consent are required here for the same reason they are on
    SignupRequest: Google verifies an email address, not an age, and without
    these fields signing in with Google would be a way around the age gate.
    """
    registration_token: str = Field(..., min_length=10)
    role: str = Field(..., pattern=r"^(student|parent)$")
    phone: str = Field(..., min_length=5, max_length=20)
    date_of_birth: date
    accept_terms: bool
    accept_privacy: bool
    school_code: str | None = Field(None, max_length=50)
    invite_code: str | None = Field(None, max_length=10)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("accept_terms", "accept_privacy")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must accept the Terms of Service and Privacy Policy to create an account."
            )
        return v
