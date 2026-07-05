"""
MindBridge Admin Service
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import (
    AuditLogResponse,
    PromptCreate,
    PromptResponse,
    StaffUserCreate,
    StaffUserResponse,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)
from database.models import AIPromptVersion, AuditLog, Tenant, User


# -------------------------------------------------------------------
# Tenants
# -------------------------------------------------------------------

async def list_tenants(db: AsyncSession) -> tuple[list[TenantResponse], int]:
    """List all tenants (admin only)."""
    count_result = await db.execute(select(func.count()).select_from(Tenant))
    total = count_result.scalar() or 0

    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()

    return [TenantResponse.model_validate(t) for t in tenants], total


async def create_tenant(db: AsyncSession, payload: TenantCreate) -> TenantResponse:
    """Create a new tenant."""
    # Check for duplicate school code
    if payload.school_code:
        existing = await db.execute(
            select(Tenant).where(Tenant.school_code == payload.school_code)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"School code '{payload.school_code}' already exists",
            )

    tenant = Tenant(
        tenant_name=payload.tenant_name,
        tenant_type=payload.tenant_type,
        school_code=payload.school_code,
        subscription_plan=payload.subscription_plan,
        student_limit=payload.student_limit,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


async def update_tenant(
    db: AsyncSession, tenant_id: uuid.UUID, payload: TenantUpdate
) -> TenantResponse:
    """Update tenant details."""
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.flush()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


# -------------------------------------------------------------------
# Staff Users
# -------------------------------------------------------------------

async def create_staff_user(db: AsyncSession, payload: StaffUserCreate) -> StaffUserResponse:
    """Create a counselor or school_admin account. Platform admin only."""
    from app.auth.service import _create_role_profile
    from app.auth.utils import hash_password

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == payload.tenant_id)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        user_id=uuid.uuid4(),
        tenant_id=payload.tenant_id,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await _create_role_profile(db, user)

    return StaffUserResponse.model_validate(user)


# -------------------------------------------------------------------
# AI Prompts
# -------------------------------------------------------------------

async def list_prompts(db: AsyncSession) -> list[PromptResponse]:
    """List all AI prompt versions."""
    result = await db.execute(
        select(AIPromptVersion).order_by(AIPromptVersion.created_at.desc())
    )
    prompts = result.scalars().all()
    return [PromptResponse.model_validate(p) for p in prompts]


async def create_prompt(db: AsyncSession, payload: PromptCreate) -> PromptResponse:
    """Create a new AI prompt version."""
    prompt = AIPromptVersion(
        prompt_name=payload.prompt_name,
        prompt_version=payload.prompt_version,
        prompt_content=payload.prompt_content,
        is_active=payload.is_active,
    )
    db.add(prompt)
    await db.flush()
    await db.refresh(prompt)
    return PromptResponse.model_validate(prompt)


# -------------------------------------------------------------------
# Audit Logs
# -------------------------------------------------------------------

async def list_audit_logs(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> tuple[list[AuditLogResponse], int]:
    """List audit logs (admin only)."""
    count_result = await db.execute(select(func.count()).select_from(AuditLog))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    return [AuditLogResponse.model_validate(log) for log in logs], total
