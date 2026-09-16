"""
Kio Risk Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_audit
from app.audit_actions import AuditAction, AuditEntity, AuditSeverity
from app.dependencies import CurrentTenant, CurrentUser, require_role
from app.risk.schemas import (
    RiskAlertListResponse,
    RiskAssessmentCreate,
    RiskAssessmentResponse,
    RiskListResponse,
    RiskQueueListResponse,
    RiskReviewUpdate,
)
from app.risk.service import (
    create_risk_assessment,
    get_active_risk_alerts,
    get_risk_queue,
    list_risk_assessments,
    review_risk_assessment,
)
from database.models import User
from database.session import get_db

router = APIRouter()


@router.post(
    "/assessments",
    response_model=RiskAssessmentResponse,
    status_code=201,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def create_assessment(
    payload: RiskAssessmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a risk assessment for a student. Counselors and admins only."""
    return await create_risk_assessment(db, payload)


@router.get(
    "/assessments/{student_id}",
    response_model=RiskListResponse,
    dependencies=[Depends(require_role("counselor", "school_admin", "admin"))],
)
async def get_assessments(
    student_id: uuid.UUID,
    request: Request,
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    viewer: Annotated[User, Depends(require_role("counselor", "school_admin", "admin"))],
):
    """List risk assessments for a student."""
    assessments, total = await list_risk_assessments(db, student_id)
    # Who looked at which student's risk history is exactly the question this
    # table exists to answer. The assessments themselves are not copied in --
    # only the fact of the read and whose record it was.
    await log_audit(
        db,
        user_id=viewer.user_id,
        action=AuditAction.RISK_CASE_VIEWED,
        entity_type="student",
        entity_id=student_id,
        details={"assessment_count": total},
        request=request,
        actor=viewer,
        severity=AuditSeverity.NOTICE,
    )
    return RiskListResponse(assessments=assessments, total=total)


@router.get(
    "/alerts",
    response_model=RiskAlertListResponse,
    dependencies=[Depends(require_role("counselor", "school_admin", "admin"))],
)
async def get_alerts(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get active high-risk alerts for the current tenant."""
    alerts, total = await get_active_risk_alerts(db, tenant_id)
    return RiskAlertListResponse(alerts=alerts, total=total)


# -------------------------------------------------------------------
# Counselor review queue
# -------------------------------------------------------------------

@router.get(
    "/queue",
    response_model=RiskQueueListResponse,
    dependencies=[Depends(require_role("counselor", "school_admin", "admin"))],
)
async def get_review_queue(
    tenant_id: CurrentTenant,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    viewer: Annotated[User, Depends(require_role("counselor", "school_admin", "admin"))],
):
    """Pending AI/tripwire assessments awaiting review (most severe first)."""
    items, total = await get_risk_queue(db, tenant_id)
    await log_audit(
        db,
        user_id=viewer.user_id,
        action=AuditAction.RISK_QUEUE_VIEWED,
        entity_type=AuditEntity.RISK_ASSESSMENT,
        details={"pending_count": total},
        request=request,
        actor=viewer,
        severity=AuditSeverity.INFO,
    )
    return RiskQueueListResponse(items=items, total=total)


@router.patch(
    "/queue/{risk_id}",
    response_model=RiskAssessmentResponse,
)
async def review_queued_assessment(
    risk_id: uuid.UUID,
    payload: RiskReviewUpdate,
    tenant_id: CurrentTenant,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    reviewer: Annotated[User, Depends(require_role("counselor", "school_admin", "admin"))],
):
    """Acknowledge or resolve a queued assessment."""
    return await review_risk_assessment(
        db, risk_id, tenant_id, reviewer.user_id, payload,
        reviewer_role=reviewer.role, request=request,
    )
