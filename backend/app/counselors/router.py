"""
Kio Counselors Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import get_student_id_for_user
from app.dependencies import CurrentTenant, CurrentUser, require_role
from app.counselors.schemas import (
    AvailabilityCreate,
    AvailabilitySlot,
    BookRequest,
    BookResponse,
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Book an open counselor slot (platform-wide).

    Students book for themselves. Parents book on behalf of a linked child and
    must supply `student_id`; the link is verified before the slot is taken.
    """
    if current_user.role == "parent":
        from fastapi import HTTPException, status

        from app.parents.service import verify_parent_child_link

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
