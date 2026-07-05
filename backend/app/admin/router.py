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
    AIRouteListResponse,
    AIRouteResponse,
    AIRouteUpdate,
    AuditLogListResponse,
    BreakGlassConversationList,
    BreakGlassMessageList,
    CounselorAdminResponse,
    CounselorAdminUpdate,
    CounselorCreate,
    CounselorListResponse,
    PlatformAnalytics,
    PlaygroundRequest,
    PlaygroundResponse,
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    ProviderListResponse,
    StaffUserCreate,
    StaffUserResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    TenantCreate,
    TenantDetailResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
    UserAdminUpdate,
)
from app.admin.service import (
    activate_prompt,
    break_glass_get_messages,
    break_glass_list_conversations,
    create_counselor,
    create_prompt,
    create_staff_user,
    create_tenant,
    delete_tenant,
    get_platform_analytics,
    get_tenant_detail,
    list_ai_routes,
    list_audit_logs,
    list_counselors,
    list_prompts,
    list_provider_configs,
    list_tenants,
    run_playground,
    set_tenant_subscription,
    update_ai_route,
    update_counselor,
    update_tenant,
    update_user_admin,
)
from app.users.schemas import UserListResponse
from app.users.service import list_tenant_users
from database.models import User
from database.session import get_db

router = APIRouter()

# Authenticated platform admin (require_role returns the current user)
AdminUser = Annotated[User, Depends(require_role("admin"))]


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


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantDetailResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tenant detail: user counts, seat usage, active subscription. Platform admin only."""
    return await get_tenant_detail(db, tenant_id)


@router.get(
    "/tenants/{tenant_id}/users",
    response_model=UserListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_tenant_users(
    tenant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = Query(None, pattern=r"^(student|parent|counselor|school_admin|admin)$"),
):
    """List a tenant's users. Platform admin only."""
    users, total = await list_tenant_users(db, tenant_id, page, page_size, role)
    return UserListResponse(users=users, total=total, page=page, page_size=page_size)


@router.post(
    "/tenants/{tenant_id}/subscription",
    response_model=SubscriptionResponse,
    status_code=201,
    dependencies=[Depends(require_role("admin"))],
)
async def create_tenant_subscription(
    tenant_id: uuid.UUID,
    payload: SubscriptionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Set a tenant's subscription (plan, seats, period). Supersedes the previous one."""
    return await set_tenant_subscription(db, tenant_id, payload)


# -------------------------------------------------------------------
# Break-Glass Chat Access (severe cases only, always audit-logged)
# -------------------------------------------------------------------

@router.get(
    "/students/{student_id}/conversations",
    response_model=BreakGlassConversationList,
)
async def break_glass_conversations(
    student_id: uuid.UUID,
    admin_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query(..., min_length=10, max_length=500,
                        description="Why this access is needed (recorded in the audit log)"),
):
    """
    BREAK-GLASS: list a student's private conversations for crisis review.
    Platform admin only. Every call is audit-logged with the stated reason.
    """
    return await break_glass_list_conversations(db, admin_user.user_id, student_id, reason)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=BreakGlassMessageList,
)
async def break_glass_messages(
    conversation_id: uuid.UUID,
    admin_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query(..., min_length=10, max_length=500,
                        description="Why this access is needed (recorded in the audit log)"),
):
    """
    BREAK-GLASS: read a student conversation transcript for crisis review.
    Platform admin only. Every call is audit-logged with the stated reason.
    """
    return await break_glass_get_messages(db, admin_user.user_id, conversation_id, reason)


@router.delete(
    "/tenants/{tenant_id}",
    status_code=204,
    dependencies=[Depends(require_role("admin"))],
)
async def remove_tenant(
    tenant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a school/tenant (cascades to its users + data). Platform admin only."""
    await delete_tenant(db, tenant_id)


# -------------------------------------------------------------------
# Staff Users
# -------------------------------------------------------------------

@router.post(
    "/users",
    response_model=StaffUserResponse,
    status_code=201,
    dependencies=[Depends(require_role("admin"))],
)
async def create_staff_account(
    payload: StaffUserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a counselor or school_admin account for a tenant. Platform admin only.
    Staff roles cannot self-register via /auth/signup."""
    return await create_staff_user(db, payload)


@router.patch(
    "/users/{user_id}",
    response_model=StaffUserResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Disable/enable a user or reset their password. Platform admin only."""
    return await update_user_admin(db, user_id, payload)


# -------------------------------------------------------------------
# Counselors (platform-wide)
# -------------------------------------------------------------------

@router.get(
    "/counselors",
    response_model=CounselorListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_counselors(db: Annotated[AsyncSession, Depends(get_db)]):
    """List all platform counselors (verified or not)."""
    return await list_counselors(db)


@router.post(
    "/counselors",
    response_model=CounselorAdminResponse,
    status_code=201,
    dependencies=[Depends(require_role("admin"))],
)
async def register_counselor(
    payload: CounselorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a platform counselor. Platform admin only."""
    return await create_counselor(db, payload)


@router.patch(
    "/counselors/{counselor_id}",
    response_model=CounselorAdminResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def edit_counselor(
    counselor_id: uuid.UUID,
    payload: CounselorAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Edit a counselor: profile, verify credentials, activate/deactivate, availability."""
    return await update_counselor(db, counselor_id, payload)


# -------------------------------------------------------------------
# AI Settings (feature -> model routing)
# -------------------------------------------------------------------

@router.get(
    "/ai/routes",
    response_model=AIRouteListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_ai_routes(db: Annotated[AsyncSession, Depends(get_db)]):
    """List AI feature routes (chat, memory, title, risk, parent insight)."""
    return await list_ai_routes(db)


@router.patch(
    "/ai/routes/{feature_name}",
    response_model=AIRouteResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def patch_ai_route(
    feature_name: str,
    payload: AIRouteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change the model routing for an AI feature (primary/fallback provider + model)."""
    return await update_ai_route(db, feature_name, payload)


# -------------------------------------------------------------------
# Platform Analytics
# -------------------------------------------------------------------

@router.get(
    "/analytics/platform",
    response_model=PlatformAnalytics,
    dependencies=[Depends(require_role("admin"))],
)
async def platform_analytics(db: Annotated[AsyncSession, Depends(get_db)]):
    """Cross-tenant platform KPIs. Platform admin only."""
    return await get_platform_analytics(db)


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
# AI Playground
# -------------------------------------------------------------------

@router.patch(
    "/prompts/{prompt_id}/activate",
    response_model=PromptResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def activate_prompt_version(
    prompt_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Activate a prompt version globally; deactivates other versions of the same prompt."""
    return await activate_prompt(db, prompt_id)


@router.get(
    "/ai/providers",
    response_model=ProviderListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_ai_providers(db: Annotated[AsyncSession, Depends(get_db)]):
    """List registered AI providers and their default models."""
    providers = await list_provider_configs(db)
    return ProviderListResponse(providers=providers)


@router.post(
    "/ai/playground",
    response_model=PlaygroundResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def ai_playground(
    payload: PlaygroundRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Internal AI playground: run one test message against up to 3
    model/prompt-version variants and compare responses, latency,
    tokens, and cost -- before activating a prompt globally.
    """
    results = await run_playground(db, payload)
    return PlaygroundResponse(results=results)


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
