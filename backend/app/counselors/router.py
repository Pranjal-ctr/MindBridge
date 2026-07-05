"""
MindBridge Counselors Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentTenant, CurrentUser, require_role
from app.counselors.schemas import (
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
    StudentListResponse,
)
from app.counselors.service import (
    add_session_note,
    create_session,
    get_counselor_id,
    list_counselor_students,
    list_session_notes,
    list_sessions,
    update_session,
)
from database.session import get_db

router = APIRouter()


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
