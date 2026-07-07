"""
MindBridge Admin Service
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import (
    AIRouteListResponse,
    AIRouteResponse,
    AIRouteUpdate,
    AuditLogResponse,
    BreakGlassConversation,
    BreakGlassConversationList,
    BreakGlassMessage,
    BreakGlassMessageList,
    CounselorAdminResponse,
    CounselorAdminUpdate,
    CounselorCreate,
    CounselorListResponse,
    PlatformAnalytics,
    PlatformConfigListResponse,
    PlatformConfigResponse,
    PlatformConfigUpdate,
    PlaygroundRequest,
    PlaygroundVariantResult,
    PromptCreate,
    PromptResponse,
    ProviderConfigResponse,
    StaffUserCreate,
    StaffUserResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    TenantCreate,
    TenantDetailResponse,
    TenantResponse,
    TenantStats,
    TenantUpdate,
    UserAdminUpdate,
)
from database.models import (
    AIFeatureRoute,
    AIPromptVersion,
    AIProviderConfig,
    AIUsageLog,
    AuditLog,
    Conversation,
    CounselorProfile,
    Message,
    ParentProfile,
    PlatformConfig,
    StudentProfile,
    Subscription,
    Tenant,
    User,
)


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


async def get_tenant_detail(db: AsyncSession, tenant_id: uuid.UUID) -> TenantDetailResponse:
    """Tenant with per-role user counts, seat usage, and active subscription."""
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    counts_result = await db.execute(
        select(User.role, func.count())
        .where(User.tenant_id == tenant_id, User.is_active == True)  # noqa: E712
        .group_by(User.role)
    )
    counts = dict(counts_result.all())

    sub_result = await db.execute(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = sub_result.scalar_one_or_none()

    detail = TenantDetailResponse.model_validate(tenant)
    detail.stats = TenantStats(
        students=counts.get("student", 0),
        parents=counts.get("parent", 0),
        counselors=counts.get("counselor", 0),
        school_admins=counts.get("school_admin", 0),
        seats_used=counts.get("student", 0),
        seat_limit=tenant.student_limit,
    )
    detail.subscription = (
        SubscriptionResponse.model_validate(subscription) if subscription else None
    )
    return detail


async def set_tenant_subscription(
    db: AsyncSession, tenant_id: uuid.UUID, payload: SubscriptionCreate
) -> SubscriptionResponse:
    """Create a new active subscription for a tenant; supersedes any existing one.
    Also syncs the tenant's plan and seat limit used for signup enforcement."""
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    existing = await db.execute(
        select(Subscription).where(
            Subscription.tenant_id == tenant_id, Subscription.status == "active"
        )
    )
    for old in existing.scalars().all():
        old.status = "cancelled"

    subscription = Subscription(
        tenant_id=tenant_id,
        plan_name=payload.plan_name,
        student_limit=payload.student_limit,
        billing_cycle=payload.billing_cycle,
        amount=payload.amount,
        start_date=payload.start_date,
        renewal_date=payload.renewal_date,
        status="active",
    )
    db.add(subscription)

    tenant.subscription_plan = payload.plan_name
    tenant.student_limit = payload.student_limit

    await db.flush()
    await db.refresh(subscription)
    return SubscriptionResponse.model_validate(subscription)


# -------------------------------------------------------------------
# Break-Glass Chat Access (severe cases only, always audit-logged)
# -------------------------------------------------------------------

async def _log_break_glass(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    reason: str,
) -> None:
    """Every break-glass access writes an audit row; the reason is part of the action."""
    db.add(AuditLog(
        audit_id=uuid.uuid4(),
        user_id=admin_user_id,
        action=f"break_glass_chat_access: {reason[:80]}",
        entity_type=entity_type,
        entity_id=entity_id,
    ))
    await db.flush()


async def break_glass_list_conversations(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
    student_id: uuid.UUID,
    reason: str,
) -> BreakGlassConversationList:
    """List a student's conversations for crisis review. Audit-logged."""
    result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.student_id == student_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    student, student_user = row

    await _log_break_glass(db, admin_user_id, "student", student_id, reason)

    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.student_id == student_id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = conv_result.scalars().all()

    return BreakGlassConversationList(
        student_id=student_id,
        student_name=f"{student_user.first_name} {student_user.last_name}",
        conversations=[BreakGlassConversation.model_validate(c) for c in conversations],
    )


async def break_glass_get_messages(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    reason: str,
) -> BreakGlassMessageList:
    """Read a conversation transcript for crisis review. Audit-logged."""
    conv_result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == conversation_id)
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await _log_break_glass(db, admin_user_id, "conversation", conversation_id, reason)

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return BreakGlassMessageList(
        conversation_id=conversation_id,
        messages=[BreakGlassMessage.model_validate(m) for m in messages],
    )


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
# User administration
# -------------------------------------------------------------------

async def update_user_admin(
    db: AsyncSession, user_id: uuid.UUID, payload: UserAdminUpdate
) -> StaffUserResponse:
    """Toggle active status and/or reset password for any user. Platform admin only."""
    from app.auth.utils import hash_password

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.new_password:
        user.password_hash = hash_password(payload.new_password)

    await db.flush()
    await db.refresh(user)
    return StaffUserResponse.model_validate(user)


async def delete_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Delete a school/tenant (cascades to its users and data)."""
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await db.delete(tenant)
    await db.flush()


# -------------------------------------------------------------------
# Counselor administration (platform-wide)
# -------------------------------------------------------------------

async def _get_or_create_platform_tenant(db: AsyncSession) -> Tenant:
    """Counselors belong to the MindBridge platform tenant, not a school."""
    result = await db.execute(select(Tenant).where(Tenant.school_code == "PLATFORM"))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="MindBridge Platform",
            tenant_type="organization",
            school_code="PLATFORM",
            status="active",
        )
        db.add(tenant)
        await db.flush()
    return tenant


def _counselor_to_admin_response(
    counselor: CounselorProfile, user: User
) -> CounselorAdminResponse:
    return CounselorAdminResponse(
        counselor_id=counselor.counselor_id,
        user_id=user.user_id,
        name=f"{user.first_name} {user.last_name}",
        email=user.email,
        phone=user.phone,
        bio=counselor.bio,
        qualification=counselor.qualification,
        specializations=counselor.specializations or [],
        languages=counselor.languages or [],
        experience_years=counselor.experience_years,
        rating=float(counselor.rating) if counselor.rating is not None else None,
        is_verified=counselor.is_verified,
        is_available=counselor.is_available,
        is_active=user.is_active,
    )


async def create_counselor(db: AsyncSession, payload: CounselorCreate) -> CounselorAdminResponse:
    """Register a platform counselor (user under the platform tenant + profile)."""
    from app.auth.utils import hash_password

    tenant = await _get_or_create_platform_tenant(db)

    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=email,
        password_hash=hash_password(payload.password),
        role="counselor",
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    counselor = CounselorProfile(
        counselor_id=uuid.uuid4(),
        user_id=user.user_id,
        bio=payload.bio,
        qualification=payload.qualification,
        specializations=payload.specializations,
        languages=payload.languages,
        experience_years=payload.experience_years,
        is_verified=payload.is_verified,
        is_available=True,
    )
    db.add(counselor)
    await db.flush()
    return _counselor_to_admin_response(counselor, user)


async def list_counselors(db: AsyncSession) -> CounselorListResponse:
    """List all platform counselors (verified or not) for management."""
    result = await db.execute(
        select(CounselorProfile, User)
        .join(User, CounselorProfile.user_id == User.user_id)
        .order_by(User.last_name.asc())
    )
    rows = result.all()
    items = [_counselor_to_admin_response(c, u) for c, u in rows]
    return CounselorListResponse(counselors=items, total=len(items))


async def update_counselor(
    db: AsyncSession, counselor_id: uuid.UUID, payload: CounselorAdminUpdate
) -> CounselorAdminResponse:
    """Edit a counselor's profile, verification, availability, or active status."""
    result = await db.execute(
        select(CounselorProfile, User)
        .join(User, CounselorProfile.user_id == User.user_id)
        .where(CounselorProfile.counselor_id == counselor_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counselor not found")
    counselor, user = row

    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data:
        user.is_active = data.pop("is_active")
    for field, value in data.items():
        setattr(counselor, field, value)

    await db.flush()
    await db.refresh(counselor)
    await db.refresh(user)
    return _counselor_to_admin_response(counselor, user)


# -------------------------------------------------------------------
# AI Settings (feature -> model routing)
# -------------------------------------------------------------------

async def list_ai_routes(db: AsyncSession) -> AIRouteListResponse:
    """List all AI feature routes (chat, memory, title, risk, parent insight, ...)."""
    result = await db.execute(select(AIFeatureRoute).order_by(AIFeatureRoute.feature_name))
    routes = result.scalars().all()
    return AIRouteListResponse(routes=[AIRouteResponse.model_validate(r) for r in routes])


async def update_ai_route(
    db: AsyncSession, feature_name: str, payload: AIRouteUpdate
) -> AIRouteResponse:
    """Update the model routing for a feature (primary/fallback provider + model)."""
    result = await db.execute(
        select(AIFeatureRoute).where(AIFeatureRoute.feature_name == feature_name)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature route not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(route, field, value)

    await db.flush()
    await db.refresh(route)
    return AIRouteResponse.model_validate(route)


# -------------------------------------------------------------------
# Platform Analytics
# -------------------------------------------------------------------

async def get_platform_analytics(db: AsyncSession) -> PlatformAnalytics:
    """Cross-tenant platform KPIs."""
    from datetime import datetime, timedelta, timezone

    async def _count(query) -> int:
        return (await db.execute(query)).scalar() or 0

    total_schools = await _count(
        select(func.count()).select_from(Tenant).where(Tenant.tenant_type == "school")
    )
    total_students = await _count(
        select(func.count()).select_from(User).where(User.role == "student", User.is_active == True)  # noqa: E712
    )
    total_parents = await _count(
        select(func.count()).select_from(User).where(User.role == "parent", User.is_active == True)  # noqa: E712
    )
    total_counselors = await _count(
        select(func.count()).select_from(User).where(User.role == "counselor", User.is_active == True)  # noqa: E712
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    active_users = await _count(
        select(func.count()).select_from(User).where(User.last_login >= cutoff)
    )

    ai_requests = await _count(select(func.count()).select_from(AIUsageLog))
    ai_cost = (await db.execute(
        select(func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0))
    )).scalar() or 0
    conversation_count = await _count(select(func.count()).select_from(Conversation))
    revenue = (await db.execute(
        select(func.coalesce(func.sum(Subscription.amount), 0)).where(Subscription.status == "active")
    )).scalar() or 0

    return PlatformAnalytics(
        total_schools=total_schools,
        total_students=total_students,
        total_parents=total_parents,
        total_counselors=total_counselors,
        active_users=active_users,
        ai_requests=ai_requests,
        ai_cost_usd=float(ai_cost),
        conversation_count=conversation_count,
        revenue_usd=float(revenue),
    )


# -------------------------------------------------------------------
# AI Playground
# -------------------------------------------------------------------

async def activate_prompt(db: AsyncSession, prompt_id: uuid.UUID) -> PromptResponse:
    """Activate one prompt version and deactivate all other versions of the same prompt."""
    result = await db.execute(
        select(AIPromptVersion).where(AIPromptVersion.prompt_id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found")

    siblings = await db.execute(
        select(AIPromptVersion).where(AIPromptVersion.prompt_name == prompt.prompt_name)
    )
    for sibling in siblings.scalars().all():
        sibling.is_active = sibling.prompt_id == prompt_id

    await db.flush()
    await db.refresh(prompt)
    return PromptResponse.model_validate(prompt)


async def list_provider_configs(db: AsyncSession) -> list[ProviderConfigResponse]:
    """List registered AI providers."""
    result = await db.execute(
        select(AIProviderConfig).order_by(AIProviderConfig.provider_name)
    )
    return [ProviderConfigResponse.model_validate(p) for p in result.scalars().all()]


async def run_playground(db: AsyncSession, payload: PlaygroundRequest) -> list[PlaygroundVariantResult]:
    """
    Run a test message against up to 3 model/prompt variants and compare.

    Calls providers directly (bypassing feature routes) so admins can test
    combinations before activating them globally. Every call is usage-logged
    under feature_name='playground'.
    """
    import asyncio
    import time

    from app.ai import factory
    from app.ai.pricing import estimate_cost_usd
    from app.ai.prompts import COMRADE_PROMPT_VERSION, COMRADE_SYSTEM_PROMPT
    from app.ai.usage import log_usage

    # Resolve system prompts up front (needs the shared db session)
    resolved: list[tuple[str, str]] = []  # (system_prompt, prompt_version_label)
    for variant in payload.variants:
        if variant.prompt_override:
            resolved.append((variant.prompt_override, "override"))
        elif variant.prompt_version_id:
            result = await db.execute(
                select(AIPromptVersion).where(AIPromptVersion.prompt_id == variant.prompt_version_id)
            )
            prompt = result.scalar_one_or_none()
            if not prompt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prompt version {variant.prompt_version_id} not found",
                )
            resolved.append((prompt.prompt_content, prompt.prompt_version))
        else:
            resolved.append((COMRADE_SYSTEM_PROMPT, COMRADE_PROMPT_VERSION))

    contents = [{"role": "user", "parts": [{"text": payload.message}]}]

    async def run_variant(variant, system_prompt):
        start = time.monotonic()
        try:
            provider = factory.get_provider(variant.provider)
            response = await provider.generate(
                model=variant.model,
                system_prompt=system_prompt,
                contents=contents,
                temperature=variant.temperature,
                max_output_tokens=1024,
            )
            return response, int((time.monotonic() - start) * 1000), None
        except Exception as e:
            return None, int((time.monotonic() - start) * 1000), str(e)

    outcomes = await asyncio.gather(*(
        run_variant(v, sp) for v, (sp, _) in zip(payload.variants, resolved)
    ))

    # Usage logging is sequential -- one AsyncSession cannot take concurrent writes
    results = []
    for variant, (_, version_label), (response, latency_ms, error) in zip(
        payload.variants, resolved, outcomes
    ):
        await log_usage(
            db,
            feature_name="playground",
            provider=variant.provider,
            model=variant.model,
            latency_ms=latency_ms,
            input_tokens=response.input_tokens if response else None,
            output_tokens=response.output_tokens if response else None,
            success=error is None,
            error_message=error,
        )
        results.append(PlaygroundVariantResult(
            provider=variant.provider,
            model=variant.model,
            prompt_version=version_label,
            text=response.text if response else None,
            latency_ms=latency_ms,
            input_tokens=response.input_tokens if response else None,
            output_tokens=response.output_tokens if response else None,
            estimated_cost_usd=float(estimate_cost_usd(
                variant.provider, variant.model,
                response.input_tokens if response else None,
                response.output_tokens if response else None,
            )) if response else None,
            error=error,
        ))

    return results


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


# -------------------------------------------------------------------
# Platform Config (intelligence-layer weights & thresholds)
# -------------------------------------------------------------------

async def list_platform_config(db: AsyncSession) -> PlatformConfigListResponse:
    """All known config keys with effective (DB-merged or default) values."""
    from app.intelligence.config import DEFAULTS, load_config

    result = await db.execute(select(PlatformConfig))
    db_keys = {row.config_key for row in result.scalars().all()}

    configs = []
    for key in DEFAULTS:
        configs.append(PlatformConfigResponse(
            config_key=key,
            config_value=await load_config(db, key),
            description=None,
            source="database" if key in db_keys else "default",
        ))
    return PlatformConfigListResponse(configs=configs)


async def get_platform_config(db: AsyncSession, config_key: str) -> PlatformConfigResponse:
    """One config key's effective value."""
    from app.intelligence.config import DEFAULTS, load_config

    if config_key not in DEFAULTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown config key")

    result = await db.execute(
        select(PlatformConfig).where(PlatformConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    return PlatformConfigResponse(
        config_key=config_key,
        config_value=await load_config(db, config_key),
        description=row.description if row else None,
        source="database" if row else "default",
    )


async def update_platform_config(
    db: AsyncSession, config_key: str, payload: PlatformConfigUpdate, admin_user_id: uuid.UUID
) -> PlatformConfigResponse:
    """Upsert a config value (known keys only). Audit-logged."""
    from app.intelligence.config import DEFAULTS, load_config

    if config_key not in DEFAULTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown config key")

    unknown = set(payload.config_value) - set(DEFAULTS[config_key])
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown sub-keys for {config_key}: {sorted(unknown)}",
        )

    if config_key == "wellness_weights":
        total = sum(v for v in payload.config_value.values() if isinstance(v, (int, float)))
        if not 0.99 <= total <= 1.01:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"wellness_weights must sum to 1.0 (got {total:.3f})",
            )

    result = await db.execute(
        select(PlatformConfig).where(PlatformConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PlatformConfig(config_key=config_key, config_value=payload.config_value)
        db.add(row)
    else:
        row.config_value = payload.config_value

    db.add(AuditLog(
        user_id=admin_user_id,
        action="platform_config_update",
        entity_type="platform_config",
    ))
    await db.flush()

    return PlatformConfigResponse(
        config_key=config_key,
        config_value=await load_config(db, config_key),
        description=row.description,
        source="database",
    )
