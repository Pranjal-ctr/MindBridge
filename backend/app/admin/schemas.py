"""
MindBridge Admin Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


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
# Tenant Detail / Subscriptions (super-admin school management)
# -------------------------------------------------------------------

class TenantStats(BaseModel):
    """Per-role user counts and seat usage for a tenant."""
    students: int = 0
    parents: int = 0
    counselors: int = 0
    school_admins: int = 0
    seats_used: int = 0
    seat_limit: int = 0


class SubscriptionCreate(BaseModel):
    """Create/replace a tenant's subscription."""
    plan_name: str = Field(..., pattern=r"^(free|starter|professional|enterprise)$")
    student_limit: int = Field(..., ge=1)
    billing_cycle: str = Field(default="annual", pattern=r"^(monthly|quarterly|annual)$")
    amount: float = Field(..., ge=0)
    start_date: date
    renewal_date: date | None = None


class SubscriptionResponse(BaseModel):
    subscription_id: uuid.UUID
    tenant_id: uuid.UUID
    plan_name: str
    student_limit: int
    billing_cycle: str
    amount: float
    start_date: date
    renewal_date: date | None = None
    status: str

    model_config = {"from_attributes": True}


class TenantDetailResponse(TenantResponse):
    """Tenant with usage stats and active subscription."""
    stats: TenantStats = Field(default_factory=TenantStats)
    subscription: SubscriptionResponse | None = None


# -------------------------------------------------------------------
# Break-Glass Chat Access (severe cases only, always audit-logged)
# -------------------------------------------------------------------

class BreakGlassConversation(BaseModel):
    conversation_id: uuid.UUID
    title: str | None = None
    total_messages: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class BreakGlassConversationList(BaseModel):
    student_id: uuid.UUID
    student_name: str
    conversations: list[BreakGlassConversation]


class BreakGlassMessage(BaseModel):
    message_id: uuid.UUID
    sender_type: str
    message_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BreakGlassMessageList(BaseModel):
    conversation_id: uuid.UUID
    messages: list[BreakGlassMessage]


# -------------------------------------------------------------------
# Staff Users (counselor / school_admin provisioning)
# -------------------------------------------------------------------

class StaffUserCreate(BaseModel):
    """Platform admin creates a counselor or school_admin account for a tenant.
    Staff roles cannot self-register via /auth/signup."""
    tenant_id: uuid.UUID
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern=r"^(counselor|school_admin)$")
    phone: str | None = Field(None, max_length=20)


class StaffUserResponse(BaseModel):
    """Created staff user."""
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    first_name: str
    last_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
# AI Playground
# -------------------------------------------------------------------

class PlaygroundVariant(BaseModel):
    """One model + prompt combination to test."""
    provider: str = Field(default="gemini", max_length=50)
    model: str = Field(..., max_length=100)
    prompt_version_id: uuid.UUID | None = Field(
        None, description="Use this stored prompt version as the system prompt"
    )
    prompt_override: str | None = Field(
        None, max_length=20000, description="Raw system prompt (takes precedence over prompt_version_id)"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class PlaygroundRequest(BaseModel):
    """Run a test message against one or more model/prompt variants."""
    message: str = Field(..., min_length=1, max_length=4000)
    variants: list[PlaygroundVariant] = Field(..., min_length=1, max_length=3)


class PlaygroundVariantResult(BaseModel):
    """Result of a single playground variant run."""
    provider: str
    model: str
    prompt_version: str | None = None
    text: str | None = None
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error: str | None = None


class PlaygroundResponse(BaseModel):
    results: list[PlaygroundVariantResult]


class ProviderConfigResponse(BaseModel):
    """Registered AI provider."""
    provider_name: str
    display_name: str
    is_enabled: bool
    default_model: str

    model_config = {"from_attributes": True}


class ProviderListResponse(BaseModel):
    providers: list[ProviderConfigResponse]


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
