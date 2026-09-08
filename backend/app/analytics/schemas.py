"""
Kio Analytics Schemas

Everything here is school-wide and aggregate. No field may carry a value that
identifies one student — see MIN_COHORT_SIZE in service.py for how small
schools are handled.

Note on ordering: these models are defined before AnalyticsOverview because it
references them. `from __future__ import annotations` makes that work either
way, but relying on Pydantic's deferred resolution for models in the same
module is a needless trip hazard.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class RiskBucket(BaseModel):
    """One risk tier and how many students sit in it.

    All four tiers are always returned, zeros included, so the chart keeps
    stable colours and ordering as a cohort moves between tiers.
    """
    level: str          # green | yellow | red | critical
    name: str           # display label
    value: int
    color: str


class WellnessTrendPoint(BaseModel):
    """Mean wellness score across the school for one calendar month."""
    month: str          # "Mar"
    month_start: date   # unambiguous — "Mar" repeats across years
    score: float | None # None = no scores recorded that month (gap, not zero)
    students: int       # how many students contributed


class StressCategory(BaseModel):
    """Share of the cohort whose dominant stress topic is this category."""
    category: str
    students: int


class CounselorActivity(BaseModel):
    """Counselling coverage over the trailing 30 days."""
    active_counselors: int      # assigned to this school and available
    sessions_last_30d: int
    students_seen_last_30d: int
    upcoming_sessions: int


class AnalyticsOverview(BaseModel):
    """School-wide anonymised analytics.

    When `cohort_suppressed` is true the school is too small to break down
    without identifying individuals: only `total_students` is populated and
    every distribution comes back empty. The dashboard must say so rather than
    render empty charts.
    """
    # The school this data describes. Lives here rather than on UserResponse:
    # it is a property of the report, and the dashboard would otherwise have no
    # way to name the school without a second request.
    school_name: str = ""

    total_students: int = 0
    students_with_wellness_data: int = 0

    # None (not 0.0) when nothing has been recorded yet — zero is a real score.
    avg_wellness_score: float | None = None

    checked_in_last_7d: int = 0
    checkin_participation: float = 0.0   # 0-100, share of students

    counselors: CounselorActivity
    risk_distribution: list[RiskBucket] = []
    wellness_trend: list[WellnessTrendPoint] = []
    stress_by_category: list[StressCategory] = []

    cohort_suppressed: bool = False
    min_cohort_size: int = 0
    generated_at: datetime


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
