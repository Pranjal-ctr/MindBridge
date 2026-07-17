"""
Kio Wellness Schemas
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
# Daily Check-in (official, once per calendar day)
# -------------------------------------------------------------------

DAILY_MOODS = ["amazing", "good", "okay", "low", "very_difficult"]
CHECKIN_REASONS = [
    "academics", "family", "friends", "relationship", "health",
    "career", "sports", "financial", "social_media", "other",
]

_MOOD_PATTERN = r"^(amazing|good|okay|low|very_difficult)$"
_REASON_PATTERN = (
    r"^(academics|family|friends|relationship|health|career|sports|financial|social_media|other)$"
)


class DailyCheckinRequest(BaseModel):
    """Official mood check-in: mood + primary reason, optional reflection."""
    mood: str = Field(..., pattern=_MOOD_PATTERN)
    reason: str = Field(..., pattern=_REASON_PATTERN)
    reflection: str | None = Field(None, max_length=2000)


class DailyCheckinInfo(BaseModel):
    """The current official check-in as stored (latest in this window)."""
    date: date
    mood: str
    reason: str
    reflection: str | None = None
    created_at: datetime | None = None


class DailyCheckinStatusResponse(BaseModel):
    """Check-in state for the current 12-hour window.

    `completed_today` keeps its original name for API compatibility but means
    "completed in the current 12-hour window". Up to 2 submissions per window:
    the initial check-in plus one update.
    """
    completed_today: bool
    checkin: DailyCheckinInfo | None = None
    updates_remaining: int = 0
    window_ends_at: datetime | None = None


class DailyCheckinResponse(BaseModel):
    checkin: DailyCheckinInfo
    wellness: WellnessScoreResponse
    updates_remaining: int = 0


# -------------------------------------------------------------------
# Mood Calendar
# -------------------------------------------------------------------

class MoodCalendarDay(BaseModel):
    """One calendar day; mood is the official check-in label when present."""
    date: date
    mood: str | None = None
    mood_score: int | None = None
    reason: str | None = None
    note: str | None = None  # student's own reflection (never sent to parents)


class MoodCalendarResponse(BaseModel):
    month: str  # YYYY-MM
    days: list[MoodCalendarDay]


# -------------------------------------------------------------------
# Personal Insights (pattern mining, shown only with enough history)
# -------------------------------------------------------------------

class PersonalInsight(BaseModel):
    kind: str  # weekday_pattern | reason_pattern | mood_trend | stress_pattern | consistency
    title: str
    body: str
    evidence: str  # e.g. "Based on 21 check-ins over the last 6 weeks"


class PersonalInsightsResponse(BaseModel):
    insights: list[PersonalInsight]
    sufficient_data: bool
    checkin_days: int


# -------------------------------------------------------------------
# Activities (personalized suggestions)
# -------------------------------------------------------------------

class ActivityItem(BaseModel):
    activity_id: str
    title: str
    description: str
    category: str  # mindfulness | physical | social | reflection | rest | creative
    duration_minutes: int
    reason: str  # why this is suggested today
    completed: bool = False  # persisted completion state
    is_daily: bool = False   # today's fresh pick vs. the weekly set


class ActivitiesResponse(BaseModel):
    activities: list[ActivityItem]
    personalized: bool  # True when the AI tailored the list; False = signal-based defaults
    generated_at: datetime


class ActivityCompleteRequest(BaseModel):
    activity_id: str = Field(..., max_length=60)
    title: str = Field(..., max_length=255)


# -------------------------------------------------------------------
# Weekly Report (shared response shape for student/parent/counselor)
# -------------------------------------------------------------------

class WeeklyReportResponse(BaseModel):
    audience: str
    week_start: date
    headline: str
    summary: str
    highlights: list[str] = []
    focus_areas: list[str] = []
    generated_by: str | None = None
    created_at: datetime


def weekly_report_response(report) -> "WeeklyReportResponse":
    """Map a WeeklyReport row to the API shape."""
    content = report.content or {}
    return WeeklyReportResponse(
        audience=report.audience,
        week_start=report.week_start,
        headline=content.get("headline", ""),
        summary=content.get("summary", ""),
        highlights=content.get("highlights", []),
        focus_areas=content.get("focus_areas", []),
        generated_by=report.generated_by,
        created_at=report.created_at,
    )


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
