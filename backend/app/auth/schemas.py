"""
Kio Auth Schemas
Pydantic v2 models for authentication requests and responses.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

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
    school_code: str | None = Field(None, max_length=50, description="Required for student, parent, school_admin")
    invite_code: str | None = Field(None, max_length=10, description="Parent invite code from student (parent signup only)")

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class LoginRequest(BaseModel):
    """Login credentials."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh payload."""
    refresh_token: str


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
    last_login: datetime | None = None
    created_at: datetime

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
    """Complete a Google signup with the only fields Google can't provide."""
    registration_token: str = Field(..., min_length=10)
    role: str = Field(..., pattern=r"^(student|parent)$")
    phone: str = Field(..., min_length=5, max_length=20)
    school_code: str | None = Field(None, max_length=50)
    invite_code: str | None = Field(None, max_length=10)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return _normalize_phone(v)
