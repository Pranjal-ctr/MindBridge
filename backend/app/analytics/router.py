"""
Kio Analytics Router
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentTenant, require_role
from app.analytics.schemas import AnalyticsOverview, SnapshotListResponse
from app.analytics.service import get_analytics_overview, list_snapshots
from database.session import get_db

router = APIRouter()


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    dependencies=[Depends(require_role("school_admin", "admin"))],
)
async def get_overview(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get school-wide analytics overview.

    Includes total students, average wellness, risk distribution,
    and wellness trend data. All data is anonymized.
    """
    return await get_analytics_overview(db, tenant_id)


@router.get(
    "/snapshots",
    response_model=SnapshotListResponse,
    dependencies=[Depends(require_role("school_admin", "admin"))],
)
async def get_snapshots(
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get historical analytics snapshots."""
    snapshots, total = await list_snapshots(db, tenant_id)
    return SnapshotListResponse(snapshots=snapshots, total=total)
