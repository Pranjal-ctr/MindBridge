"""
MindBridge Users Schemas
Pydantic v2 models for user profile management.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserUpdate(BaseModel):
    """Updatable user fields."""
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    profile_image: str | None = None


class UserProfileResponse(BaseModel):
    """Full user profile with role-specific data."""
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
    updated_at: datetime

    # Role-specific profile (populated based on role)
    student_profile: StudentProfileData | None = None
    parent_profile: ParentProfileData | None = None
    counselor_profile: CounselorProfileData | None = None
    school_admin_profile: SchoolAdminProfileData | None = None

    model_config = {"from_attributes": True}


class StudentProfileData(BaseModel):
    """Student-specific profile data."""
    student_id: uuid.UUID
    admission_number: str | None = None
    age: int | None = None
    gender: str | None = None
    wellness_score: float | None = None
    risk_level: str = "green"

    model_config = {"from_attributes": True}


class ParentProfileData(BaseModel):
    """Parent-specific profile data."""
    parent_id: uuid.UUID
    occupation: str | None = None
    relationship_type: str | None = None

    model_config = {"from_attributes": True}


class CounselorProfileData(BaseModel):
    """Counselor-specific profile data."""
    counselor_id: uuid.UUID
    specialization: str | None = None
    experience_years: int | None = None
    license_number: str | None = None
    rating: float | None = None
    bio: str | None = None

    model_config = {"from_attributes": True}


class SchoolAdminProfileData(BaseModel):
    """School admin-specific profile data."""
    admin_id: uuid.UUID
    designation: str | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated user list."""
    users: list[UserProfileResponse]
    total: int
    page: int
    page_size: int
