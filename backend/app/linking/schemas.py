"""
Kio Linking Schemas
Pydantic v2 models for parent-student invite code system.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Invite Codes
# -------------------------------------------------------------------

class InviteCodeResponse(BaseModel):
    """Active invite code for a student."""
    code_id: uuid.UUID
    code: str
    expires_at: datetime
    is_used: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteCodeCreateResponse(BaseModel):
    """Response after generating a new invite code."""
    code: str
    expires_at: datetime
    message: str = "Share this code with your parent to link accounts"


# -------------------------------------------------------------------
# Redeem
# -------------------------------------------------------------------

class RedeemInviteRequest(BaseModel):
    """Parent redeems a student's invite code."""
    invite_code: str = Field(..., min_length=4, max_length=10, description="Invite code from student (e.g. MB-X7K9)")
    relationship: str = Field(
        default="parent",
        pattern=r"^(parent|guardian|mother|father|other)$",
        description="Relationship to student",
    )


class RedeemInviteResponse(BaseModel):
    """Response after successfully redeeming an invite code."""
    link_id: uuid.UUID
    student_name: str
    relationship: str
    message: str = "Account successfully linked"


# -------------------------------------------------------------------
# Linked Users
# -------------------------------------------------------------------

class LinkedParentResponse(BaseModel):
    """A parent linked to the student."""
    link_id: uuid.UUID
    parent_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    relationship: str | None = None
    linked_at: datetime


class LinkedParentsListResponse(BaseModel):
    """List of parents linked to a student."""
    parents: list[LinkedParentResponse]


class LinkedChildResponse(BaseModel):
    """A child linked to the parent."""
    link_id: uuid.UUID
    student_id: uuid.UUID
    first_name: str
    last_name: str
    age: int | None = None
    wellness_score: float | None = None
    risk_level: str = "green"
    relationship: str | None = None
    linked_at: datetime


class LinkedChildrenListResponse(BaseModel):
    """List of children linked to a parent."""
    children: list[LinkedChildResponse]


# -------------------------------------------------------------------
# Guardians (student-managed)
# -------------------------------------------------------------------

_GUARDIAN_REL = r"^(mother|father|guardian|grandparent|sibling|other)$"


class GuardianCreate(BaseModel):
    """Student adds a guardian record."""
    name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    relationship: str = Field(..., pattern=_GUARDIAN_REL)
    is_primary: bool = False


class GuardianUpdate(BaseModel):
    """Edit a guardian record (all fields optional)."""
    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    relationship: str | None = Field(None, pattern=_GUARDIAN_REL)
    is_primary: bool | None = None


class GuardianResponse(BaseModel):
    """A guardian record with its active invite code (if any)."""
    guardian_id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    relationship: str
    is_primary: bool
    status: str
    invite_code: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardianListResponse(BaseModel):
    guardians: list[GuardianResponse]
