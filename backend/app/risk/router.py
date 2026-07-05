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
)
from app.risk.service import create_risk_assessment, get_active_risk_alerts, list_risk_assessments
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
