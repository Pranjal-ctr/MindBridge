"""
MindBridge Counselors Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Schedule a counselor session."""
    student_id: uuid.UUID
    scheduled_at: datetime


class SessionUpdate(BaseModel):
    """Update session status."""
    status: str = Field(..., pattern=r"^(scheduled|in_progress|completed|cancelled|no_show)$")
    ai_summary: str | None = None


class SessionResponse(BaseModel):
    """Counselor session response."""
    counselor_session_id: uuid.UUID
    student_id: uuid.UUID
    counselor_id: uuid.UUID
    scheduled_at: datetime
    status: str
    ai_summary: str | None = None
    created_at: datetime
    student_name: str | None = None

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    """Add a session note."""
    note_text: str = Field(..., min_length=1)


class NoteResponse(BaseModel):
    """Session note response."""
    note_id: uuid.UUID
    counselor_session_id: uuid.UUID
    counselor_id: uuid.UUID
    note_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentCounselorProfile(BaseModel):
    """Detailed student profile for counselor view."""
    student_id: uuid.UUID
    first_name: str
    last_name: str
    age: int | None = None
    gender: str | None = None
    risk_level: str = "green"
    wellness_score: float | None = None
    main_concerns: list[str] = []
    emotional_trend: str = "Stable"
    last_session: str | None = None
    ai_summary: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]


class StudentListResponse(BaseModel):
    students: list[StudentCounselorProfile]
    total: int
