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
    BreakGlassConversation,
    BreakGlassConversationList,
    BreakGlassMessage,
    BreakGlassMessageList,
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
)
from database.models import (
    AIPromptVersion,
    AIProviderConfig,
    AuditLog,
    Conversation,
    Message,
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
