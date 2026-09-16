"""
Kio Admin Router
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_role
from app.admin.schemas import (
    AdminRiskDetail,
    AdminRiskListResponse,
    AdminUserListResponse,
    AIConfigResponse,
    AIConfigUpdate,
    AIRouteListResponse,
    AIRouteResponse,
    AIRouteUpdate,
    AuditLogListResponse,
    PlatformConfigListResponse,
    PlatformConfigResponse,
    PlatformConfigUpdate,
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
from app.audit import log_audit
from app.audit_actions import AuditAction, AuditEntity, AuditSeverity
from app.admin.service import (
    get_ai_config,
    update_ai_config,
    activate_prompt,
    get_admin_risk_detail,
    list_admin_risk,
    break_glass_get_messages,
    break_glass_list_conversations,
    create_counselor,
    create_prompt,
    create_staff_user,
    create_tenant,
    delete_tenant,
    AUDIT_EXPORT_MAX_ROWS,
    iter_audit_logs_csv,
    get_platform_analytics,
    get_platform_config,
    get_tenant_detail,
    list_ai_routes,
    list_all_users,
    list_audit_logs,
    list_counselors,
    list_platform_config,
    list_prompts,
    list_provider_configs,
    list_tenants,
    run_playground,
    set_tenant_subscription,
    soft_delete_user,
    update_ai_route,
    update_platform_config,
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
async def get_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    status: str | None = Query(None, pattern=r"^(active|inactive|suspended|trial|archived)$"),
    include_archived: bool = Query(False),
):
    """List schools with search/status filters. Platform admin only."""
    tenants, total = await list_tenants(
        db, page, page_size,
        search=search, status_filter=status,
        include_archived=include_archived or status == "archived",
    )
    return TenantListResponse(tenants=tenants, total=total, page=page, page_size=page_size)


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=201,
)
async def create_new_tenant(
    payload: TenantCreate,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new tenant (school/organization). Platform admin only."""
    return await create_tenant(db, payload, admin_user.user_id, request)


@router.put(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
)
async def update_tenant_endpoint(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a tenant (incl. suspend/activate via status). Platform admin only."""
    return await update_tenant(db, tenant_id, payload, admin_user.user_id, request)


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
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query(..., min_length=10, max_length=500,
                        description="Why this access is needed (recorded in the audit log)"),
):
    """
    BREAK-GLASS: list a student's private conversations for crisis review.
    Platform admin only. Every call is audit-logged with the stated reason.
    """
    return await break_glass_list_conversations(
        db, admin_user.user_id, student_id, reason, request=request
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=BreakGlassMessageList,
)
async def break_glass_messages(
    conversation_id: uuid.UUID,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query(..., min_length=10, max_length=500,
                        description="Why this access is needed (recorded in the audit log)"),
):
    """
    BREAK-GLASS: read a student conversation transcript for crisis review.
    Platform admin only. Every call is audit-logged with the stated reason.
    """
    return await break_glass_get_messages(
        db, admin_user.user_id, conversation_id, reason, request=request
    )


@router.delete(
    "/tenants/{tenant_id}",
    status_code=204,
)
async def remove_tenant(
    tenant_id: uuid.UUID,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Archive (soft-delete) a school. Data is retained; access is blocked.
    Platform admin only."""
    await delete_tenant(db, tenant_id, admin_user.user_id, request)


# -------------------------------------------------------------------
# Staff Users
# -------------------------------------------------------------------

@router.get(
    "/users",
    response_model=AdminUserListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_all_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = Query(None, pattern=r"^(student|parent|counselor|school_admin|admin)$"),
    search: str | None = Query(None, max_length=255),
    tenant_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None, pattern=r"^(active|inactive|deleted)$"),
):
    """Cross-tenant user list with role/school/status filters and name/email search.
    Includes suspended and soft-deleted users. Platform admin only."""
    users, total = await list_all_users(
        db, page, page_size,
        role=role, search=search, tenant_id=tenant_id, status_filter=status,
    )
    return AdminUserListResponse(users=users, total=total, page=page, page_size=page_size)


@router.post(
    "/users",
    response_model=StaffUserResponse,
    status_code=201,
)
async def create_staff_account(
    payload: StaffUserCreate,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a counselor or school_admin account for a tenant. Platform admin only.
    Staff roles cannot self-register via /auth/signup."""
    return await create_staff_user(db, payload, admin_user.user_id, request)


@router.patch(
    "/users/{user_id}",
    response_model=StaffUserResponse,
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Disable/enable a user, reset their password, or edit profile basics.
    Platform admin only."""
    return await update_user_admin(db, user_id, payload, admin_user.user_id, request)


@router.delete(
    "/users/{user_id}",
    status_code=204,
)
async def remove_user(
    user_id: uuid.UUID,
    admin_user: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft-delete a user (blocks login, keeps the record). Platform admin only."""
    await soft_delete_user(db, user_id, admin_user.user_id, request)


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
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a platform counselor. Platform admin only."""
    return await create_counselor(db, payload, actor_id=admin.user_id, request=request)


@router.patch(
    "/counselors/{counselor_id}",
    response_model=CounselorAdminResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def edit_counselor(
    counselor_id: uuid.UUID,
    payload: CounselorAdminUpdate,
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Edit a counselor: profile, verify credentials, activate/deactivate, availability."""
    return await update_counselor(
        db, counselor_id, payload, actor_id=admin.user_id, request=request
    )


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
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change the model routing for one AI feature (a deliberate override).

    This endpoint predates the platform configuration and is kept: running risk
    detection on a different model than chat is a real need. It now validates
    against the same registry, because it previously accepted arbitrary
    provider and model strings -- which meant a typo here could point a
    safety-critical feature at a model that does not exist, and the failure
    would only appear the next time a student said something concerning.
    """
    return await update_ai_route(
        db, feature_name, payload, actor_id=admin.user_id, request=request
    )


@router.get(
    "/ai/config",
    response_model=AIConfigResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def read_ai_config(db: Annotated[AsyncSession, Depends(get_db)]):
    """The active platform AI configuration, the selectable registry, and health.

    Platform admin only. Returns credential *availability* as a boolean per
    provider and never any part of a key.
    """
    return await get_ai_config(db)


@router.put(
    "/ai/config",
    response_model=AIConfigResponse,
)
async def write_ai_config(
    payload: AIConfigUpdate,
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change which supported provider/model serves every AI feature.

    Platform admin only. Rejected with 422 (and nothing written) unless the
    provider and model are both in the backend registry and the provider's API
    key is present on this server, so a valid configuration can never be
    replaced by an unusable one.

    Takes effect for new AI requests immediately -- no restart, no deploy. It
    is not an authentication change: no session, token, or user record is read
    or written on this path, and requests already in flight keep the provider
    they started with.
    """
    return await update_ai_config(db, payload, admin.user_id, request=request)


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
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Activate a prompt version globally; deactivates other versions of the same prompt."""
    return await activate_prompt(db, prompt_id, actor_id=admin.user_id, request=request)


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
# Platform Config (intelligence-layer weights & thresholds)
# -------------------------------------------------------------------

@router.get(
    "/config",
    response_model=PlatformConfigListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_all_platform_config(db: Annotated[AsyncSession, Depends(get_db)]):
    """All intelligence-layer config keys with their effective values."""
    return await list_platform_config(db)


@router.get(
    "/config/{config_key}",
    response_model=PlatformConfigResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_one_platform_config(
    config_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """One config key's effective (DB-merged or default) value."""
    return await get_platform_config(db, config_key)


@router.put(
    "/config/{config_key}",
    response_model=PlatformConfigResponse,
)
async def put_platform_config(
    config_key: str,
    payload: PlatformConfigUpdate,
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a config value (wellness weights, risk bands, crisis thresholds, ...)."""
    return await update_platform_config(
        db, config_key, payload, admin.user_id, request=request
    )


# -------------------------------------------------------------------
# Audit Logs
# -------------------------------------------------------------------

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
)
async def get_audit_logs(
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100, description="Action prefix match"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    tenant_id: uuid.UUID | None = Query(None, description="School scope"),
    actor_role: str | None = Query(None, max_length=50),
    entity_type: str | None = Query(None, max_length=50),
    result: str | None = Query(None, max_length=20),
    severity: str | None = Query(None, max_length=20),
    request_id: str | None = Query(
        None, max_length=64,
        description="Correlation id -- joins this event to its application logs",
    ),
):
    """View the audit trail. Platform admin only.

    Reading the audit trail is itself audited. Someone who can see every
    sensitive action on the platform is exercising real power, and a log that
    does not record its own readers has a hole exactly where it matters.
    """
    logs, total = await list_audit_logs(
        db, page, page_size,
        user_id=user_id, action=action, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, actor_role=actor_role, entity_type=entity_type,
        result=result, severity=severity, request_id=request_id,
    )
    await log_audit(
        db,
        user_id=admin.user_id,
        action=AuditAction.AUDIT_LOG_VIEWED,
        entity_type=AuditEntity.AUDIT_LOG,
        # The filters, not the rows. This says what was looked for without
        # copying the results back into the table and doubling it every read.
        details={
            "page": page,
            "page_size": page_size,
            "result_count": len(logs),
            "filters": {
                k: str(v) for k, v in {
                    "user_id": user_id, "action": action,
                    "date_from": date_from, "date_to": date_to,
                    "tenant_id": tenant_id, "actor_role": actor_role,
                    "entity_type": entity_type, "result": result,
                    "severity": severity, "request_id": request_id,
                }.items() if v is not None
            },
        },
        request=request,
        actor=admin,
        severity=AuditSeverity.NOTICE,
    )
    return AuditLogListResponse(logs=logs, total=total)


@router.get("/audit-logs/export")
async def export_audit_logs(
    admin: AdminUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100, description="Action prefix match"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    tenant_id: uuid.UUID | None = Query(None, description="School scope"),
    actor_role: str | None = Query(None, max_length=50),
    entity_type: str | None = Query(None, max_length=50),
    result: str | None = Query(None, max_length=20),
    severity: str | None = Query(None, max_length=20),
    request_id: str | None = Query(None, max_length=64),
):
    """Export the filtered audit log as CSV. Platform admin only.

    Read-only, and capped at AUDIT_EXPORT_MAX_ROWS. The export event is
    written and committed *before* a single byte is streamed: the response
    body is produced lazily after the endpoint returns, so a row written
    alongside it would be committed only if the download completed. Taking a
    copy of the audit trail off the platform is precisely the act that must be
    recorded whether or not it finished.
    """
    filters = dict(
        user_id=user_id, action=action, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, actor_role=actor_role, entity_type=entity_type,
        result=result, severity=severity, request_id=request_id,
    )

    await log_audit(
        db,
        user_id=admin.user_id,
        action=AuditAction.AUDIT_LOG_EXPORTED,
        entity_type=AuditEntity.AUDIT_LOG,
        details={
            "max_rows": AUDIT_EXPORT_MAX_ROWS,
            "filters": {k: str(v) for k, v in filters.items() if v is not None},
        },
        request=request,
        actor=admin,
        # An export leaves the platform and cannot be recalled.
        severity=AuditSeverity.WARNING,
    )
    await db.commit()

    filename = (
        "kio-audit-logs-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}Z.csv"
    )
    return StreamingResponse(
        # No `db`: the generator opens its own session, because FastAPI has
        # already closed this one by the time the body streams.
        iter_audit_logs_csv(**filters),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Max-Rows": str(AUDIT_EXPORT_MAX_ROWS),
        },
    )


# -------------------------------------------------------------------
# Cross-tenant risk oversight
# -------------------------------------------------------------------
# /risk/queue is tenant-scoped to the caller, so a platform admin hitting it
# sees their own (empty) queue. These give the across-schools view instead.
# Read-only: recording a verdict stays with the counselor who owns the case.

@router.get(
    "/risk",
    response_model=AdminRiskListResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_admin_risk_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    review_status: str | None = Query(None, max_length=20),
    risk_level: str | None = Query(None, max_length=20),
    tenant_id: uuid.UUID | None = Query(None),
):
    """Risk assessments across every school, most severe then oldest first."""
    items, total = await list_admin_risk(
        db, page, page_size,
        review_status=review_status, risk_level=risk_level, tenant_id=tenant_id,
    )
    return AdminRiskListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/risk/{risk_id}",
    response_model=AdminRiskDetail,
    dependencies=[Depends(require_role("admin"))],
)
async def get_admin_risk(
    risk_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """One assessment in full, including the counselor's recorded verdict."""
    return await get_admin_risk_detail(db, risk_id)
