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
    School-wide analytics overview.

    Roster size, average wellness, check-in participation, risk distribution,
    six-month wellness trend, dominant stress topics, and counselling coverage
    — all aggregate, all scoped to the caller's school.

    Schools below the minimum cohort size come back with `cohort_suppressed`
    true and empty distributions: with a small roster a per-tier count
    identifies individual students to an admin who can already see the roster.
    Clients must render that state explicitly rather than as empty charts.

    Fields distinguish "no data" from zero — `avg_wellness_score` and a trend
    point's `score` are null when nothing has been recorded.
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
