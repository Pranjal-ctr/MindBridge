"""
Kio Counselors Router
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import get_student_id_for_user
from app.dependencies import CurrentTenant, CurrentUser, require_role
from app.counselors.schemas import (
    AvailabilityCreate,
    AvailabilitySearchResponse,
    AvailabilitySlot,
    BookRequest,
    BookResponse,
    CancelRequest,
    ExceptionCreate,
    ExceptionListResponse,
    ExceptionResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
    SessionSettingsResponse,
    SessionSettingsUpdate,
    CounselorDirectoryResponse,
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
    SlotListResponse,
    StudentListResponse,
)
from app.counselors.scheduling import (
    book_session,
    cancel_session,
    create_exception,
    create_schedule,
    delete_exception,
    delete_schedule,
    get_settings,
    list_exceptions,
    list_schedules,
    search_availability,
    update_schedule,
    update_settings,
)
from app.counselors.service import (
    add_availability,
    add_session_note,
    book_slot,
    create_session,
    delete_availability,
    get_counselor_id,
    get_open_slots,
    list_counselor_students,
    list_directory,
    list_my_availability,
    list_session_notes,
    list_sessions,
    update_session,
)
from database.session import get_db

router = APIRouter()


def _as_utc(value: datetime) -> datetime:
    """
    Treat a naive query datetime as UTC.

    Clients are asked for UTC; a missing offset is far more likely to be a
    formatting slip than a claim about the server's local zone, and reading it
    as server-local would make results depend on where Kio is hosted.
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# -------------------------------------------------------------------
# Platform-wide directory & booking (students/parents)
# -------------------------------------------------------------------

@router.get(
    "/directory",
    response_model=CounselorDirectoryResponse,
    dependencies=[Depends(require_role("student", "parent", "admin"))],
)
async def get_directory(db: Annotated[AsyncSession, Depends(get_db)]):
    """Every active, verified counselor platform-wide. Bookable by any student/parent."""
    return await list_directory(db)


@router.get(
    "/{counselor_id}/slots",
    response_model=SlotListResponse,
    dependencies=[Depends(require_role("student", "parent", "admin"))],
)
async def get_slots(
    counselor_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """A counselor's open, upcoming slots."""
    return await get_open_slots(db, counselor_id)


@router.post(
    "/book",
    response_model=BookResponse,
    status_code=201,
    dependencies=[Depends(require_role("student", "parent"))],
)
async def book_counselor(
    payload: BookRequest,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Book a counseling session (platform-wide).

    Preferred form names `counselor_id` + `starts_at`, revalidated against the
    availability engine inside the booking transaction. The legacy `slot_id`
    form still works against the deprecated pre-generated slot table.

    Students book for themselves. Parents book on behalf of a linked child and
    must supply `student_id`; the link is verified before anything is written.
    """
    from app.parents.service import verify_parent_child_link

    if current_user.role == "parent":
        if payload.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select which child this session is for.",
            )
        await verify_parent_child_link(db, current_user.user_id, payload.student_id)
        student_id = payload.student_id
    else:
        # A student's own profile always wins; a supplied student_id is ignored
        # so nobody can book a session onto someone else's record.
        student_id = await get_student_id_for_user(db, current_user.user_id)

    # Students and parents run the identical booking path from here: one engine,
    # one set of validations, one place where a race can be lost.
    if payload.counselor_id is not None and payload.starts_at is not None:
        return await book_session(
            db,
            student_id=student_id,
            counselor_id=payload.counselor_id,
            starts_at=_as_utc(payload.starts_at),
            booked_by_user_id=current_user.user_id,
            request=request,
        )

    return await book_slot(db, student_id, payload)


# -------------------------------------------------------------------
# Counselor: manage own availability
# -------------------------------------------------------------------

@router.get(
    "/availability",
    response_model=SlotListResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def my_availability(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List the current counselor's upcoming slots."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await list_my_availability(db, counselor_id)


@router.post(
    "/availability",
    response_model=AvailabilitySlot,
    status_code=201,
    dependencies=[Depends(require_role("counselor"))],
)
async def create_availability(
    payload: AvailabilityCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Offer a new bookable slot."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await add_availability(db, counselor_id, payload)


@router.delete(
    "/availability/{slot_id}",
    status_code=204,
    dependencies=[Depends(require_role("counselor"))],
)
async def remove_availability(
    slot_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove one of the counselor's own (unbooked) slots."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    await delete_availability(db, counselor_id, slot_id)


@router.get(
    "/students",
    response_model=StudentListResponse,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def get_students(
    current_user: CurrentUser,
    tenant_id: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List students in the counselor's tenant with risk profiles."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    students, total = await list_counselor_students(db, counselor_id, tenant_id)
    return StudentListResponse(students=students, total=total)


@router.get(
    "/students/{student_id}/weekly-report",
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def student_weekly_report(
    student_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """This week's AI summary written for the counselor (cached per ISO week)."""
    from fastapi import HTTPException

    from app.intelligence.reports import get_weekly_report
    from app.wellness.schemas import weekly_report_response
    from database.models import StudentProfile
    from sqlalchemy import select

    exists = (await db.execute(
        select(StudentProfile.student_id).where(StudentProfile.student_id == student_id)
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Student not found")

    report = await get_weekly_report(db, student_id, "counselor")
    return weekly_report_response(report)


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def schedule_session(
    payload: SessionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Schedule a new counselor session with a student."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await create_session(db, counselor_id, payload)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def get_sessions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
):
    """List the counselor's sessions."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    sessions, total = await list_sessions(db, counselor_id, status)
    return SessionListResponse(sessions=sessions, total=total)


@router.put(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def update_session_endpoint(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a session's status or add AI summary."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await update_session(db, session_id, counselor_id, payload)


@router.post(
    "/sessions/{session_id}/notes",
    response_model=NoteResponse,
    status_code=201,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def add_note(
    session_id: uuid.UUID,
    payload: NoteCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a note to a counselor session."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await add_session_note(db, session_id, counselor_id, payload)


@router.get(
    "/sessions/{session_id}/notes",
    response_model=NoteListResponse,
    dependencies=[Depends(require_role("counselor", "admin"))],
)
async def get_notes(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get notes for a specific session."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    notes = await list_session_notes(db, session_id, counselor_id)
    return NoteListResponse(notes=notes)


# ===================================================================
# Availability engine (migration 016)
#
# The endpoints above that read counselor_availability are deprecated: they
# serve pre-generated slot rows, which the engine replaces with schedules
# expanded on demand. They keep working so existing clients are not broken.
# ===================================================================


@router.get(
    "/availability/search",
    response_model=AvailabilitySearchResponse,
    dependencies=[Depends(require_role("student", "parent", "admin"))],
    summary="Find bookable slots in a time window",
)
async def search_slots(
    db: Annotated[AsyncSession, Depends(get_db)],
    window_start: datetime = Query(..., description="Window start, UTC (ISO 8601)"),
    window_end: datetime = Query(..., description="Window end, UTC (ISO 8601)"),
    counselor_id: uuid.UUID | None = Query(
        None, description="Omit for 'any counselor is fine'."
    ),
    duration_minutes: int | None = Query(
        None, ge=15, le=180, description="Defaults to each counselor's own setting."
    ),
    timezone_name: str = Query(
        "Asia/Kolkata", alias="timezone", description="Zone for the display_* fields."
    ),
    limit: int | None = Query(None, ge=1, le=200),
):
    """
    Concrete bookable slots, computed from recurring schedules.

    Time-first discovery: the caller says when they want a session and gets the
    counselors who are genuinely free then. Slots already taken, outside the
    working pattern, on a day off, or in the past never appear.
    """
    return await search_availability(
        db,
        _as_utc(window_start),
        _as_utc(window_end),
        counselor_id=counselor_id,
        duration_minutes=duration_minutes,
        display_timezone=timezone_name,
        limit=limit,
    )


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=BookResponse,
    dependencies=[Depends(require_role("student", "parent", "counselor", "admin"))],
    summary="Cancel a booked session",
)
async def cancel_booked_session(
    session_id: uuid.UUID,
    payload: CancelRequest,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Cancel a session and return the time to the counselor's availability.

    Who may cancel is derived from the database -- the student it belongs to, a
    linked parent, the counselor taking it, or an admin -- never from ids in
    the request body.
    """
    return await cancel_session(
        db,
        session_id=session_id,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
        reason=payload.reason,
        request=request,
    )


# -------------------------------------------------------------------
# Counselor: recurring schedule, exceptions and session settings
# -------------------------------------------------------------------


@router.get(
    "/schedules",
    response_model=ScheduleListResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def my_schedules(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """The signed-in counselor's recurring weekly availability."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await list_schedules(db, counselor_id)


@router.post(
    "/schedules",
    response_model=ScheduleResponse,
    status_code=201,
    dependencies=[Depends(require_role("counselor"))],
)
async def add_schedule(
    payload: ScheduleCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a recurring working interval. End at or before start means overnight."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await create_schedule(db, counselor_id, payload)


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def edit_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduleUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Edit one of your own schedules. Another counselor's is simply not found."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await update_schedule(db, counselor_id, schedule_id, payload)


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    dependencies=[Depends(require_role("counselor"))],
)
async def remove_schedule(
    schedule_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove a recurring interval. Sessions already booked are unaffected."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    await delete_schedule(db, counselor_id, schedule_id)


@router.get(
    "/exceptions",
    response_model=ExceptionListResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def my_exceptions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    upcoming_only: bool = Query(True),
):
    """Time off and one-off extra availability."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await list_exceptions(db, counselor_id, upcoming_only=upcoming_only)


@router.post(
    "/exceptions",
    response_model=ExceptionResponse,
    status_code=201,
    dependencies=[Depends(require_role("counselor"))],
)
async def add_exception(
    payload: ExceptionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add time off (omit both times for a whole day) or extra availability."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await create_exception(db, counselor_id, payload)


@router.delete(
    "/exceptions/{exception_id}",
    status_code=204,
    dependencies=[Depends(require_role("counselor"))],
)
async def remove_exception(
    exception_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove an exception, restoring the recurring pattern for that date."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    await delete_exception(db, counselor_id, exception_id)


@router.get(
    "/settings",
    response_model=SessionSettingsResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def my_settings(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Session length, buffer, and the timezone your hours are stated in."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await get_settings(db, counselor_id)


@router.put(
    "/settings",
    response_model=SessionSettingsResponse,
    dependencies=[Depends(require_role("counselor"))],
)
async def edit_settings(
    payload: SessionSettingsUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change session length, buffer or timezone."""
    counselor_id = await get_counselor_id(db, current_user.user_id)
    return await update_settings(db, counselor_id, payload)
