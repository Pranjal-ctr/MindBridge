"""
MindBridge Auth Schemas
Pydantic v2 models for authentication requests and responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
