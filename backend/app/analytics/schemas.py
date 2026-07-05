"""
MindBridge Analytics Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    """School-wide analytics overview matching the SchoolAdminDashboard."""
    total_students: int = 0
    avg_wellness_score: float = 0.0
    active_counselors: int = 0
    counselor_utilization: float = 0.0
    risk_distribution: list[RiskBucket] = []
    wellness_trend: list[WellnessTrendPoint] = []
    stress_by_category: list[StressCategory] = []


class RiskBucket(BaseModel):
    """Risk distribution bucket."""
    name: str
    value: int
    color: str


class WellnessTrendPoint(BaseModel):
    """Monthly wellness trend data point."""
    month: str
    score: float


class StressCategory(BaseModel):
    """Stress factor category."""
    category: str
    students: int


class SnapshotResponse(BaseModel):
    """Analytics snapshot response."""
    snapshot_id: uuid.UUID
    tenant_id: uuid.UUID
    snapshot_month: date
    total_students: int
    avg_wellness: float | None = None
    avg_risk: float | None = None
    engagement_rate: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotListResponse(BaseModel):
    snapshots: list[SnapshotResponse]
    total: int
