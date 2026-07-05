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
