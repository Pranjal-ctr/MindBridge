"""
MindBridge Admin Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_role
from app.admin.schemas import (
    AuditLogListResponse,
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    TenantCreate,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from app.admin.service import (
    create_prompt,
    create_tenant,
    list_audit_logs,
    list_prompts,
    list_tenants,
    update_tenant,
)
from database.session import get_db

router = APIRouter()


# -------------------------------------------------------------------
# Tenants
# -------------------------------------------------------------------

@router.get(
    "/tenants",
    response_model=TenantListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_tenants(db: Annotated[AsyncSession, Depends(get_db)]):
    """List all tenants. Platform admin only."""
    tenants, total = await list_tenants(db)
    return TenantListResponse(tenants=tenants, total=total)


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=201,
    dependencies=[Depends(require_role("admin"))],
)
async def create_new_tenant(
    payload: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new tenant (school/organization). Platform admin only."""
    return await create_tenant(db, payload)


@router.put(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_tenant_endpoint(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a tenant. Platform admin only."""
    return await update_tenant(db, tenant_id, payload)


# -------------------------------------------------------------------
# AI Prompts
# -------------------------------------------------------------------

@router.get(
    "/prompts",
    response_model=PromptListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_prompts(db: Annotated[AsyncSession, Depends(get_db)]):
    """List AI prompt versions."""
    prompts = await list_prompts(db)
    return PromptListResponse(prompts=prompts)


@router.post(
    "/prompts",
    response_model=PromptResponse,
    status_code=201,
    dependencies=[Depends(require_role("admin"))],
)
async def create_new_prompt(
    payload: PromptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new AI prompt version."""
    return await create_prompt(db, payload)


# -------------------------------------------------------------------
# Audit Logs
# -------------------------------------------------------------------

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """View audit trail. Platform admin only."""
    logs, total = await list_audit_logs(db, page, page_size)
    return AuditLogListResponse(logs=logs, total=total)
