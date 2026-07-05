"""
MindBridge Counselors Service
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.counselors.schemas import (
    NoteCreate,
    NoteResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    StudentCounselorProfile,
)
from database.models import (
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
    session = CounselorSession(
        student_id=payload.student_id,
        counselor_id=counselor_id,
        scheduled_at=payload.scheduled_at,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


async def list_sessions(
    db: AsyncSession,
    counselor_id: uuid.UUID,
    status_filter: str | None = None,
) -> tuple[list[SessionResponse], int]:
    """List counselor sessions."""
    query = select(CounselorSession).where(CounselorSession.counselor_id == counselor_id)
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
    sessions = result.scalars().all()

    return [SessionResponse.model_validate(s) for s in sessions], total


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
