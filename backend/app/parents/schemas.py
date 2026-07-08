"""
MindBridge Parents Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ChildSummary(BaseModel):
    """Summary of a linked child for parent dashboard."""
    student_id: uuid.UUID
    first_name: str
    last_name: str
    age: int | None = None
    wellness_score: float | None = None
    risk_level: str = "green"
    relationship: str | None = None


class ChildrenListResponse(BaseModel):
    """List of parent's linked children."""
    children: list[ChildSummary]


class WellnessTrendPoint(BaseModel):
    """Single data point for wellness trend chart."""
    date: str
    score: float


class StressFactor(BaseModel):
    """Stress factor breakdown."""
    name: str
    value: int


class WellnessBreakdown(BaseModel):
    """Explainable wellness score breakdown (from the latest computed score)."""
    trend: str
    confidence: float | None = None
    components: dict = {}
    explanation: str | None = None
    calculated_at: datetime | None = None


class RiskTrendPoint(BaseModel):
    """Daily risk reading (levels/scores only -- never message content)."""
    date: str
    level: str
    score: float | None = None


class MoodTrendPoint(BaseModel):
    """Daily dominant emotion."""
    date: str
    emotion: str


class TodayInsightCard(BaseModel):
    """AI-generated insight card for the parent dashboard."""
    type: str = "info"  # positive | caution | info
    title: str
    body: str


class ChildInsightResponse(BaseModel):
    """Aggregated insights for a parent's child."""
    student_id: uuid.UUID
    student_name: str
    wellness_score: float | None = None
    risk_level: str = "green"
    emotional_state: str = "Stable"
    summary: str | None = None
    wellness_trend: list[WellnessTrendPoint] = []
    stress_factors: list[StressFactor] = []
    recommendations: list[str] = []
    last_updated: datetime | None = None
    # Intelligence-layer fields (all additive/optional)
    wellness_breakdown: WellnessBreakdown | None = None
    risk_trend: list[RiskTrendPoint] = []
    mood_trend: list[MoodTrendPoint] = []
    today_insights: list[TodayInsightCard] = []
    improvements: list[str] = []
    concerns: list[str] = []
    weekly_progress: dict = {}


class RecommendationResponse(BaseModel):
    """Parenting recommendation."""
    title: str
    description: str
    category: str


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationResponse]
