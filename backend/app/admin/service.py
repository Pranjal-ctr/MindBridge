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

from app.audit import log_audit, log_audit_detached
from app.audit_actions import AuditAction, AuditEntity, AuditResult, AuditSeverity
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
        db, user_id=actor_id, action=AuditAction.SCHOOL_CREATED,
        entity_type=AuditEntity.TENANT, entity_id=tenant.tenant_id,
        details={"tenant_name": tenant.tenant_name, "school_code": tenant.school_code},
        request=request, actor_role="admin",
        # The event belongs to the school created, not to the admin's own.
        tenant_id=tenant.tenant_id,
        severity=AuditSeverity.NOTICE,
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
        action = AuditAction.SCHOOL_SUSPENDED
    elif new_status == "active":
        action = AuditAction.SCHOOL_ACTIVATED
    else:
        action = AuditAction.SCHOOL_UPDATED
    await log_audit(
        db, user_id=actor_id, action=action,
        entity_type=AuditEntity.TENANT, entity_id=tenant.tenant_id,
        # Field *names* only, never the values -- this payload can carry seat
        # limits and billing detail that the trail has no need to duplicate.
        details={"changed": sorted(update_data.keys())},
        request=request, actor_role="admin", tenant_id=tenant.tenant_id,
        # Suspending a school signs out every one of its users.
        severity=(
            AuditSeverity.WARNING if new_status == "suspended"
            else AuditSeverity.NOTICE
        ),
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
    tenant_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> None:
    """
    Every break-glass access writes an audit row.

    The reason used to be interpolated into the action name, which made the
    action column a free-text field: admin-typed prose landed in the indexed
    column the admin page filters on, so no two break-glass events ever shared
    an action string and the "Break-glass" filter could only ever prefix-match.
    The reason is structured metadata; it belongs in details.
    """
    await log_audit(
        db,
        user_id=admin_user_id,
        action=AuditAction.BREAK_GLASS_CHAT_ACCESS,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"reason": reason[:200]},
        request=request,
        actor_role="admin",
        tenant_id=tenant_id,
        # A platform admin reading a student's conversations is the single
        # most sensitive thing this product permits. It should never be
        # buried among routine events.
        severity=AuditSeverity.CRITICAL,
    )


async def break_glass_list_conversations(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
    student_id: uuid.UUID,
    reason: str,
    request: Request | None = None,
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

    await _log_break_glass(
        db, admin_user_id, "student", student_id, reason,
        tenant_id=student_user.tenant_id, request=request,
    )

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
    request: Request | None = None,
) -> BreakGlassMessageList:
    """Read a conversation transcript for crisis review. Audit-logged."""
    # Conversations carry no tenant of their own, so the school scope for the
    # audit row is resolved through the student who owns it -- the event
    # belongs to that student's school, not to the platform admin's.
    conv_result = await db.execute(
        select(Conversation, User.tenant_id)
        .join(StudentProfile, Conversation.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(Conversation.conversation_id == conversation_id)
    )
    conv_row = conv_result.one_or_none()
    if conv_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    _conversation, subject_tenant_id = conv_row

    await _log_break_glass(
        db, admin_user_id, "conversation", conversation_id, reason,
        tenant_id=subject_tenant_id, request=request,
    )

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
        db, user_id=actor_id, action=AuditAction.USER_CREATED,
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
        actions.append(
            AuditAction.USER_REACTIVATED if payload.is_active
            else AuditAction.USER_DEACTIVATED
        )
    if payload.new_password:
        user.password_hash = hash_password(payload.new_password)
        actions.append(AuditAction.PASSWORD_RESET_BY_ADMIN)
    profile_changed = False
    for field in ("first_name", "last_name", "phone"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
            profile_changed = True
    if profile_changed:
        actions.append(AuditAction.USER_UPDATED)

    await db.flush()
    await db.refresh(user)
    for action in actions:
        await log_audit(
            db, user_id=actor_id, action=action,
            entity_type=AuditEntity.USER, entity_id=user.user_id,
            # The new password is of course never recorded -- only that one
            # was set, and by whom.
            details={"email": user.email, "role": user.role},
            request=request, actor_role="admin",
            # The subject's school, not the acting platform admin's.
            tenant_id=user.tenant_id,
            severity=(
                AuditSeverity.WARNING
                if action in (
                    AuditAction.USER_DEACTIVATED,
                    AuditAction.PASSWORD_RESET_BY_ADMIN,
                )
                else AuditSeverity.NOTICE
            ),
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
        db, user_id=actor_id, action=AuditAction.USER_DEACTIVATED,
        entity_type=AuditEntity.USER, entity_id=user.user_id,
        details={"email": user.email, "role": user.role, "soft_delete": True},
        request=request, actor_role="admin", tenant_id=user.tenant_id,
        severity=AuditSeverity.WARNING,
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
        db, user_id=actor_id, action=AuditAction.SCHOOL_ARCHIVED,
        entity_type=AuditEntity.TENANT, entity_id=tenant.tenant_id,
        details={"tenant_name": tenant.tenant_name},
        request=request, actor_role="admin", tenant_id=tenant.tenant_id,
        severity=AuditSeverity.WARNING,
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


async def create_counselor(
    db: AsyncSession,
    payload: CounselorCreate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> CounselorAdminResponse:
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
    await log_audit(
        db, user_id=actor_id, action=AuditAction.COUNSELOR_REGISTERED,
        entity_type=AuditEntity.COUNSELOR, entity_id=counselor.counselor_id,
        details={"email": user.email, "is_verified": counselor.is_verified},
        request=request, actor_role="admin", tenant_id=user.tenant_id,
        severity=AuditSeverity.NOTICE,
    )
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
    db: AsyncSession,
    counselor_id: uuid.UUID,
    payload: CounselorAdminUpdate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
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
    # Verification is what puts a counselor in front of students in the public
    # booking directory, so a change to it is called out separately from an
    # ordinary profile edit rather than being flattened into "updated".
    verification_changed = "is_verified" in data
    await log_audit(
        db,
        user_id=actor_id,
        action=(
            AuditAction.COUNSELOR_VERIFIED if verification_changed
            else AuditAction.USER_UPDATED
        ),
        entity_type=AuditEntity.COUNSELOR,
        entity_id=counselor.counselor_id,
        details={
            "changed": sorted(data.keys()),
            **({"is_verified": counselor.is_verified} if verification_changed else {}),
        },
        request=request, actor_role="admin", tenant_id=user.tenant_id,
        severity=(
            AuditSeverity.WARNING if verification_changed else AuditSeverity.NOTICE
        ),
    )
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
    db: AsyncSession,
    feature_name: str,
    payload: AIRouteUpdate,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
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
    # Which model answers a given feature changes what every student is told.
    await log_audit(
        db, user_id=actor_id, action=AuditAction.COMRADE_CONFIGURATION_CHANGED,
        entity_type=AuditEntity.CONFIG, entity_id=None,
        details={
            "feature_name": feature_name,
            "primary_provider": route.primary_provider,
            "primary_model": route.primary_model,
        },
        request=request, actor_role="admin",
        severity=AuditSeverity.CRITICAL,
    )
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

async def activate_prompt(
    db: AsyncSession,
    prompt_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> PromptResponse:
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
    # Activating a prompt version changes Comrade's instructions for every
    # student on the platform at once. The prompt *text* is not recorded --
    # it is versioned in ai_prompt_versions and named here by id.
    await log_audit(
        db, user_id=actor_id, action=AuditAction.COMRADE_CONFIGURATION_CHANGED,
        entity_type=AuditEntity.CONFIG, entity_id=prompt.prompt_id,
        details={
            "prompt_name": prompt.prompt_name,
            "version": prompt.version,
            "change": "prompt_activated",
        },
        request=request, actor_role="admin",
        severity=AuditSeverity.CRITICAL,
    )
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
    user_id=None,
    action=None,
    date_from=None,
    date_to=None,
    tenant_id=None,
    actor_role=None,
    entity_type=None,
    result=None,
    severity=None,
    request_id=None,
) -> list:
    """
    Shared WHERE clauses for audit-log listing and export.

    Listing and export must filter identically -- an export that quietly
    covered a different set than the screen it was taken from would be worse
    than no export at all.
    """
    filters = []
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action.ilike(f"{action}%"))
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)
    if tenant_id is not None:
        filters.append(AuditLog.tenant_id == tenant_id)
    if actor_role:
        filters.append(AuditLog.actor_role == actor_role)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if result:
        filters.append(AuditLog.result == result)
    if severity:
        filters.append(AuditLog.severity == severity)
    if request_id:
        filters.append(AuditLog.request_id == request_id)
    return filters


def _audit_row_to_response(
    log: AuditLog, user: User | None, school_name: str | None = None
) -> AuditLogResponse:
    return AuditLogResponse(
        audit_id=log.audit_id,
        user_id=log.user_id,
        user_name=f"{user.first_name} {user.last_name}" if user else None,
        # Prefer the role recorded on the event. Falling back to the user's
        # current role keeps pre-018 rows readable, but the stored value wins:
        # it is what the actor was at the time, which is the question a reader
        # of an audit trail is actually asking.
        user_role=log.actor_role or (user.role if user else None),
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        details=log.details,
        created_at=log.created_at,
        tenant_id=log.tenant_id,
        school_name=school_name,
        result=log.result,
        severity=log.severity,
        request_id=log.request_id,
    )


def _audit_select():
    """Audit rows joined to actor and school, both optional."""
    return (
        select(AuditLog, User, Tenant.tenant_name)
        .outerjoin(User, AuditLog.user_id == User.user_id)
        .outerjoin(Tenant, AuditLog.tenant_id == Tenant.tenant_id)
    )


async def list_audit_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tenant_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    result: str | None = None,
    severity: str | None = None,
    request_id: str | None = None,
) -> tuple[list[AuditLogResponse], int]:
    """List audit logs with optional filters (platform admin only).

    Filtering and pagination are both server-side: the table is append-only
    and grows without bound, so a client that fetched everything and filtered
    in the browser would eventually be asking for the whole history.
    """
    filters = _audit_log_filters(
        user_id, action, date_from, date_to, tenant_id,
        actor_role, entity_type, result, severity, request_id,
    )

    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(*filters)
    )
    total = count_result.scalar() or 0

    rows = await db.execute(
        _audit_select()
        .where(*filters)
        # audit_id breaks ties: created_at alone is not unique, and without a
        # deterministic order two pages can repeat or skip a row.
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return [
        _audit_row_to_response(log, user, school_name)
        for log, user, school_name in rows.all()
    ], total


# An export is a bounded operation, not a database dump.
AUDIT_EXPORT_MAX_ROWS = 10_000

# Rows per round trip while streaming, so peak memory stays flat in the size
# of the export rather than proportional to it.
_AUDIT_EXPORT_CHUNK = 500

AUDIT_EXPORT_COLUMNS = [
    "timestamp", "request_id", "severity", "result", "user_id", "user_name",
    "role", "school", "action", "entity_type", "entity_id", "ip_address",
    "user_agent", "details",
]


async def iter_audit_logs_csv(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tenant_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    result: str | None = None,
    severity: str | None = None,
    request_id: str | None = None,
):
    """
    Yield the filtered audit log as CSV text, a chunk at a time.

    Streamed rather than assembled in memory: the previous version built every
    matching row and its serialised details into one string before sending a
    byte, so a wide date range was a memory spike proportional to the export.

    Opens its **own** session rather than borrowing the request's. FastAPI
    closes `yield` dependencies before the response body is streamed, so a
    generator holding the request's session would be reading from a closed one
    by the time it ran. It also keeps a long export off the request's
    transaction, which has already been committed by the caller.

    Emits the same columns the on-screen table shows, plus the correlation id.
    There is no field here that the admin API does not already return, and
    `details` was scrubbed on the way into the table, not on the way out.
    """
    import csv
    import io as _io
    import json

    from database.session import async_session_factory

    filters = _audit_log_filters(
        user_id, action, date_from, date_to, tenant_id,
        actor_role, entity_type, result, severity, request_id,
    )

    buffer = _io.StringIO()
    writer = csv.writer(buffer)

    def _drain() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return text

    writer.writerow(AUDIT_EXPORT_COLUMNS)
    yield _drain()

    async with async_session_factory() as db:
        stream = await db.stream(
            _audit_select()
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.audit_id.desc())
            .limit(AUDIT_EXPORT_MAX_ROWS)
        )

        async for chunk in stream.partitions(_AUDIT_EXPORT_CHUNK):
            for log, user, school_name in chunk:
                writer.writerow([
                    log.created_at.isoformat(),
                    log.request_id or "",
                    log.severity,
                    log.result,
                    str(log.user_id) if log.user_id else "",
                    f"{user.first_name} {user.last_name}" if user else "",
                    log.actor_role or (user.role if user else ""),
                    school_name or "",
                    log.action,
                    log.entity_type or "",
                    str(log.entity_id) if log.entity_id else "",
                    log.ip_address or "",
                    log.user_agent or "",
                    json.dumps(log.details) if log.details else "",
                ])
            yield _drain()


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
    db: AsyncSession,
    config_key: str,
    payload: PlatformConfigUpdate,
    admin_user_id: uuid.UUID,
    request: Request | None = None,
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

    # Which key changed is the whole point of the record -- "a config changed"
    # with no indication of which one is not an audit trail. The value itself
    # is deliberately not stored: safety_floors is small and safe, but this
    # endpoint takes arbitrary JSON and the audit table is the wrong place to
    # accumulate whatever a future key holds.
    await log_audit(
        db,
        user_id=admin_user_id,
        action=(
            AuditAction.SAFETY_THRESHOLD_CHANGED
            if config_key == "safety_floors"
            else AuditAction.SETTINGS_CHANGED
        ),
        entity_type=AuditEntity.CONFIG,
        details={"config_key": config_key, "keys_set": sorted(payload.config_value.keys())},
        request=request,
        actor_role="admin",
        # Safety thresholds decide when a student is escalated to a human.
        severity=(
            AuditSeverity.CRITICAL
            if config_key == "safety_floors"
            else AuditSeverity.NOTICE
        ),
    )

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
