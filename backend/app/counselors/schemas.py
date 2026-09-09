"""
Kio Counselors Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


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


# -------------------------------------------------------------------
# Platform-wide directory & booking (Phase 5)
# -------------------------------------------------------------------

class AvailabilitySlot(BaseModel):
    """A bookable counselor time slot."""
    slot_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    is_booked: bool = False

    model_config = {"from_attributes": True}


class SlotListResponse(BaseModel):
    counselor_id: uuid.UUID
    slots: list[AvailabilitySlot]


class CounselorDirectoryItem(BaseModel):
    """A counselor as shown on the platform-wide Book Counselling page."""
    counselor_id: uuid.UUID
    name: str
    photo: str | None = None
    bio: str | None = None
    qualification: str | None = None
    specializations: list[str] = []
    languages: list[str] = []
    experience_years: int | None = None
    rating: float | None = None
    next_slots: list[AvailabilitySlot] = []


class CounselorDirectoryResponse(BaseModel):
    counselors: list[CounselorDirectoryItem]
    total: int


class AvailabilityCreate(BaseModel):
    """Counselor offers a bookable slot."""
    start_at: datetime
    end_at: datetime


class BookRequest(BaseModel):
    """
    Book a session.

    Two shapes are accepted. The current one names the counselor and the exact
    instant: the availability engine derives slots rather than storing them, so
    there is no slot row to point at. The legacy `slot_id` form still works
    against the deprecated `counselor_availability` table so existing clients
    keep booking while they migrate.

    Students book for themselves and leave `student_id` unset. Parents must name
    which linked child the session is for.
    """

    slot_id: uuid.UUID | None = Field(
        None, description="Deprecated. Legacy pre-generated slot."
    )
    counselor_id: uuid.UUID | None = Field(None, description="With `starts_at`.")
    starts_at: datetime | None = Field(
        None, description="Slot start, UTC. Must match a currently bookable slot."
    )
    student_id: uuid.UUID | None = Field(
        None, description="Required for parents; ignored for students."
    )

    @model_validator(mode="after")
    def _one_booking_mode(self) -> "BookRequest":
        engine_mode = self.counselor_id is not None and self.starts_at is not None
        if engine_mode == (self.slot_id is not None):
            raise ValueError(
                "Provide either counselor_id + starts_at, or a legacy slot_id."
            )
        return self


class CancelRequest(BaseModel):
    """Cancel a booked session."""

    reason: str | None = Field(None, max_length=500)


# -------------------------------------------------------------------
# Recurring availability (migration 016)
# -------------------------------------------------------------------


class ScheduleBase(BaseModel):
    """
    One recurring weekly working interval, in the counselor's own timezone.

    `end_time` at or before `start_time` means the interval runs past midnight:
    Monday 17:00-01:00 is Monday evening through Tuesday 01:00. It is not
    rejected as an inverted range, which is why there is no start < end check.
    """

    day_of_week: int = Field(..., ge=0, le=6, description="0 = Monday .. 6 = Sunday")
    start_time: time
    end_time: time
    is_active: bool = True
    effective_from: date | None = None
    effective_until: date | None = None

    @model_validator(mode="after")
    def _check(self) -> "ScheduleBase":
        if self.start_time == self.end_time:
            raise ValueError("Start and end cannot be the same time.")
        if (
            self.effective_from
            and self.effective_until
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until cannot be before effective_from.")
        return self


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    """Partial update; only supplied fields change."""

    day_of_week: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None
    effective_from: date | None = None
    effective_until: date | None = None


class ScheduleResponse(ScheduleBase):
    schedule_id: uuid.UUID
    counselor_id: uuid.UUID
    crosses_midnight: bool = False

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]
    timezone: str


class ExceptionCreate(BaseModel):
    """
    A dated override. Omit both times for a whole day off.

    `is_available` True adds availability the recurring schedule does not
    cover; False is time off. Additional availability must name a window --
    "available all day" has no defensible meaning against a working pattern.
    """

    exception_date: date
    start_time: time | None = None
    end_time: time | None = None
    is_available: bool = False
    reason: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def _check(self) -> "ExceptionCreate":
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("Provide both start_time and end_time, or neither.")
        if self.is_available and self.start_time is None:
            raise ValueError("Additional availability needs a start and end time.")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time == self.end_time
        ):
            raise ValueError("Start and end cannot be the same time.")
        return self


class ExceptionResponse(BaseModel):
    exception_id: uuid.UUID
    counselor_id: uuid.UUID
    exception_date: date
    start_time: time | None
    end_time: time | None
    is_available: bool
    reason: str | None

    model_config = {"from_attributes": True}


class ExceptionListResponse(BaseModel):
    exceptions: list[ExceptionResponse]
    timezone: str


class SessionSettingsResponse(BaseModel):
    """How long sessions are, how far apart, and in whose timezone."""

    session_duration_minutes: int
    buffer_minutes: int
    timezone: str

    model_config = {"from_attributes": True}


class SessionSettingsUpdate(BaseModel):
    session_duration_minutes: int | None = Field(None, description="30, 45 or 60")
    buffer_minutes: int | None = Field(None, description="0, 5, 10 or 15")
    timezone: str | None = Field(None, max_length=64, description="IANA name")

    @model_validator(mode="after")
    def _check(self) -> "SessionSettingsUpdate":
        if self.session_duration_minutes is not None and self.session_duration_minutes not in (
            30,
            45,
            60,
        ):
            raise ValueError("Session duration must be 30, 45 or 60 minutes.")
        if self.buffer_minutes is not None and self.buffer_minutes not in (0, 5, 10, 15):
            raise ValueError("Buffer must be 0, 5, 10 or 15 minutes.")
        return self


class AvailableSlot(BaseModel):
    """
    A concrete bookable slot.

    `start`/`end` are UTC and are what the booking endpoint expects back.
    `display_*` are pre-formatted in `timezone` so every client renders the
    same wall-clock time regardless of the viewer's device settings.
    """

    counselor_id: uuid.UUID
    counselor_name: str
    start: datetime
    end: datetime
    duration_minutes: int
    display_start: str
    display_end: str
    display_date: str


class AvailabilitySearchResponse(BaseModel):
    timezone: str
    window_start: datetime
    window_end: datetime
    slots: list[AvailableSlot]
    counselors_considered: int


class BookResponse(BaseModel):
    counselor_session_id: uuid.UUID
    counselor_id: uuid.UUID
    counselor_name: str
    scheduled_at: datetime
    status: str
    message: str = "Session booked"
