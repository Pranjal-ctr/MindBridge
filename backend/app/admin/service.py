"""
Kio Admin Service
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_audit
from app.admin.schemas import (
    AdminRiskDetail,
    AdminRiskRow,
    AdminUserListResponse,
    AdminUserRow,
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
    RiskAssessment,
    StudentProfile,
    Subscription,
    Tenant,
    User,
)


# -------------------------------------------------------------------
# Tenants
# -------------------------------------------------------------------

# Internal tenants that must never be suspended, archived, or deleted.
RESERVED_SCHOOL_CODES = {"PLATFORM", "DEFAULT"}


async def _get_tenant_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


async def list_tenants(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status_filter: str | None = None,
    include_archived: bool = False,
) -> tuple[list[TenantResponse], int]:
    """List schools (admin only). Internal org tenants (PLATFORM/DEFAULT) are excluded
    by the school type filter; archived schools are hidden unless requested."""
    filters = [Tenant.tenant_type == "school"]
    if not include_archived:
        filters.append(Tenant.deleted_at.is_(None))
    if status_filter:
        filters.append(Tenant.status == status_filter)
    if search:
        pattern = f"%{search}%"
        filters.append(
            Tenant.tenant_name.ilike(pattern) | Tenant.school_code.ilike(pattern)
        )

    count_result = await db.execute(
        select(func.count()).select_from(Tenant).where(*filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Tenant)
        .where(*filters)
        .order_by(Tenant.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tenants = result.scalars().all()

    return [TenantResponse.model_validate(t) for t in tenants], total


async def create_tenant(
    db: AsyncSession,
    payload: TenantCreate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> TenantResponse:
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

    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    await log_audit(
        db, user_id=actor_id, action="tenant.create",
        entity_type="tenant", entity_id=tenant.tenant_id,
        details={"tenant_name": tenant.tenant_name, "school_code": tenant.school_code},
        request=request,
    )
    return TenantResponse.model_validate(tenant)


async def update_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> TenantResponse:
    """Update tenant details (also covers suspend/activate via the status field)."""
    tenant = await _get_tenant_or_404(db, tenant_id)

    update_data = payload.model_dump(exclude_unset=True)
    new_status = update_data.get("status")
    if (
        new_status
        and new_status != "active"
        and tenant.school_code in RESERVED_SCHOOL_CODES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal platform tenants cannot be suspended or deactivated",
        )

    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.flush()
    await db.refresh(tenant)

    if new_status == "suspended":
        action = "tenant.suspend"
    elif new_status == "active":
        action = "tenant.activate"
    else:
        action = "tenant.update"
    await log_audit(
        db, user_id=actor_id, action=action,
        entity_type="tenant", entity_id=tenant.tenant_id,
        details={"changed": sorted(update_data.keys())},
        request=request,
    )
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

async def create_staff_user(
    db: AsyncSession,
    payload: StaffUserCreate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> StaffUserResponse:
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

    await log_audit(
        db, user_id=actor_id, action="user.create",
        entity_type="user", entity_id=user.user_id,
        details={"email": user.email, "role": user.role},
        request=request,
    )
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

async def _ensure_not_last_active_admin(
    db: AsyncSession, user: User, acting_admin_id: uuid.UUID | None
) -> None:
    """Guards for platform-admin accounts: no self-lockout, and at least one
    active platform admin must always remain."""
    if acting_admin_id is not None and user.user_id == acting_admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot suspend or delete your own account",
        )
    if user.role == "admin":
        others = await db.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin",
                User.is_active == True,  # noqa: E712
                User.user_id != user.user_id,
            )
        )
        if (others.scalar() or 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove the last active platform admin",
            )


async def update_user_admin(
    db: AsyncSession,
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> StaffUserResponse:
    """Toggle active status, reset password, or edit profile basics. Platform admin only."""
    from app.auth.utils import hash_password

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    actions: list[str] = []
    if payload.is_active is not None and payload.is_active != user.is_active:
        if not payload.is_active:
            await _ensure_not_last_active_admin(db, user, actor_id)
        user.is_active = payload.is_active
        actions.append("user.activate" if payload.is_active else "user.suspend")
    if payload.new_password:
        user.password_hash = hash_password(payload.new_password)
        actions.append("user.reset_password")
    profile_changed = False
    for field in ("first_name", "last_name", "phone"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
            profile_changed = True
    if profile_changed:
        actions.append("user.update")

    await db.flush()
    await db.refresh(user)
    for action in actions:
        await log_audit(
            db, user_id=actor_id, action=action,
            entity_type="user", entity_id=user.user_id,
            details={"email": user.email, "role": user.role},
            request=request,
        )
    return StaffUserResponse.model_validate(user)


async def list_all_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
    search: str | None = None,
    tenant_id: uuid.UUID | None = None,
    status_filter: str | None = None,
) -> tuple[list[AdminUserRow], int]:
    """Cross-tenant user list. Deliberately includes suspended and soft-deleted
    users so the platform admin can see and restore them."""
    filters = []
    if role:
        filters.append(User.role == role)
    if tenant_id is not None:
        filters.append(User.tenant_id == tenant_id)
    if status_filter == "active":
        filters.append(User.is_active == True)  # noqa: E712
        filters.append(User.deleted_at.is_(None))
    elif status_filter == "inactive":
        filters.append(User.is_active == False)  # noqa: E712
        filters.append(User.deleted_at.is_(None))
    elif status_filter == "deleted":
        filters.append(User.deleted_at.is_not(None))
    if search:
        pattern = f"%{search}%"
        filters.append(
            User.email.ilike(pattern)
            | (User.first_name + " " + User.last_name).ilike(pattern)
        )

    count_result = await db.execute(
        select(func.count()).select_from(User).where(*filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(User, Tenant.tenant_name)
        .join(Tenant, User.tenant_id == Tenant.tenant_id)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = [
        AdminUserRow(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            profile_image=user.profile_image,
            is_active=user.is_active,
            deleted_at=user.deleted_at,
            last_login=user.last_login,
            created_at=user.created_at,
        )
        for user, tenant_name in result.all()
    ]
    return rows, total


async def soft_delete_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> None:
    """Soft-delete a user: blocks login immediately, keeps the row for audit trails."""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await _ensure_not_last_active_admin(db, user, actor_id)

    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_audit(
        db, user_id=actor_id, action="user.delete",
        entity_type="user", entity_id=user.user_id,
        details={"email": user.email, "role": user.role},
        request=request,
    )


async def delete_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> None:
    """Soft-delete (archive) a school. Data is retained; the school disappears from
    default listings and its users can no longer sign in or register."""
    tenant = await _get_tenant_or_404(db, tenant_id)
    if tenant.school_code in RESERVED_SCHOOL_CODES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal platform tenants cannot be archived",
        )
    tenant.deleted_at = datetime.now(timezone.utc)
    tenant.status = "archived"
    await db.flush()
    await log_audit(
        db, user_id=actor_id, action="tenant.archive",
        entity_type="tenant", entity_id=tenant.tenant_id,
        details={"tenant_name": tenant.tenant_name},
        request=request,
    )


# -------------------------------------------------------------------
# Counselor administration (platform-wide)
# -------------------------------------------------------------------

async def _get_or_create_platform_tenant(db: AsyncSession) -> Tenant:
    """Counselors belong to the Kio platform tenant, not a school."""
    result = await db.execute(select(Tenant).where(Tenant.school_code == "PLATFORM"))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Kio Platform",
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

def _audit_log_filters(
    user_id: uuid.UUID | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list:
    """Shared WHERE clauses for audit-log listing and export."""
    filters = []
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action.ilike(f"{action}%"))
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)
    return filters


def _audit_row_to_response(log: AuditLog, user: User | None) -> AuditLogResponse:
    return AuditLogResponse(
        audit_id=log.audit_id,
        user_id=log.user_id,
        user_name=f"{user.first_name} {user.last_name}" if user else None,
        user_role=user.role if user else None,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        details=log.details,
        created_at=log.created_at,
    )


async def list_audit_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[AuditLogResponse], int]:
    """List audit logs with optional filters (admin only)."""
    filters = _audit_log_filters(user_id, action, date_from, date_to)

    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(*filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.user_id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return [_audit_row_to_response(log, user) for log, user in result.all()], total


AUDIT_EXPORT_MAX_ROWS = 10_000


async def export_audit_logs_csv(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> str:
    """Render filtered audit logs as CSV text (capped at AUDIT_EXPORT_MAX_ROWS)."""
    import csv
    import io
    import json

    result = await db.execute(
        select(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.user_id)
        .where(*_audit_log_filters(user_id, action, date_from, date_to))
        .order_by(AuditLog.created_at.desc())
        .limit(AUDIT_EXPORT_MAX_ROWS)
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "timestamp", "user_id", "user_name", "role", "action",
        "entity_type", "entity_id", "ip_address", "user_agent", "details",
    ])
    for log, user in result.all():
        writer.writerow([
            log.created_at.isoformat(),
            str(log.user_id) if log.user_id else "",
            f"{user.first_name} {user.last_name}" if user else "",
            user.role if user else "",
            log.action,
            log.entity_type or "",
            str(log.entity_id) if log.entity_id else "",
            log.ip_address or "",
            log.user_agent or "",
            json.dumps(log.details) if log.details else "",
        ])
    return buffer.getvalue()


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


# -------------------------------------------------------------------
# Cross-tenant risk oversight
# -------------------------------------------------------------------
# /risk/queue scopes to the CALLER's tenant, so a platform admin calling it
# sees their own (empty) queue rather than the platform. These functions are
# the cross-tenant equivalent, and are deliberately read-only — see the note
# on AdminRiskRow in schemas.py.

# Most severe first: the ordering exists so an admin scanning the list sees
# critical rows before low ones regardless of when they arrived.
_ADMIN_LEVEL_SEVERITY = case(
    {"critical": 4, "red": 3, "yellow": 2, "green": 1},
    value=RiskAssessment.risk_level,
    else_=0,
)


def _risk_base_query():
    """Assessment joined to its student, school, assigned counselor and reviewer.

    Two separate aliases of `users` are needed: one for the student behind the
    assessment, one for whoever reviewed it. Without aliasing, SQLAlchemy would
    collapse them into a single join and silently return the wrong names.
    """
    student_user = aliased(User, name="student_user")
    counselor_user = aliased(User, name="counselor_user")
    reviewer_user = aliased(User, name="reviewer_user")

    query = (
        select(
            RiskAssessment,
            student_user.first_name,
            student_user.last_name,
            Tenant.tenant_id,
            Tenant.tenant_name,
            counselor_user.first_name,
            counselor_user.last_name,
            reviewer_user.first_name,
            reviewer_user.last_name,
        )
        .join(StudentProfile, RiskAssessment.student_id == StudentProfile.student_id)
        .join(student_user, StudentProfile.user_id == student_user.user_id)
        .join(Tenant, student_user.tenant_id == Tenant.tenant_id)
        .outerjoin(
            CounselorProfile,
            CounselorProfile.counselor_id == RiskAssessment.assigned_counselor_id,
        )
        .outerjoin(counselor_user, CounselorProfile.user_id == counselor_user.user_id)
        .outerjoin(reviewer_user, RiskAssessment.reviewed_by == reviewer_user.user_id)
    )
    return query, student_user


def _full_name(first: str | None, last: str | None) -> str | None:
    name = f"{first or ''} {last or ''}".strip()
    return name or None


def _risk_row_fields(row, now: datetime) -> dict:
    """Shared field mapping for the list row and the detail record."""
    (
        assessment,
        s_first, s_last,
        tenant_id, school_name,
        c_first, c_last,
        r_first, r_last,
    ) = row

    created = assessment.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    return {
        "risk_id": assessment.risk_id,
        "student_id": assessment.student_id,
        "student_name": _full_name(s_first, s_last) or "Unknown",
        "tenant_id": tenant_id,
        "school_name": school_name,
        "risk_level": assessment.risk_level,
        "risk_score": float(assessment.risk_score) if assessment.risk_score is not None else None,
        "confidence": float(assessment.confidence) if assessment.confidence is not None else None,
        "review_status": assessment.review_status,
        "assigned_counselor_id": assessment.assigned_counselor_id,
        "assigned_counselor_name": _full_name(c_first, c_last),
        "reviewed_by_name": _full_name(r_first, r_last),
        "reviewed_at": assessment.reviewed_at,
        "generated_by": assessment.generated_by,
        "created_at": assessment.created_at,
        "age_hours": round((now - created).total_seconds() / 3600, 1),
    }


async def list_admin_risk(
    db: AsyncSession,
    page: int,
    page_size: int,
    *,
    review_status: str | None = None,
    risk_level: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> tuple[list[AdminRiskRow], int]:
    """Cross-tenant assessment list, most severe first then oldest.

    Oldest-first within a severity tier is deliberate: the point of this view is
    spotting what has been waiting too long, so the stalest row in a tier should
    surface at the top, not the newest.
    """
    now = datetime.now(timezone.utc)
    query, _student_user = _risk_base_query()

    filters = []
    if review_status:
        filters.append(RiskAssessment.review_status == review_status)
    if risk_level:
        filters.append(RiskAssessment.risk_level == risk_level)
    if tenant_id:
        filters.append(Tenant.tenant_id == tenant_id)
    if filters:
        query = query.where(*filters)

    count_query = (
        select(func.count())
        .select_from(RiskAssessment)
        .join(StudentProfile, RiskAssessment.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .join(Tenant, User.tenant_id == Tenant.tenant_id)
    )
    if filters:
        count_query = count_query.where(*filters)
    total = (await db.execute(count_query)).scalar() or 0

    rows = (
        await db.execute(
            query
            .order_by(_ADMIN_LEVEL_SEVERITY.desc(), RiskAssessment.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return [AdminRiskRow(**_risk_row_fields(row, now)) for row in rows], total


async def get_admin_risk_detail(db: AsyncSession, risk_id: uuid.UUID) -> AdminRiskDetail:
    """One assessment in full, across tenants."""
    now = datetime.now(timezone.utc)
    query, _student_user = _risk_base_query()

    row = (
        await db.execute(query.where(RiskAssessment.risk_id == risk_id))
    ).first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk assessment not found",
        )

    assessment = row[0]
    return AdminRiskDetail(
        **_risk_row_fields(row, now),
        categories=assessment.categories,
        summary=assessment.summary,
        trigger_reason=assessment.trigger_reason,
        resolution_note=assessment.resolution_note,
        counselor_risk_level=assessment.counselor_risk_level,
        verdict=assessment.verdict,
        outcome=assessment.outcome,
    )
