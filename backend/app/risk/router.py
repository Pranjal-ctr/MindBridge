"""
MindBridge Risk Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List risk assessments for a student."""
    assessments, total = await list_risk_assessments(db, student_id)
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pending AI/tripwire assessments awaiting review (most severe first)."""
    items, total = await get_risk_queue(db, tenant_id)
    return RiskQueueListResponse(items=items, total=total)


@router.patch(
    "/queue/{risk_id}",
    response_model=RiskAssessmentResponse,
)
async def review_queued_assessment(
    risk_id: uuid.UUID,
    payload: RiskReviewUpdate,
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    reviewer: Annotated[User, Depends(require_role("counselor", "school_admin", "admin"))],
):
    """Acknowledge or resolve a queued assessment."""
    return await review_risk_assessment(db, risk_id, tenant_id, reviewer.user_id, payload)
