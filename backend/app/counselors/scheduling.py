"""
Counselor scheduling: recurring availability, exceptions, settings, booking.

The pure interval maths lives in ``availability.py``; this module owns the
database writes, the authorization checks that surround them, and the booking
transaction that must never produce two overlapping sessions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_audit
from app.counselors.availability import (
    INACTIVE_SESSION_STATUSES,
    crosses_midnight,
    find_available_slots,
    resolve_zone,
)
from app.counselors.schemas import (
    AvailabilitySearchResponse,
    AvailableSlot,
    BookResponse,
    ExceptionCreate,
    ExceptionListResponse,
    ExceptionResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
    SessionSettingsResponse,
    SessionSettingsUpdate,
)
from app.notifications.service import notify_users
from database.models import (
    CounselorProfile,
    CounselorSchedule,
    CounselorScheduleException,
    CounselorSession,
    ParentProfile,
    StudentParentLink,
    StudentProfile,
    User,
)

logger = logging.getLogger(__name__)

# How far ahead a student may book. Not a restriction anyone asked for so much
# as a bound on how much availability we will compute in one request; a year of
# slots is neither useful to a student nor cheap to generate.
MAX_BOOKING_HORIZON_DAYS = 90

# Widest window a single availability query may span.
MAX_SEARCH_WINDOW_DAYS = 14

EXCLUSION_CONSTRAINT = "excl_counselor_session_overlap"


# -------------------------------------------------------------------
# Counselor: recurring schedules
# -------------------------------------------------------------------


async def _counselor_settings(
    db: AsyncSession, counselor_id: uuid.UUID
) -> CounselorProfile:
    result = await db.execute(
        select(CounselorProfile).where(CounselorProfile.counselor_id == counselor_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Counselor not found"
        )
    return profile


def _schedule_response(row: CounselorSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        schedule_id=row.schedule_id,
        counselor_id=row.counselor_id,
        day_of_week=row.day_of_week,
        start_time=row.start_time,
        end_time=row.end_time,
        is_active=row.is_active,
        effective_from=row.effective_from,
        effective_until=row.effective_until,
        crosses_midnight=crosses_midnight(row.start_time, row.end_time),
    )


async def list_schedules(db: AsyncSession, counselor_id: uuid.UUID) -> ScheduleListResponse:
    profile = await _counselor_settings(db, counselor_id)
    rows = (
        await db.execute(
            select(CounselorSchedule)
            .where(CounselorSchedule.counselor_id == counselor_id)
            .order_by(CounselorSchedule.day_of_week, CounselorSchedule.start_time)
        )
    ).scalars().all()
    return ScheduleListResponse(
        schedules=[_schedule_response(r) for r in rows], timezone=profile.timezone
    )


async def create_schedule(
    db: AsyncSession, counselor_id: uuid.UUID, payload: ScheduleCreate
) -> ScheduleResponse:
    await _counselor_settings(db, counselor_id)
    row = CounselorSchedule(
        schedule_id=uuid.uuid4(),
        counselor_id=counselor_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_active=payload.is_active,
        effective_from=payload.effective_from,
        effective_until=payload.effective_until,
    )
    db.add(row)
    await db.flush()
    return _schedule_response(row)


async def update_schedule(
    db: AsyncSession,
    counselor_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: ScheduleUpdate,
) -> ScheduleResponse:
    result = await db.execute(
        select(CounselorSchedule).where(
            CounselorSchedule.schedule_id == schedule_id,
            # Ownership is part of the lookup, never a separate check that
            # could be forgotten: another counselor's row simply is not found.
            CounselorSchedule.counselor_id == counselor_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(row, field, value)

    if row.start_time == row.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start and end cannot be the same time.",
        )
    await db.flush()
    return _schedule_response(row)


async def delete_schedule(
    db: AsyncSession, counselor_id: uuid.UUID, schedule_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(CounselorSchedule).where(
            CounselorSchedule.schedule_id == schedule_id,
            CounselorSchedule.counselor_id == counselor_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    # Sessions already booked under this schedule are untouched: removing a
    # working pattern must never cancel appointments people are expecting.
    await db.delete(row)
    await db.flush()


# -------------------------------------------------------------------
# Counselor: exceptions
# -------------------------------------------------------------------


async def list_exceptions(
    db: AsyncSession, counselor_id: uuid.UUID, upcoming_only: bool = True
) -> ExceptionListResponse:
    profile = await _counselor_settings(db, counselor_id)
    query = select(CounselorScheduleException).where(
        CounselorScheduleException.counselor_id == counselor_id
    )
    if upcoming_only:
        zone = resolve_zone(profile.timezone)
        today = datetime.now(timezone.utc).astimezone(zone).date()
        query = query.where(CounselorScheduleException.exception_date >= today)
    rows = (
        await db.execute(query.order_by(CounselorScheduleException.exception_date))
    ).scalars().all()
    return ExceptionListResponse(
        exceptions=[ExceptionResponse.model_validate(r) for r in rows],
        timezone=profile.timezone,
    )


async def create_exception(
    db: AsyncSession, counselor_id: uuid.UUID, payload: ExceptionCreate
) -> ExceptionResponse:
    await _counselor_settings(db, counselor_id)
    row = CounselorScheduleException(
        exception_id=uuid.uuid4(),
        counselor_id=counselor_id,
        exception_date=payload.exception_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_available=payload.is_available,
        reason=payload.reason,
    )
    db.add(row)
    await db.flush()
    return ExceptionResponse.model_validate(row)


async def delete_exception(
    db: AsyncSession, counselor_id: uuid.UUID, exception_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(CounselorScheduleException).where(
            CounselorScheduleException.exception_id == exception_id,
            CounselorScheduleException.counselor_id == counselor_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found"
        )
    await db.delete(row)
    await db.flush()


# -------------------------------------------------------------------
# Counselor: session settings
# -------------------------------------------------------------------


async def get_settings(db: AsyncSession, counselor_id: uuid.UUID) -> SessionSettingsResponse:
    profile = await _counselor_settings(db, counselor_id)
    return SessionSettingsResponse.model_validate(profile)


async def update_settings(
    db: AsyncSession, counselor_id: uuid.UUID, payload: SessionSettingsUpdate
) -> SessionSettingsResponse:
    profile = await _counselor_settings(db, counselor_id)
    data = payload.model_dump(exclude_unset=True)

    if "timezone" in data and data["timezone"]:
        # Reject an unresolvable zone here rather than silently falling back at
        # render time, which would show the counselor hours they never set.
        candidate = data["timezone"]
        if str(resolve_zone(candidate)) != candidate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown timezone: {candidate}",
            )

    for field, value in data.items():
        setattr(profile, field, value)
    await db.flush()
    return SessionSettingsResponse.model_validate(profile)


# -------------------------------------------------------------------
# Availability search
# -------------------------------------------------------------------


def _display(dt: datetime, zone) -> tuple[str, str]:
    local = dt.astimezone(zone)
    # %-I is not portable to Windows; strip the zero by hand.
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{hour}:{local:%M %p}", f"{local:%Y-%m-%d}"


async def search_availability(
    db: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    *,
    counselor_id: uuid.UUID | None = None,
    duration_minutes: int | None = None,
    display_timezone: str | None = None,
    limit: int | None = None,
    now: datetime | None = None,
) -> AvailabilitySearchResponse:
    """Concrete bookable slots for a window, across every eligible counselor."""
    current = now or datetime.now(timezone.utc)

    if window_end <= window_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The end of the window must be after its start.",
        )
    if window_end - window_start > timedelta(days=MAX_SEARCH_WINDOW_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Search at most {MAX_SEARCH_WINDOW_DAYS} days at a time.",
        )
    if window_start > current + timedelta(days=MAX_BOOKING_HORIZON_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sessions can be booked up to {MAX_BOOKING_HORIZON_DAYS} days ahead.",
        )

    # A window entirely in the past yields nothing rather than erroring: "today
    # 9-5" is a reasonable thing to ask at 6pm, and the honest answer is that
    # nothing is left, not that the request was malformed.
    effective_start = max(window_start, current)

    slots = await find_available_slots(
        db,
        effective_start,
        window_end,
        counselor_id=counselor_id,
        duration_minutes=duration_minutes,
        now=current,
        limit=limit,
    )

    zone = resolve_zone(display_timezone)
    rendered = []
    for slot in slots:
        start_label, date_label = _display(slot.start, zone)
        end_label, _ = _display(slot.end, zone)
        rendered.append(
            AvailableSlot(
                counselor_id=slot.counselor_id,
                counselor_name=slot.counselor_name,
                start=slot.start,
                end=slot.end,
                duration_minutes=slot.duration_minutes,
                display_start=start_label,
                display_end=end_label,
                display_date=date_label,
            )
        )

    return AvailabilitySearchResponse(
        timezone=str(zone),
        window_start=effective_start,
        window_end=window_end,
        slots=rendered,
        counselors_considered=len({s.counselor_id for s in slots}),
    )


# -------------------------------------------------------------------
# Booking
# -------------------------------------------------------------------


async def _notify_booking(
    db: AsyncSession,
    *,
    session: CounselorSession,
    counselor_user_id: uuid.UUID,
    student_user_id: uuid.UUID,
    student_name: str,
    counselor_name: str,
    cancelled: bool = False,
) -> None:
    """
    Tell the people involved, and the student's guardians.

    Deliberately content-free beyond names and times: a notification is read on
    a lock screen, and that a counselling session exists is itself sensitive.
    """
    when = session.scheduled_at.strftime("%d %b %Y at %H:%M UTC")
    if cancelled:
        counselor_msg = f"Your session with {student_name} on {when} was cancelled."
        student_msg = f"Your session with {counselor_name} on {when} was cancelled."
        title = "Session cancelled"
    else:
        counselor_msg = f"{student_name} booked a session with you on {when}."
        student_msg = f"Your session with {counselor_name} is confirmed for {when}."
        title = "Session booked"

    await notify_users(db, [counselor_user_id], title, counselor_msg)
    await notify_users(db, [student_user_id], title, student_msg)

    # Guardians see that a session exists, never what it is about. The link
    # table holds profile ids, so resolve through ParentProfile to reach the
    # user rows notifications are addressed to.
    parent_ids = (
        await db.execute(
            select(ParentProfile.user_id)
            .join(StudentParentLink, StudentParentLink.parent_id == ParentProfile.parent_id)
            .where(StudentParentLink.student_id == session.student_id)
        )
    ).scalars().all()
    if parent_ids:
        await notify_users(db, list(parent_ids), title, student_msg)


async def _resolve_participants(
    db: AsyncSession, student_id: uuid.UUID, counselor_id: uuid.UUID
) -> tuple[uuid.UUID, str, uuid.UUID, str]:
    """(student_user_id, student_name, counselor_user_id, counselor_name)."""
    student = (
        await db.execute(
            select(User.user_id, User.first_name, User.last_name)
            .join(StudentProfile, StudentProfile.user_id == User.user_id)
            .where(StudentProfile.student_id == student_id)
        )
    ).one_or_none()
    counselor = (
        await db.execute(
            select(User.user_id, User.first_name, User.last_name)
            .join(CounselorProfile, CounselorProfile.user_id == User.user_id)
            .where(CounselorProfile.counselor_id == counselor_id)
        )
    ).one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if counselor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Counselor not found"
        )
    return (
        student.user_id,
        f"{student.first_name} {student.last_name}".strip(),
        counselor.user_id,
        f"{counselor.first_name} {counselor.last_name}".strip(),
    )


async def book_session(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    counselor_id: uuid.UUID,
    starts_at: datetime,
    booked_by_user_id: uuid.UUID,
    request: Request | None = None,
    now: datetime | None = None,
) -> BookResponse:
    """
    Book a concrete slot, atomically.

    The frontend's view of availability is a suggestion, never authority: it
    was computed some seconds ago, and two students can hold the same suggestion
    at once. Everything is therefore revalidated here, inside the transaction:

      1. Serialise per counselor by locking the counselor row. Two bookings for
         the same counselor cannot evaluate their overlap checks concurrently;
         bookings for *different* counselors do not contend at all.
      2. Recompute availability from the schedule and confirm this exact slot
         is genuinely offered right now.
      3. Re-check for an overlapping live session.
      4. Insert, with the database's EXCLUDE constraint as the final arbiter.

    Steps 3 and 4 overlap on purpose. Step 3 gives a clean 409 in the ordinary
    race; step 4 is what holds if the constraint is the only thing standing
    (an unexpected code path, or a future caller that forgets to lock).
    """
    current = now or datetime.now(timezone.utc)

    if starts_at <= current:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That time has already passed.",
        )
    if starts_at > current + timedelta(days=MAX_BOOKING_HORIZON_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sessions can be booked up to {MAX_BOOKING_HORIZON_DAYS} days ahead.",
        )

    # 1. Serialise concurrent bookings for this counselor.
    locked = (
        await db.execute(
            select(CounselorProfile)
            .where(CounselorProfile.counselor_id == counselor_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Counselor not found"
        )

    duration = timedelta(minutes=locked.session_duration_minutes)
    ends_at = starts_at + duration

    # 2. Overlap check first, so a slot someone else has taken is reported as
    # exactly that. Both checks below return 409, but they mean different
    # things to the person reading the message: "just booked" invites a
    # retry on the next slot, while "not available" means this time was never
    # on offer. Asking the engine first would collapse the two, because a
    # taken slot has already been removed from what it returns.
    clash = (
        await db.execute(
            select(CounselorSession.counselor_session_id).where(
                CounselorSession.counselor_id == counselor_id,
                CounselorSession.status.not_in(INACTIVE_SESSION_STATUSES),
                CounselorSession.scheduled_at < ends_at,
                CounselorSession.ends_at > starts_at,
            )
        )
    ).first()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot was just booked. Here are the next available options.",
        )

    # 3. Is this slot actually on offer? Ask the engine, not the caller. This
    # catches times outside the working pattern, on a day off, or off the slot
    # grid entirely -- none of which any honest client would send.
    offered = await find_available_slots(
        db,
        starts_at,
        ends_at,
        counselor_id=counselor_id,
        now=current,
    )
    if not any(slot.start == starts_at for slot in offered):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is no longer available. Please pick another slot.",
        )

    student_user_id, student_name, counselor_user_id, counselor_name = (
        await _resolve_participants(db, student_id, counselor_id)
    )

    session = CounselorSession(
        counselor_session_id=uuid.uuid4(),
        student_id=student_id,
        counselor_id=counselor_id,
        scheduled_at=starts_at,
        ends_at=ends_at,
        status="scheduled",
        booked_by_user_id=booked_by_user_id,
    )
    db.add(session)

    # 4. The database has the last word.
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if EXCLUSION_CONSTRAINT in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That slot was just booked. Here are the next available options.",
            ) from exc
        raise

    await _notify_booking(
        db,
        session=session,
        counselor_user_id=counselor_user_id,
        student_user_id=student_user_id,
        student_name=student_name,
        counselor_name=counselor_name,
    )
    await log_audit(
        db,
        user_id=booked_by_user_id,
        action="counselor_session:book",
        entity_type="counselor_session",
        entity_id=session.counselor_session_id,
        details={
            "counselor_id": str(counselor_id),
            "student_id": str(student_id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        request=request,
    )

    return BookResponse(
        counselor_session_id=session.counselor_session_id,
        counselor_id=counselor_id,
        counselor_name=counselor_name,
        scheduled_at=starts_at,
        status=session.status,
    )


async def cancel_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    reason: str | None = None,
    request: Request | None = None,
) -> BookResponse:
    """
    Cancel a booked session and hand the time back.

    Cancelling sets a status the availability engine ignores, so the slot
    returns to the pool immediately -- no flag to reset, which is precisely how
    the old per-slot model leaked bookable time on every cancellation.
    """
    session = (
        await db.execute(
            select(CounselorSession).where(
                CounselorSession.counselor_session_id == session_id
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await _assert_may_cancel(db, session, actor_user_id, actor_role)

    if session.status in INACTIVE_SESSION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That session is already cancelled."
        )
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A completed session cannot be cancelled.",
        )

    session.status = "cancelled"
    session.cancelled_at = datetime.now(timezone.utc)
    session.cancelled_by_user_id = actor_user_id
    session.cancellation_reason = reason
    await db.flush()

    student_user_id, student_name, counselor_user_id, counselor_name = (
        await _resolve_participants(db, session.student_id, session.counselor_id)
    )
    await _notify_booking(
        db,
        session=session,
        counselor_user_id=counselor_user_id,
        student_user_id=student_user_id,
        student_name=student_name,
        counselor_name=counselor_name,
        cancelled=True,
    )
    await log_audit(
        db,
        user_id=actor_user_id,
        action="counselor_session:cancel",
        entity_type="counselor_session",
        entity_id=session.counselor_session_id,
        details={"reason": reason, "role": actor_role},
        request=request,
    )

    return BookResponse(
        counselor_session_id=session.counselor_session_id,
        counselor_id=session.counselor_id,
        counselor_name=counselor_name,
        scheduled_at=session.scheduled_at,
        status=session.status,
        message="Session cancelled",
    )


async def _assert_may_cancel(
    db: AsyncSession,
    session: CounselorSession,
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> None:
    """
    Ownership is derived from the database, never from the request.

    A student may cancel their own session; a parent one belonging to a child
    they are linked to; the counselor their own; admins anything.
    """
    if actor_role == "admin":
        return

    if actor_role == "counselor":
        owner = (
            await db.execute(
                select(CounselorProfile.counselor_id).where(
                    CounselorProfile.user_id == actor_user_id
                )
            )
        ).scalar_one_or_none()
        if owner == session.counselor_id:
            return

    elif actor_role == "student":
        owner = (
            await db.execute(
                select(StudentProfile.student_id).where(
                    StudentProfile.user_id == actor_user_id
                )
            )
        ).scalar_one_or_none()
        if owner == session.student_id:
            return

    elif actor_role == "parent":
        # Same two-step the parent insights path uses: user -> profile -> link.
        link = (
            await db.execute(
                select(StudentParentLink.link_id)
                .join(ParentProfile, ParentProfile.parent_id == StudentParentLink.parent_id)
                .where(
                    ParentProfile.user_id == actor_user_id,
                    StudentParentLink.student_id == session.student_id,
                )
            )
        ).first()
        if link is not None:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You cannot cancel this session.",
    )


async def exclusion_constraint_active(db: AsyncSession) -> bool:
    """
    Whether the database is enforcing overlaps itself.

    Surfaced so a deployment that could not create btree_gist is discoverable
    rather than silently weaker than the one it was tested on.
    """
    result = await db.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
        {"name": EXCLUSION_CONSTRAINT},
    )
    return result.scalar() is not None
