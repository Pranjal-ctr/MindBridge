"""
Booking against the availability engine: API, authorization and concurrency.

The concurrency test at the bottom uses two real database connections rather
than the shared test session, because a race that both halves observe through
one transaction is not a race.
"""

import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.utils import create_access_token, hash_password
from app.counselors.scheduling import book_session
from database.models import (
    CounselorProfile,
    CounselorSchedule,
    CounselorSession,
    ParentProfile,
    StudentParentLink,
    StudentProfile,
    Tenant,
    User,
)

UTC = timezone.utc


def next_weekday(weekday: int, weeks_ahead: int = 1) -> date:
    """A date safely in the future on the given weekday, avoiding 'today' races."""
    today = datetime.now(UTC).date()
    ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=ahead + 7 * weeks_ahead)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


async def _make_counselor(db, *, verified=True, available=True, tz="UTC", duration=30, buffer=0):
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name="Kio Platform",
        tenant_type="organization",
        school_code=f"PLAT{uuid.uuid4().hex[:5].upper()}",
        status="active",
    )
    db.add(tenant)
    await db.flush()
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=f"c_{uuid.uuid4().hex[:8]}@kio.ai",
        password_hash=hash_password("x"),
        role="counselor",
        first_name="Dana",
        last_name="Counsel",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    profile = CounselorProfile(
        counselor_id=uuid.uuid4(),
        user_id=user.user_id,
        qualification="LMFT",
        is_verified=verified,
        is_available=available,
        timezone=tz,
        session_duration_minutes=duration,
        buffer_minutes=buffer,
    )
    db.add(profile)
    await db.flush()
    return profile, user


async def _make_student(db, tenant_id):
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"s_{uuid.uuid4().hex[:8]}@kio.ai",
        password_hash=hash_password("x"),
        role="student",
        first_name="Sam",
        last_name="Student",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    profile = StudentProfile(student_id=uuid.uuid4(), user_id=user.user_id)
    db.add(profile)
    await db.flush()
    return profile, user


def headers_for(user: User, role: str) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def working_counselor(db_session):
    """A counselor working 09:00-17:00 UTC every weekday."""
    profile, user = await _make_counselor(db_session)
    for dow in range(7):
        db_session.add(
            CounselorSchedule(
                schedule_id=uuid.uuid4(),
                counselor_id=profile.counselor_id,
                day_of_week=dow,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_active=True,
            )
        )
    await db_session.flush()
    return profile, user


@pytest_asyncio.fixture
async def student(db_session, test_tenant):
    return await _make_student(db_session, test_tenant.tenant_id)


# -------------------------------------------------------------------
# Counselor schedule management
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counselor_creates_and_lists_a_schedule(client, db_session):
    profile, user = await _make_counselor(db_session)
    h = headers_for(user, "counselor")

    created = await client.post(
        "/counselors/schedules",
        headers=h,
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "17:00:00"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["crosses_midnight"] is False

    listed = await client.get("/counselors/schedules", headers=h)
    assert listed.status_code == 200
    assert len(listed.json()["schedules"]) == 1
    assert listed.json()["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_overnight_schedule_is_accepted_and_flagged(client, db_session):
    profile, user = await _make_counselor(db_session)
    created = await client.post(
        "/counselors/schedules",
        headers=headers_for(user, "counselor"),
        json={"day_of_week": 0, "start_time": "17:00:00", "end_time": "01:00:00"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["crosses_midnight"] is True


@pytest.mark.asyncio
async def test_identical_start_and_end_is_rejected(client, db_session):
    profile, user = await _make_counselor(db_session)
    r = await client.post(
        "/counselors/schedules",
        headers=headers_for(user, "counselor"),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "09:00:00"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_counselor_cannot_touch_another_counselors_schedule(client, db_session):
    owner, owner_user = await _make_counselor(db_session)
    intruder, intruder_user = await _make_counselor(db_session)

    created = await client.post(
        "/counselors/schedules",
        headers=headers_for(owner_user, "counselor"),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "17:00:00"},
    )
    schedule_id = created.json()["schedule_id"]

    for method, kwargs in (
        ("patch", {"json": {"is_active": False}}),
        ("delete", {}),
    ):
        r = await getattr(client, method)(
            f"/counselors/schedules/{schedule_id}",
            headers=headers_for(intruder_user, "counselor"),
            **kwargs,
        )
        assert r.status_code == 404, f"{method} leaked another counselor's schedule"


@pytest.mark.asyncio
async def test_students_cannot_manage_schedules(client, student):
    _, user = student
    r = await client.get("/counselors/schedules", headers=headers_for(user, "student"))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_session_settings_round_trip_and_validate(client, db_session):
    profile, user = await _make_counselor(db_session)
    h = headers_for(user, "counselor")

    ok = await client.put(
        "/counselors/settings",
        headers=h,
        json={"session_duration_minutes": 45, "buffer_minutes": 15, "timezone": "UTC"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json() == {
        "session_duration_minutes": 45,
        "buffer_minutes": 15,
        "timezone": "UTC",
    }

    assert (await client.put(
        "/counselors/settings", headers=h, json={"session_duration_minutes": 37}
    )).status_code == 422
    assert (await client.put(
        "/counselors/settings", headers=h, json={"buffer_minutes": 7}
    )).status_code == 422
    assert (await client.put(
        "/counselors/settings", headers=h, json={"timezone": "Mars/Olympus"}
    )).status_code == 422


# -------------------------------------------------------------------
# Availability search
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_slots_from_a_recurring_schedule(
    client, working_counselor, student
):
    profile, _ = working_counselor
    _, student_user = student
    day = next_weekday(0)

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={
            "window_start": at(day, 9).isoformat(),
            "window_end": at(day, 11).isoformat(),
            "timezone": "UTC",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    mine = [s for s in body["slots"] if s["counselor_id"] == str(profile.counselor_id)]
    assert [s["display_start"] for s in mine] == ["9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM"]
    assert mine[0]["duration_minutes"] == 30


@pytest.mark.asyncio
async def test_search_excludes_an_unverified_counselor(client, db_session, student):
    profile, _ = await _make_counselor(db_session, verified=False)
    db_session.add(
        CounselorSchedule(
            schedule_id=uuid.uuid4(),
            counselor_id=profile.counselor_id,
            day_of_week=0,
            start_time=time(9),
            end_time=time(17),
        )
    )
    await db_session.flush()
    _, student_user = student
    day = next_weekday(0)

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 11).isoformat()},
    )
    ids = {s["counselor_id"] for s in r.json()["slots"]}
    assert str(profile.counselor_id) not in ids


@pytest.mark.asyncio
async def test_search_excludes_a_counselor_who_is_unavailable(client, db_session, student):
    profile, _ = await _make_counselor(db_session, available=False)
    db_session.add(
        CounselorSchedule(
            schedule_id=uuid.uuid4(),
            counselor_id=profile.counselor_id,
            day_of_week=0,
            start_time=time(9),
            end_time=time(17),
        )
    )
    await db_session.flush()
    _, student_user = student
    day = next_weekday(0)

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 11).isoformat()},
    )
    ids = {s["counselor_id"] for s in r.json()["slots"]}
    assert str(profile.counselor_id) not in ids


@pytest.mark.asyncio
async def test_a_booked_session_disappears_from_search(client, working_counselor, student):
    profile, _ = working_counselor
    student_profile, student_user = student
    day = next_weekday(0)
    h = headers_for(student_user, "student")

    booked = await client.post(
        "/counselors/book",
        headers=h,
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    assert booked.status_code == 201, booked.text

    r = await client.get(
        "/counselors/availability/search",
        headers=h,
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 11).isoformat()},
    )
    mine = [
        s for s in r.json()["slots"] if s["counselor_id"] == str(profile.counselor_id)
    ]
    assert at(day, 10).isoformat() not in [s["start"].replace("Z", "+00:00") for s in mine]
    assert len(mine) == 3


@pytest.mark.asyncio
async def test_cancelling_returns_the_slot_to_availability(
    client, working_counselor, student
):
    """The old per-slot model never reset is_booked; this must not repeat it."""
    profile, _ = working_counselor
    _, student_user = student
    day = next_weekday(0)
    h = headers_for(student_user, "student")

    booked = await client.post(
        "/counselors/book",
        headers=h,
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    session_id = booked.json()["counselor_session_id"]

    cancelled = await client.post(
        f"/counselors/sessions/{session_id}/cancel", headers=h, json={"reason": "clash"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    r = await client.get(
        "/counselors/availability/search",
        headers=h,
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 11).isoformat()},
    )
    mine = [s for s in r.json()["slots"] if s["counselor_id"] == str(profile.counselor_id)]
    assert len(mine) == 4, "cancelling did not release the slot"


@pytest.mark.asyncio
async def test_completed_session_does_not_block_future_availability(
    client, db_session, working_counselor, student
):
    profile, _ = working_counselor
    student_profile, student_user = student
    past_day = datetime.now(UTC) - timedelta(days=30)
    db_session.add(
        CounselorSession(
            counselor_session_id=uuid.uuid4(),
            student_id=student_profile.student_id,
            counselor_id=profile.counselor_id,
            scheduled_at=past_day,
            ends_at=past_day + timedelta(minutes=30),
            status="completed",
        )
    )
    await db_session.flush()

    day = next_weekday(0)
    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 11).isoformat()},
    )
    mine = [s for s in r.json()["slots"] if s["counselor_id"] == str(profile.counselor_id)]
    assert len(mine) == 4


@pytest.mark.asyncio
async def test_time_off_removes_the_whole_day(client, db_session, working_counselor, student):
    profile, counselor_user = working_counselor
    _, student_user = student
    day = next_weekday(0)

    off = await client.post(
        "/counselors/exceptions",
        headers=headers_for(counselor_user, "counselor"),
        json={"exception_date": day.isoformat(), "reason": "Leave"},
    )
    assert off.status_code == 201, off.text

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={"window_start": at(day, 9).isoformat(), "window_end": at(day, 17).isoformat()},
    )
    mine = [s for s in r.json()["slots"] if s["counselor_id"] == str(profile.counselor_id)]
    assert mine == []


@pytest.mark.asyncio
async def test_partial_time_off_trims_only_that_window(
    client, db_session, working_counselor, student
):
    profile, counselor_user = working_counselor
    _, student_user = student
    day = next_weekday(0)

    await client.post(
        "/counselors/exceptions",
        headers=headers_for(counselor_user, "counselor"),
        json={
            "exception_date": day.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
        },
    )

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={
            "window_start": at(day, 9).isoformat(),
            "window_end": at(day, 12).isoformat(),
            "timezone": "UTC",
        },
    )
    labels = [
        s["display_start"]
        for s in r.json()["slots"]
        if s["counselor_id"] == str(profile.counselor_id)
    ]
    assert labels == ["9:00 AM", "9:30 AM", "11:00 AM", "11:30 AM"]


@pytest.mark.asyncio
async def test_additional_availability_opens_a_non_working_day(client, db_session, student):
    """A counselor with no recurring Sunday still opens one Sunday morning."""
    profile, counselor_user = await _make_counselor(db_session, tz="UTC")
    db_session.add(
        CounselorSchedule(
            schedule_id=uuid.uuid4(),
            counselor_id=profile.counselor_id,
            day_of_week=0,
            start_time=time(9),
            end_time=time(17),
        )
    )
    await db_session.flush()
    sunday = next_weekday(6)
    _, student_user = student

    await client.post(
        "/counselors/exceptions",
        headers=headers_for(counselor_user, "counselor"),
        json={
            "exception_date": sunday.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "is_available": True,
        },
    )

    r = await client.get(
        "/counselors/availability/search",
        headers=headers_for(student_user, "student"),
        params={
            "window_start": at(sunday, 9).isoformat(),
            "window_end": at(sunday, 12).isoformat(),
            "timezone": "UTC",
        },
    )
    labels = [
        s["display_start"]
        for s in r.json()["slots"]
        if s["counselor_id"] == str(profile.counselor_id)
    ]
    assert labels == ["10:00 AM", "10:30 AM"]


@pytest.mark.asyncio
async def test_all_day_additional_availability_is_rejected(client, db_session):
    profile, user = await _make_counselor(db_session)
    r = await client.post(
        "/counselors/exceptions",
        headers=headers_for(user, "counselor"),
        json={"exception_date": next_weekday(0).isoformat(), "is_available": True},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_window_must_be_ordered_and_bounded(client, student):
    _, student_user = student
    h = headers_for(student_user, "student")
    day = next_weekday(0)

    backwards = await client.get(
        "/counselors/availability/search",
        headers=h,
        params={"window_start": at(day, 11).isoformat(), "window_end": at(day, 9).isoformat()},
    )
    assert backwards.status_code == 422

    far = datetime.now(UTC) + timedelta(days=400)
    beyond = await client.get(
        "/counselors/availability/search",
        headers=h,
        params={
            "window_start": far.isoformat(),
            "window_end": (far + timedelta(hours=2)).isoformat(),
        },
    )
    assert beyond.status_code == 422


# -------------------------------------------------------------------
# Booking
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_books_a_slot(client, working_counselor, student):
    profile, _ = working_counselor
    _, student_user = student
    day = next_weekday(0)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "scheduled"
    assert r.json()["counselor_name"] == "Dana Counsel"


@pytest.mark.asyncio
async def test_booking_a_time_outside_the_schedule_is_refused(
    client, working_counselor, student
):
    profile, _ = working_counselor
    _, student_user = student
    day = next_weekday(0)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 3).isoformat()},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_booking_off_the_slot_grid_is_refused(client, working_counselor, student):
    """10:07 is inside working hours but is not a slot the engine offers."""
    profile, _ = working_counselor
    _, student_user = student
    day = next_weekday(0)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(day, 10, 7).isoformat(),
        },
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_booking_in_the_past_is_refused(client, working_counselor, student):
    profile, _ = working_counselor
    _, student_user = student
    past = datetime.now(UTC) - timedelta(days=3)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": past.isoformat()},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_booking_beyond_the_horizon_is_refused(client, working_counselor, student):
    profile, _ = working_counselor
    _, student_user = student
    far = datetime.now(UTC) + timedelta(days=200)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": far.isoformat()},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_double_booking_the_same_slot_is_a_conflict(
    client, db_session, working_counselor, student, test_tenant
):
    profile, _ = working_counselor
    _, first_user = student
    _, second_user = await _make_student(db_session, test_tenant.tenant_id)
    day = next_weekday(0)
    slot = at(day, 10).isoformat()

    first = await client.post(
        "/counselors/book",
        headers=headers_for(first_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": slot},
    )
    assert first.status_code == 201

    second = await client.post(
        "/counselors/book",
        headers=headers_for(second_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": slot},
    )
    assert second.status_code == 409
    assert "just booked" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_a_partially_overlapping_booking_is_refused(
    client, db_session, working_counselor, student, test_tenant
):
    """
    10:00-10:45 and 10:30-11:00 overlap. Comparing start times alone would
    have let this through, which is the failure mode the spec calls out.
    """
    profile, counselor_user = working_counselor
    await client.put(
        "/counselors/settings",
        headers=headers_for(counselor_user, "counselor"),
        json={"session_duration_minutes": 45},
    )
    _, first_user = student
    _, second_user = await _make_student(db_session, test_tenant.tenant_id)
    day = next_weekday(0)

    first = await client.post(
        "/counselors/book",
        headers=headers_for(first_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 9).isoformat()},
    )
    assert first.status_code == 201

    overlapping = await client.post(
        "/counselors/book",
        headers=headers_for(second_user, "student"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(day, 9, 30).isoformat(),
        },
    )
    assert overlapping.status_code == 409


@pytest.mark.asyncio
async def test_booking_request_needs_exactly_one_mode(client, working_counselor, student):
    profile, _ = working_counselor
    _, student_user = student
    h = headers_for(student_user, "student")

    neither = await client.post("/counselors/book", headers=h, json={})
    assert neither.status_code == 422

    both = await client.post(
        "/counselors/book",
        headers=h,
        json={
            "slot_id": str(uuid.uuid4()),
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(next_weekday(0), 10).isoformat(),
        },
    )
    assert both.status_code == 422


# -------------------------------------------------------------------
# Authorization
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parent_books_for_a_linked_child(
    client, db_session, working_counselor, student, test_tenant
):
    profile, _ = working_counselor
    student_profile, _ = student

    parent_user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"p_{uuid.uuid4().hex[:8]}@kio.ai",
        password_hash=hash_password("x"),
        role="parent",
        first_name="Pat",
        last_name="Parent",
        is_active=True,
    )
    db_session.add(parent_user)
    await db_session.flush()
    parent_profile = ParentProfile(parent_id=uuid.uuid4(), user_id=parent_user.user_id)
    db_session.add(parent_profile)
    await db_session.flush()
    db_session.add(
        StudentParentLink(
            link_id=uuid.uuid4(),
            student_id=student_profile.student_id,
            parent_id=parent_profile.parent_id,
        )
    )
    await db_session.flush()

    day = next_weekday(0)
    r = await client.post(
        "/counselors/book",
        headers=headers_for(parent_user, "parent"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(day, 10).isoformat(),
            "student_id": str(student_profile.student_id),
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_parent_cannot_book_for_an_unlinked_child(
    client, db_session, working_counselor, student, test_tenant
):
    profile, _ = working_counselor
    student_profile, _ = student

    parent_user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"p_{uuid.uuid4().hex[:8]}@kio.ai",
        password_hash=hash_password("x"),
        role="parent",
        first_name="Nope",
        last_name="Parent",
        is_active=True,
    )
    db_session.add(parent_user)
    await db_session.flush()
    db_session.add(ParentProfile(parent_id=uuid.uuid4(), user_id=parent_user.user_id))
    await db_session.flush()

    r = await client.post(
        "/counselors/book",
        headers=headers_for(parent_user, "parent"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(next_weekday(0), 10).isoformat(),
            "student_id": str(student_profile.student_id),
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_parent_must_name_a_child(client, working_counselor, db_session, test_tenant):
    profile, _ = working_counselor
    parent_user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"p_{uuid.uuid4().hex[:8]}@kio.ai",
        password_hash=hash_password("x"),
        role="parent",
        first_name="Pat",
        last_name="Parent",
        is_active=True,
    )
    db_session.add(parent_user)
    await db_session.flush()

    r = await client.post(
        "/counselors/book",
        headers=headers_for(parent_user, "parent"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(next_weekday(0), 10).isoformat(),
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_a_student_cannot_book_onto_someone_elses_record(
    client, db_session, working_counselor, student, test_tenant
):
    """A supplied student_id is ignored for students, never trusted."""
    profile, _ = working_counselor
    _, student_user = student
    victim_profile, _ = await _make_student(db_session, test_tenant.tenant_id)
    day = next_weekday(0)

    r = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={
            "counselor_id": str(profile.counselor_id),
            "starts_at": at(day, 10).isoformat(),
            "student_id": str(victim_profile.student_id),
        },
    )
    assert r.status_code == 201
    booked = await db_session.get(CounselorSession, uuid.UUID(r.json()["counselor_session_id"]))
    assert booked.student_id != victim_profile.student_id


@pytest.mark.asyncio
async def test_an_unrelated_student_cannot_cancel_someone_elses_session(
    client, db_session, working_counselor, student, test_tenant
):
    profile, _ = working_counselor
    _, owner_user = student
    _, other_user = await _make_student(db_session, test_tenant.tenant_id)
    day = next_weekday(0)

    booked = await client.post(
        "/counselors/book",
        headers=headers_for(owner_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    session_id = booked.json()["counselor_session_id"]

    r = await client.post(
        f"/counselors/sessions/{session_id}/cancel",
        headers=headers_for(other_user, "student"),
        json={},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_the_counselor_can_cancel_their_own_session(
    client, working_counselor, student
):
    profile, counselor_user = working_counselor
    _, student_user = student
    day = next_weekday(0)

    booked = await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    r = await client.post(
        f"/counselors/sessions/{booked.json()['counselor_session_id']}/cancel",
        headers=headers_for(counselor_user, "counselor"),
        json={"reason": "unwell"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cancelling_twice_is_a_conflict(client, working_counselor, student):
    profile, _ = working_counselor
    _, student_user = student
    h = headers_for(student_user, "student")
    day = next_weekday(0)

    booked = await client.post(
        "/counselors/book",
        headers=h,
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )
    session_id = booked.json()["counselor_session_id"]

    assert (await client.post(
        f"/counselors/sessions/{session_id}/cancel", headers=h, json={}
    )).status_code == 200
    assert (await client.post(
        f"/counselors/sessions/{session_id}/cancel", headers=h, json={}
    )).status_code == 409


@pytest.mark.asyncio
async def test_booking_notifies_the_student_and_the_counselor(
    client, db_session, working_counselor, student
):
    from database.models import Notification

    profile, counselor_user = working_counselor
    _, student_user = student
    day = next_weekday(0)

    await client.post(
        "/counselors/book",
        headers=headers_for(student_user, "student"),
        json={"counselor_id": str(profile.counselor_id), "starts_at": at(day, 10).isoformat()},
    )

    from sqlalchemy import select

    rows = (
        await db_session.execute(
            select(Notification.user_id).where(
                Notification.user_id.in_([counselor_user.user_id, student_user.user_id])
            )
        )
    ).scalars().all()
    assert counselor_user.user_id in rows
    assert student_user.user_id in rows


# -------------------------------------------------------------------
# Concurrency -- two real connections
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simultaneous_bookings_for_one_slot_yield_exactly_one_winner():
    """
    Two students click Book on the same slot at the same moment.

    Uses two independent sessions, committed, because the shared test session
    would serialise the two halves through one transaction and prove nothing.
    """
    from tests.conftest import test_session_factory

    created_ids: list[uuid.UUID] = []
    counselor_id = None
    student_a = student_b = None
    user_a = user_b = None

    async with test_session_factory() as setup:
        profile, _ = await _make_counselor(setup, tz="UTC")
        counselor_id = profile.counselor_id
        setup.add(
            CounselorSchedule(
                schedule_id=uuid.uuid4(),
                counselor_id=counselor_id,
                day_of_week=next_weekday(0).weekday(),
                start_time=time(9),
                end_time=time(17),
            )
        )
        tenant = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Race School",
            tenant_type="school",
            school_code=f"RACE{uuid.uuid4().hex[:5].upper()}",
            status="active",
        )
        setup.add(tenant)
        await setup.flush()
        a, a_user = await _make_student(setup, tenant.tenant_id)
        b, b_user = await _make_student(setup, tenant.tenant_id)
        student_a, student_b = a.student_id, b.student_id
        # booked_by_user_id is a real foreign key; a random uuid would fail
        # with an integrity error that looks exactly like losing the race.
        user_a, user_b = a_user.user_id, b_user.user_id
        await setup.commit()

    day = next_weekday(0)
    slot = at(day, 10)

    async def attempt(student_id, actor_id):
        async with test_session_factory() as session:
            try:
                result = await book_session(
                    session,
                    student_id=student_id,
                    counselor_id=counselor_id,
                    starts_at=slot,
                    booked_by_user_id=actor_id,
                )
                await session.commit()
                created_ids.append(result.counselor_session_id)
                return "booked"
            except Exception as exc:  # HTTPException(409) or an integrity error
                await session.rollback()
                return f"rejected:{getattr(exc, 'status_code', type(exc).__name__)}"

    try:
        outcomes = await asyncio.gather(
            attempt(student_a, user_a), attempt(student_b, user_b), return_exceptions=False
        )
        assert outcomes.count("booked") == 1, f"expected exactly one winner, got {outcomes}"
        loser = [o for o in outcomes if o != "booked"][0]
        assert "409" in loser or "Integrity" in loser, f"loser failed wrongly: {loser}"

        # And the database holds exactly one live session for that slot.
        async with test_session_factory() as check:
            from sqlalchemy import func, select

            count = (
                await check.execute(
                    select(func.count())
                    .select_from(CounselorSession)
                    .where(
                        CounselorSession.counselor_id == counselor_id,
                        CounselorSession.scheduled_at == slot,
                        CounselorSession.status.not_in(("cancelled", "no_show")),
                    )
                )
            ).scalar()
            assert count == 1
    finally:
        # Committed rows outlive the test session, so clean up explicitly.
        async with test_session_factory() as cleanup:
            from sqlalchemy import delete

            await cleanup.execute(
                delete(CounselorSession).where(CounselorSession.counselor_id == counselor_id)
            )
            await cleanup.execute(
                delete(CounselorSchedule).where(CounselorSchedule.counselor_id == counselor_id)
            )
            await cleanup.commit()
