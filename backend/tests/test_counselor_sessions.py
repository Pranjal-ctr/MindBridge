"""
Counselor session lifecycle: scheduling, status updates and session notes.

Covers the endpoints the counselor dashboard drives, and in particular that a
session list carries a displayable `student_name` — the table only stores
student_id, so without the join the UI has nothing to render.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.utils import create_access_token, hash_password
from database.models import CounselorProfile, StudentProfile, Tenant, User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def counselor(db_session, test_tenant: Tenant) -> CounselorProfile:
    """A verified counselor in the same tenant as the test student."""
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"counselor_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="counselor",
        first_name="Casey",
        last_name="Counsel",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    profile = CounselorProfile(
        counselor_id=uuid.uuid4(),
        user_id=user.user_id,
        bio="Test counselor",
        qualification="LCSW",
        specializations=["Anxiety"],
        languages=["English"],
        experience_years=5,
        is_verified=True,
        is_available=True,
    )
    db_session.add(profile)
    await db_session.flush()
    profile.user = user  # convenience for the auth-header fixture
    return profile


@pytest_asyncio.fixture
async def counselor_headers(db_session, counselor: CounselorProfile) -> dict[str, str]:
    user = await db_session.get(User, counselor.user_id)
    token = create_access_token({
        "sub": str(user.user_id),
        "tenant_id": str(user.tenant_id),
        "role": "counselor",
    })
    return {"Authorization": f"Bearer {token}"}


def in_hours(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# -------------------------------------------------------------------
# Scheduling
# -------------------------------------------------------------------

async def test_schedule_session_returns_student_name(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session
):
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()

    resp = await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "scheduled"
    assert body["student_name"] == "Test Student"


async def test_schedule_session_unknown_student_is_404(client: AsyncClient, counselor_headers):
    resp = await client.post(
        "/counselors/sessions",
        json={"student_id": str(uuid.uuid4()), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    assert resp.status_code == 404


async def test_students_cannot_schedule_sessions(
    client: AsyncClient, student_auth_headers, test_student_user: User
):
    resp = await client.post(
        "/counselors/sessions",
        json={"student_id": str(uuid.uuid4()), "scheduled_at": in_hours(24)},
        headers=student_auth_headers,
    )
    assert resp.status_code == 403


# -------------------------------------------------------------------
# Listing
# -------------------------------------------------------------------

async def test_session_list_carries_student_names(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session
):
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()

    for hours in (24, 48):
        await client.post(
            "/counselors/sessions",
            json={"student_id": str(student.student_id), "scheduled_at": in_hours(hours)},
            headers=counselor_headers,
        )

    resp = await client.get("/counselors/sessions", headers=counselor_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["sessions"]) == 2
    # The regression this guards: student_name was previously always null.
    assert all(s["student_name"] == "Test Student" for s in body["sessions"])


async def test_session_list_is_scoped_to_the_counselor(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session, test_tenant
):
    """A second counselor must not see the first counselor's sessions."""
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()
    await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )

    other_user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"other_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("x"),
        role="counselor",
        first_name="Other",
        last_name="Counselor",
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(CounselorProfile(
        counselor_id=uuid.uuid4(), user_id=other_user.user_id, is_verified=True, is_available=True
    ))
    await db_session.flush()

    token = create_access_token({
        "sub": str(other_user.user_id),
        "tenant_id": str(other_user.tenant_id),
        "role": "counselor",
    })
    resp = await client.get(
        "/counselors/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_session_list_filters_by_status(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session
):
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()
    created = await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    session_id = created.json()["counselor_session_id"]

    await client.put(
        f"/counselors/sessions/{session_id}",
        json={"status": "completed"},
        headers=counselor_headers,
    )

    completed = await client.get(
        "/counselors/sessions?status=completed", headers=counselor_headers
    )
    assert completed.json()["total"] == 1

    scheduled = await client.get(
        "/counselors/sessions?status=scheduled", headers=counselor_headers
    )
    assert scheduled.json()["total"] == 0


# -------------------------------------------------------------------
# Notes
# -------------------------------------------------------------------

async def test_notes_round_trip(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session
):
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()
    created = await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    session_id = created.json()["counselor_session_id"]

    empty = await client.get(
        f"/counselors/sessions/{session_id}/notes", headers=counselor_headers
    )
    assert empty.json()["notes"] == []

    added = await client.post(
        f"/counselors/sessions/{session_id}/notes",
        json={"note_text": "Discussed exam stress; agreed on a sleep routine."},
        headers=counselor_headers,
    )
    assert added.status_code == 201

    listed = await client.get(
        f"/counselors/sessions/{session_id}/notes", headers=counselor_headers
    )
    notes = listed.json()["notes"]
    assert len(notes) == 1
    assert "exam stress" in notes[0]["note_text"]


async def test_empty_note_is_rejected(
    client: AsyncClient, counselor_headers, test_student_user: User, db_session
):
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()
    created = await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    session_id = created.json()["counselor_session_id"]

    resp = await client.post(
        f"/counselors/sessions/{session_id}/notes",
        json={"note_text": ""},
        headers=counselor_headers,
    )
    assert resp.status_code == 422


async def test_students_cannot_read_session_notes(
    client: AsyncClient, counselor_headers, student_auth_headers, test_student_user: User, db_session
):
    """Clinical notes are staff-only, including for the student they describe."""
    student = (await db_session.execute(
        StudentProfile.__table__.select().where(StudentProfile.user_id == test_student_user.user_id)
    )).first()
    created = await client.post(
        "/counselors/sessions",
        json={"student_id": str(student.student_id), "scheduled_at": in_hours(24)},
        headers=counselor_headers,
    )
    session_id = created.json()["counselor_session_id"]

    resp = await client.get(
        f"/counselors/sessions/{session_id}/notes", headers=student_auth_headers
    )
    assert resp.status_code == 403
