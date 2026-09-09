"""
Kio Counselors Service
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.counselors.schemas import (
    AvailabilityCreate,
    AvailabilitySlot,
    BookRequest,
    BookResponse,
    CounselorDirectoryItem,
    CounselorDirectoryResponse,
    NoteCreate,
    NoteResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    SlotListResponse,
    StudentCounselorProfile,
)
from database.models import (
    CounselorAvailability,
    CounselorNote,
    CounselorProfile,
    CounselorSession,
    ConversationTag,
    StudentProfile,
    User,
)


async def get_counselor_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Get counselor_id from user_id."""
    result = await db.execute(
        select(CounselorProfile.counselor_id).where(CounselorProfile.user_id == user_id)
    )
    counselor_id = result.scalar_one_or_none()
    if not counselor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counselor profile not found")
    return counselor_id


async def list_counselor_students(
    db: AsyncSession, counselor_id: uuid.UUID, tenant_id: uuid.UUID
) -> tuple[list[StudentCounselorProfile], int]:
    """List students that have had sessions with this counselor (or in the same tenant)."""
    # Get students in the same tenant
    query = (
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(User.tenant_id == tenant_id)
        .order_by(
            # High-risk students first
            StudentProfile.risk_level.desc(),
            User.last_name.asc(),
        )
    )

    result = await db.execute(query)
    rows = result.all()

    students = []
    for student, user in rows:
        # Get last session
        session_result = await db.execute(
            select(CounselorSession)
            .where(
                CounselorSession.student_id == student.student_id,
                CounselorSession.counselor_id == counselor_id,
            )
            .order_by(CounselorSession.scheduled_at.desc())
            .limit(1)
        )
        last_session = session_result.scalar_one_or_none()

        students.append(
            StudentCounselorProfile(
                student_id=student.student_id,
                first_name=user.first_name,
                last_name=user.last_name,
                age=student.age,
                gender=student.gender,
                risk_level=student.risk_level or "green",
                wellness_score=float(student.wellness_score) if student.wellness_score else None,
                last_session=(
                    last_session.scheduled_at.strftime("%b %d, %Y") if last_session else None
                ),
                ai_summary=last_session.ai_summary if last_session else None,
            )
        )

    return students, len(students)


async def create_session(
    db: AsyncSession, counselor_id: uuid.UUID, payload: SessionCreate
) -> SessionResponse:
    """Schedule a new counselor session."""
    # Resolve the student first: an unknown id would otherwise surface as a raw
    # foreign-key error (500) instead of a 404.
    student = (await db.execute(
        select(User)
        .join(StudentProfile, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.student_id == payload.student_id)
    )).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Sessions need an end (migration 016). A counselor scheduling directly
    # still gets their configured duration, so their calendar blocks the same
    # amount of time a student booking would have taken.
    profile = (await db.execute(
        select(CounselorProfile).where(CounselorProfile.counselor_id == counselor_id)
    )).scalar_one_or_none()
    duration = timedelta(minutes=profile.session_duration_minutes if profile else 30)

    session = CounselorSession(
        student_id=payload.student_id,
        counselor_id=counselor_id,
        scheduled_at=payload.scheduled_at,
        ends_at=payload.scheduled_at + duration,
    )
    db.add(session)
    try:
        await db.flush()
    except IntegrityError as exc:
        # The overlap constraint applies to counselor-scheduled sessions too:
        # double-booking is double-booking whoever initiated it.
        await db.rollback()
        if "excl_counselor_session_overlap" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That time overlaps a session you already have.",
            ) from exc
        raise
    await db.refresh(session)

    result = SessionResponse.model_validate(session)
    result.student_name = f"{student.first_name} {student.last_name}".strip()
    return result


async def list_sessions(
    db: AsyncSession,
    counselor_id: uuid.UUID,
    status_filter: str | None = None,
) -> tuple[list[SessionResponse], int]:
    """List counselor sessions."""
    # Joined to the student's user row so the caller gets a name to display --
    # counselor_sessions only stores student_id, and a session list showing bare
    # UUIDs is useless in the UI.
    query = (
        select(CounselorSession, User)
        .join(StudentProfile, CounselorSession.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(CounselorSession.counselor_id == counselor_id)
    )
    count_query = (
        select(func.count())
        .select_from(CounselorSession)
        .where(CounselorSession.counselor_id == counselor_id)
    )

    if status_filter:
        query = query.where(CounselorSession.status == status_filter)
        count_query = count_query.where(CounselorSession.status == status_filter)

    query = query.order_by(CounselorSession.scheduled_at.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    rows = result.all()

    sessions = []
    for session, user in rows:
        item = SessionResponse.model_validate(session)
        item.student_name = f"{user.first_name} {user.last_name}".strip()
        sessions.append(item)

    return sessions, total


async def update_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    counselor_id: uuid.UUID,
    payload: SessionUpdate,
) -> SessionResponse:
    """Update session status."""
    result = await db.execute(
        select(CounselorSession).where(
            CounselorSession.counselor_session_id == session_id,
            CounselorSession.counselor_id == counselor_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)

    await db.flush()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


async def add_session_note(
    db: AsyncSession,
    session_id: uuid.UUID,
    counselor_id: uuid.UUID,
    payload: NoteCreate,
) -> NoteResponse:
    """Add a note to a counselor session."""
    # Verify session ownership
    result = await db.execute(
        select(CounselorSession).where(
            CounselorSession.counselor_session_id == session_id,
            CounselorSession.counselor_id == counselor_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    note = CounselorNote(
        counselor_session_id=session_id,
        counselor_id=counselor_id,
        note_text=payload.note_text,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return NoteResponse.model_validate(note)


async def list_session_notes(
    db: AsyncSession, session_id: uuid.UUID, counselor_id: uuid.UUID
) -> list[NoteResponse]:
    """Get notes for a session."""
    result = await db.execute(
        select(CounselorNote)
        .where(
            CounselorNote.counselor_session_id == session_id,
            CounselorNote.counselor_id == counselor_id,
        )
        .order_by(CounselorNote.created_at.asc())
    )
    notes = result.scalars().all()
    return [NoteResponse.model_validate(n) for n in notes]


# -------------------------------------------------------------------
# Platform-wide directory & booking (Phase 5)
# -------------------------------------------------------------------

_MAX_DIRECTORY_SLOTS = 5


async def _open_slots_for(
    db: AsyncSession, counselor_id: uuid.UUID, limit: int | None = None
) -> list[CounselorAvailability]:
    query = (
        select(CounselorAvailability)
        .where(
            CounselorAvailability.counselor_id == counselor_id,
            CounselorAvailability.is_booked == False,  # noqa: E712
            CounselorAvailability.start_at > datetime.now(timezone.utc),
        )
        .order_by(CounselorAvailability.start_at.asc())
    )
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_directory(db: AsyncSession) -> CounselorDirectoryResponse:
    """
    List every active, verified, available counselor platform-wide.
    Counselors belong to the Kio platform, not a school -- no tenant filter.
    """
    result = await db.execute(
        select(CounselorProfile, User)
        .join(User, CounselorProfile.user_id == User.user_id)
        .where(
            User.is_active == True,  # noqa: E712
            CounselorProfile.is_verified == True,  # noqa: E712
            CounselorProfile.is_available == True,  # noqa: E712
        )
        .order_by(CounselorProfile.rating.desc().nullslast(), User.last_name.asc())
    )
    rows = result.all()

    items: list[CounselorDirectoryItem] = []
    for counselor, user in rows:
        slots = await _open_slots_for(db, counselor.counselor_id, _MAX_DIRECTORY_SLOTS)
        items.append(
            CounselorDirectoryItem(
                counselor_id=counselor.counselor_id,
                name=f"{user.first_name} {user.last_name}",
                photo=user.profile_image,
                bio=counselor.bio,
                qualification=counselor.qualification,
                specializations=counselor.specializations or [],
                languages=counselor.languages or [],
                experience_years=counselor.experience_years,
                rating=float(counselor.rating) if counselor.rating is not None else None,
                next_slots=[AvailabilitySlot.model_validate(s) for s in slots],
            )
        )

    return CounselorDirectoryResponse(counselors=items, total=len(items))


async def get_open_slots(db: AsyncSession, counselor_id: uuid.UUID) -> SlotListResponse:
    """List a counselor's open (unbooked, future) slots."""
    slots = await _open_slots_for(db, counselor_id)
    return SlotListResponse(
        counselor_id=counselor_id,
        slots=[AvailabilitySlot.model_validate(s) for s in slots],
    )


async def add_availability(
    db: AsyncSession, counselor_id: uuid.UUID, payload: AvailabilityCreate
) -> AvailabilitySlot:
    """Counselor offers a new bookable slot."""
    if payload.end_at <= payload.start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Slot end must be after its start.",
        )
    slot = CounselorAvailability(
        slot_id=uuid.uuid4(),
        counselor_id=counselor_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
    db.add(slot)
    await db.flush()
    await db.refresh(slot)
    return AvailabilitySlot.model_validate(slot)


async def delete_availability(
    db: AsyncSession, counselor_id: uuid.UUID, slot_id: uuid.UUID
) -> None:
    """Remove one of the counselor's own slots (only if not booked)."""
    result = await db.execute(
        select(CounselorAvailability).where(
            CounselorAvailability.slot_id == slot_id,
            CounselorAvailability.counselor_id == counselor_id,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    if slot.is_booked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked and cannot be removed.",
        )
    await db.delete(slot)
    await db.flush()


async def list_my_availability(db: AsyncSession, counselor_id: uuid.UUID) -> SlotListResponse:
    """All of a counselor's own upcoming slots (booked + open) for management."""
    result = await db.execute(
        select(CounselorAvailability)
        .where(
            CounselorAvailability.counselor_id == counselor_id,
            CounselorAvailability.start_at > datetime.now(timezone.utc),
        )
        .order_by(CounselorAvailability.start_at.asc())
    )
    slots = result.scalars().all()
    return SlotListResponse(
        counselor_id=counselor_id,
        slots=[AvailabilitySlot.model_validate(s) for s in slots],
    )


async def book_slot(
    db: AsyncSession, student_id: uuid.UUID, payload: BookRequest
) -> BookResponse:
    """
    Student books an open counselor slot (platform-wide, cross-tenant allowed).
    Row-locks the slot so two students cannot book the same time.
    """
    result = await db.execute(
        select(CounselorAvailability)
        .where(CounselorAvailability.slot_id == payload.slot_id)
        .with_for_update()
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    if slot.is_booked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sorry, that time was just booked. Please pick another slot.",
        )
    if slot.start_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That slot is in the past.",
        )

    slot.is_booked = True

    session = CounselorSession(
        counselor_session_id=uuid.uuid4(),
        student_id=student_id,
        counselor_id=slot.counselor_id,
        scheduled_at=slot.start_at,
        # The legacy slot already carries its own end; use it rather than the
        # counselor's current duration, so a slot booked under the old model
        # occupies exactly the time it advertised.
        ends_at=slot.end_at,
        status="scheduled",
    )
    db.add(session)
    await db.flush()

    # Counselor name for the confirmation
    name_result = await db.execute(
        select(User.first_name, User.last_name)
        .join(CounselorProfile, CounselorProfile.user_id == User.user_id)
        .where(CounselorProfile.counselor_id == slot.counselor_id)
    )
    row = name_result.one_or_none()
    counselor_name = f"{row[0]} {row[1]}" if row else "your counselor"

    return BookResponse(
        counselor_session_id=session.counselor_session_id,
        counselor_id=slot.counselor_id,
        counselor_name=counselor_name,
        scheduled_at=slot.start_at,
        status=session.status,
    )
