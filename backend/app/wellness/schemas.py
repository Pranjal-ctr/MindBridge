"""
MindBridge Wellness Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Wellness Records
# -------------------------------------------------------------------

class WellnessRecordCreate(BaseModel):
    """Daily wellness check-in."""
    mood_score: int = Field(..., ge=1, le=10)
    stress_score: int = Field(..., ge=1, le=10)
    confidence_score: int = Field(..., ge=1, le=10)
    anxiety_score: int = Field(..., ge=1, le=10)
    energy_score: int = Field(..., ge=1, le=10)
    date_recorded: date | None = None  # Defaults to today


class WellnessRecordResponse(BaseModel):
    """Wellness record response."""
    record_id: uuid.UUID
    student_id: uuid.UUID
    mood_score: int | None
    stress_score: int | None
    confidence_score: int | None
    anxiety_score: int | None
    energy_score: int | None
    date_recorded: date
    created_at: datetime

    model_config = {"from_attributes": True}


# -------------------------------------------------------------------
# Goals
# -------------------------------------------------------------------

class GoalCreate(BaseModel):
    """Create a new student goal."""
    goal_title: str = Field(..., max_length=255)
    goal_description: str | None = None
    target_date: date | None = None


class GoalUpdate(BaseModel):
    """Update goal fields."""
    goal_title: str | None = Field(None, max_length=255)
    goal_description: str | None = None
    status: str | None = Field(None, pattern=r"^(active|completed|paused|abandoned)$")
    target_date: date | None = None


class GoalResponse(BaseModel):
    """Goal response."""
    goal_id: uuid.UUID
    student_id: uuid.UUID
    goal_title: str
    goal_description: str | None = None
    status: str
    target_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# -------------------------------------------------------------------
# Journal
# -------------------------------------------------------------------

class JournalEntryCreate(BaseModel):
    """Create a journal entry."""
    title: str | None = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    mood_score: int | None = Field(None, ge=1, le=10)


class JournalEntryResponse(BaseModel):
    """Journal entry response."""
    journal_id: uuid.UUID
    student_id: uuid.UUID
    title: str | None = None
    content: str
    mood_score: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# -------------------------------------------------------------------
# Wellness Score (computed by the intelligence layer)
# -------------------------------------------------------------------

class WellnessScoreResponse(BaseModel):
    """Latest computed wellness score with the explainable breakdown."""
    has_data: bool
    overall: float | None = None
    trend: str | None = None
    confidence: float | None = None
    components: dict | None = None
    explanation: str | None = None
    streak_days: int = 0
    calculated_at: datetime | None = None


class WellnessScorePoint(BaseModel):
    date: datetime
    score: float
    trend: str


class WellnessScoreHistoryResponse(BaseModel):
    points: list[WellnessScorePoint]


class MoodCheckinRequest(BaseModel):
    """Lightweight one-tap mood check-in."""
    mood: str = Field(..., pattern=r"^(happy|okay|down)$")


class MoodCheckinResponse(BaseModel):
    record: WellnessRecordResponse
    wellness: WellnessScoreResponse


# -------------------------------------------------------------------
# Emotions (computed from emotion_history)
# -------------------------------------------------------------------

class EmotionTimelinePoint(BaseModel):
    created_at: datetime
    emotion: str
    intensity: int | None = None


class EmotionTrendPoint(BaseModel):
    period: str  # ISO date (weekly trend) or week-start date (monthly trend)
    emotion: str


class EmotionSummaryResponse(BaseModel):
    has_data: bool
    current_emotion: str | None = None
    dominant_emotion: str | None = None
    stability: float | None = None      # 0-1: share of recent readings matching dominant
    confidence: float | None = None
    weekly_trend: list[EmotionTrendPoint] = []
    monthly_trend: list[EmotionTrendPoint] = []
    timeline: list[EmotionTimelinePoint] = []


# -------------------------------------------------------------------
# List Responses
# -------------------------------------------------------------------

class WellnessListResponse(BaseModel):
    records: list[WellnessRecordResponse]
    total: int


class GoalListResponse(BaseModel):
    goals: list[GoalResponse]
    total: int


class JournalListResponse(BaseModel):
    entries: list[JournalEntryResponse]
    total: int
