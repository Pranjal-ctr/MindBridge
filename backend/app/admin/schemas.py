"""
MindBridge Admin Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Tenants
# -------------------------------------------------------------------

class TenantCreate(BaseModel):
    """Create a new tenant."""
    tenant_name: str = Field(..., max_length=255)
    tenant_type: str = Field(default="school", pattern=r"^(school|district|organization)$")
    school_code: str | None = Field(None, max_length=50)
    subscription_plan: str = Field(default="free", pattern=r"^(free|starter|professional|enterprise)$")
    student_limit: int = Field(default=100, ge=1)


class TenantUpdate(BaseModel):
    """Update tenant fields."""
    tenant_name: str | None = Field(None, max_length=255)
    status: str | None = Field(None, pattern=r"^(active|inactive|suspended|trial)$")
    subscription_plan: str | None = None
    student_limit: int | None = Field(None, ge=1)


class TenantResponse(BaseModel):
    """Tenant response."""
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_type: str
    school_code: str | None = None
    subscription_plan: str
    student_limit: int
    active_students: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantListResponse(BaseModel):
    tenants: list[TenantResponse]
    total: int


# -------------------------------------------------------------------
# AI Prompts
# -------------------------------------------------------------------

class PromptCreate(BaseModel):
    """Create or update an AI prompt."""
    prompt_name: str = Field(..., max_length=100)
    prompt_version: str = Field(..., max_length=20)
    prompt_content: str
    is_active: bool = True


class PromptResponse(BaseModel):
    """AI prompt version response."""
    prompt_id: uuid.UUID
    prompt_name: str
    prompt_version: str
    prompt_content: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptListResponse(BaseModel):
    prompts: list[PromptResponse]


# -------------------------------------------------------------------
# Audit Logs
# -------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    audit_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
