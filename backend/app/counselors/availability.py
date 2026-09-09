"""
Counselor availability engine.

Turns recurring weekly schedules into concrete bookable slots for a requested
window. Nothing here is persisted: storing generated slots would mean writing
thousands of rows to express a rule ("Mon-Fri 09:00-17:00") that fits in five,
and every schedule edit would have to rewrite them.

THE ALGORITHM, in order:

  1. Expand recurring schedules into concrete local intervals for each date in
     the requested range.
  2. Apply exceptions. Unavailable exceptions are subtracted; additional
     availability is added. Exceptions always win over the recurring rule.
  3. Convert to UTC.
  4. Subtract time already taken by live sessions, each widened by the
     counselor's buffer on both sides.
  5. Walk each surviving interval in steps of (duration + buffer), emitting a
     slot wherever a full session fits.
  6. Drop anything starting in the past.

TIMEZONES. A schedule's "09:00" is a claim about the counselor's morning, not
about a UTC instant, so recurring times are stored naive and interpreted in the
counselor's IANA zone at expansion time. Everything downstream -- comparison,
storage, the API contract -- is UTC. The server's own timezone is never
consulted, because availability must not change with the hosting region.

OVERNIGHT SCHEDULES. A row whose end_time is less than or equal to its
start_time runs past midnight into the following day: Monday 17:00-01:00 means
Monday 17:00 through Tuesday 01:00. It stays one row. To catch an interval that
began the day before the requested range, expansion always starts one day early
and filters afterwards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    CounselorProfile,
    CounselorSchedule,
    CounselorScheduleException,
    CounselorSession,
    User,
)

# Statuses that do not occupy the calendar. Mirrors the WHERE clause on the
# excl_counselor_session_overlap constraint -- if these two ever disagree, the
# engine would offer a slot the database then refuses.
INACTIVE_SESSION_STATUSES = ("cancelled", "no_show")

DEFAULT_TIMEZONE = "Asia/Kolkata"

# An interval in UTC.
Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Slot:
    """One bookable session slot, always in UTC."""

    counselor_id: uuid.UUID
    counselor_name: str
    start: datetime
    end: datetime
    duration_minutes: int


@dataclass(frozen=True)
class CounselorScheduleData:
    """Everything the engine needs about one counselor, fetched in bulk."""

    counselor_id: uuid.UUID
    counselor_name: str
    timezone_name: str
    duration_minutes: int
    buffer_minutes: int
    schedules: list[CounselorSchedule]
    exceptions: list[CounselorScheduleException]
    busy: list[Interval]


def resolve_zone(name: str | None) -> ZoneInfo | timezone:
    """
    A counselor's zone, falling back rather than failing.

    A typo in a timezone column must not take availability down for everyone;
    an India-default is wrong for that one counselor but recoverable, whereas
    a 500 on the booking page is not.

    The second fallback is not paranoia. zoneinfo has no zone data of its own:
    it reads the host's IANA database, and Windows has none while slim
    container images often omit it. The `tzdata` package covers that (and is a
    declared dependency for exactly this reason), but if it is ever missing,
    resolving the default would raise from inside the error handler for a bad
    zone -- turning a recoverable typo into an outage. UTC always exists.
    """
    for candidate in (name, DEFAULT_TIMEZONE):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return timezone.utc


def _local_to_utc(local_date: date, local_time: time, zone: ZoneInfo) -> datetime:
    """Interpret a naive local date+time in `zone` and return it as UTC."""
    return datetime.combine(local_date, local_time, tzinfo=zone).astimezone(timezone.utc)


def crosses_midnight(start: time, end: time) -> bool:
    """True when an interval runs past midnight (Mon 17:00 -> Tue 01:00)."""
    return end <= start


def _schedule_applies_on(schedule: CounselorSchedule, day: date) -> bool:
    """Whether a recurring row is in force on a given local date."""
    if not schedule.is_active:
        return False
    if schedule.day_of_week != day.weekday():
        return False
    if schedule.effective_from and day < schedule.effective_from:
        return False
    if schedule.effective_until and day > schedule.effective_until:
        return False
    return True


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """Sort and coalesce touching or overlapping intervals."""
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda i: i[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def subtract_intervals(base: list[Interval], cuts: list[Interval]) -> list[Interval]:
    """Remove every `cuts` region from `base`, splitting intervals as needed."""
    if not cuts:
        return list(base)
    result: list[Interval] = []
    for start, end in base:
        pieces = [(start, end)]
        for cut_start, cut_end in cuts:
            next_pieces: list[Interval] = []
            for piece_start, piece_end in pieces:
                # No intersection: the piece survives whole.
                if cut_end <= piece_start or cut_start >= piece_end:
                    next_pieces.append((piece_start, piece_end))
                    continue
                if cut_start > piece_start:
                    next_pieces.append((piece_start, cut_start))
                if cut_end < piece_end:
                    next_pieces.append((cut_end, piece_end))
            pieces = next_pieces
        result.extend(pieces)
    return merge_intervals(result)


def expand_recurring(
    schedules: list[CounselorSchedule],
    zone: ZoneInfo,
    first_day: date,
    last_day: date,
) -> list[Interval]:
    """
    Concrete UTC intervals from recurring rows, for local dates in range.

    Starts a day early so an overnight interval that began the previous evening
    is still found; the caller clips to the requested window.
    """
    # The requested local range, as UTC bounds. Intervals from the extra day
    # are only of interest if they reach into it.
    range_start = _local_to_utc(first_day, time(0, 0), zone)
    range_end = _local_to_utc(last_day + timedelta(days=1), time(0, 0), zone)

    intervals: list[Interval] = []
    day = first_day - timedelta(days=1)
    while day <= last_day:
        for schedule in schedules:
            if not _schedule_applies_on(schedule, day):
                continue
            start = _local_to_utc(day, schedule.start_time, zone)
            if crosses_midnight(schedule.start_time, schedule.end_time):
                end = _local_to_utc(day + timedelta(days=1), schedule.end_time, zone)
            else:
                end = _local_to_utc(day, schedule.end_time, zone)
            if end <= start:
                continue
            # Drop intervals that do not reach the requested range at all, so
            # the extra look-back day contributes only the overnight tail it
            # was added for.
            if end <= range_start or start >= range_end:
                continue
            # Kept WHOLE rather than truncated to the range. The slot grid is
            # anchored to the interval's real start, so clipping an overnight
            # interval at midnight would shift every slot after it: a 45-minute
            # session in a 22:00-06:00 window would be offered at 00:00, 00:45
            # when asked about Tuesday but 22:00, 22:45, 23:30, 00:15 when
            # asked about Monday. Slots are clipped to the caller's window
            # later, which bounds the output without moving the grid.
            intervals.append((start, end))
        day += timedelta(days=1)
    return merge_intervals(intervals)


def apply_exceptions(
    base: list[Interval],
    exceptions: list[CounselorScheduleException],
    zone: ZoneInfo,
) -> list[Interval]:
    """
    availability = recurring - unavailable + additional

    Additional availability is added first and unavailable subtracted second,
    so a same-day "off 14:00-15:00" still wins over an extra Saturday morning.
    """
    additional: list[Interval] = []
    removals: list[Interval] = []

    for exc in exceptions:
        day = exc.exception_date
        if exc.start_time is None or exc.end_time is None:
            # Whole-day exception. Only meaningful as time off; the check
            # constraint forbids an all-day "additional" row.
            start = _local_to_utc(day, time(0, 0), zone)
            end = _local_to_utc(day + timedelta(days=1), time(0, 0), zone)
            removals.append((start, end))
            continue

        start = _local_to_utc(day, exc.start_time, zone)
        if crosses_midnight(exc.start_time, exc.end_time):
            end = _local_to_utc(day + timedelta(days=1), exc.end_time, zone)
        else:
            end = _local_to_utc(day, exc.end_time, zone)
        if end <= start:
            continue
        (additional if exc.is_available else removals).append((start, end))

    combined = merge_intervals(list(base) + additional)
    return subtract_intervals(combined, merge_intervals(removals))


def slots_from_intervals(
    intervals: list[Interval],
    duration_minutes: int,
    buffer_minutes: int,
    busy: list[Interval],
    *,
    counselor_id: uuid.UUID,
    counselor_name: str,
    not_before: datetime,
    window_start: datetime,
    window_end: datetime,
) -> list[Slot]:
    """
    Walk each free interval and emit slots that fit.

    The stride is duration + buffer, so with a 30-minute session and a
    10-minute buffer the starts are 09:00, 09:40, 10:20 -- the buffer is time
    the counselor gets back between sessions, never bookable time.

    Booked sessions are widened by the buffer on both sides before subtraction,
    so a booking at 10:00 also protects the counselor's break either side of it.
    """
    duration = timedelta(minutes=duration_minutes)
    buffer = timedelta(minutes=buffer_minutes)
    stride = duration + buffer
    if duration <= timedelta(0):
        return []

    padded_busy = merge_intervals([(s - buffer, e + buffer) for s, e in busy])
    free = subtract_intervals(intervals, padded_busy)

    slots: list[Slot] = []
    for interval_start, interval_end in free:
        cursor = interval_start
        while cursor + duration <= interval_end:
            slot_end = cursor + duration
            # Clip to the caller's window and refuse anything already past.
            if cursor >= not_before and cursor >= window_start and slot_end <= window_end:
                slots.append(
                    Slot(
                        counselor_id=counselor_id,
                        counselor_name=counselor_name,
                        start=cursor,
                        end=slot_end,
                        duration_minutes=duration_minutes,
                    )
                )
            cursor += stride
    return slots


async def load_counselor_schedules(
    db: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    counselor_id: uuid.UUID | None = None,
) -> list[CounselorScheduleData]:
    """
    Fetch every eligible counselor's rules and commitments in four queries.

    Deliberately not one query per counselor: the "any counselor" search hits
    the whole verified directory, and per-counselor round trips would make that
    N+1 (see the performance note in the spec).

    Eligibility is the existing product rule -- verified, available, and an
    active user account. Booking is platform-wide by design (migration 008), so
    there is no tenant filter here; a student at any school may book any
    verified counselor.
    """
    counselor_query = (
        select(
            CounselorProfile.counselor_id,
            User.first_name,
            User.last_name,
            CounselorProfile.timezone,
            CounselorProfile.session_duration_minutes,
            CounselorProfile.buffer_minutes,
        )
        .join(User, User.user_id == CounselorProfile.user_id)
        .where(
            CounselorProfile.is_verified.is_(True),
            CounselorProfile.is_available.is_(True),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if counselor_id is not None:
        counselor_query = counselor_query.where(CounselorProfile.counselor_id == counselor_id)

    rows = (await db.execute(counselor_query)).all()
    if not rows:
        return []

    ids = [row.counselor_id for row in rows]

    schedules = (
        await db.execute(
            select(CounselorSchedule).where(
                CounselorSchedule.counselor_id.in_(ids),
                CounselorSchedule.is_active.is_(True),
            )
        )
    ).scalars().all()

    # Exception dates are local, so widen by a day either side rather than
    # trying to convert a UTC window into every counselor's local calendar.
    exceptions = (
        await db.execute(
            select(CounselorScheduleException).where(
                CounselorScheduleException.counselor_id.in_(ids),
                CounselorScheduleException.exception_date
                >= (window_start - timedelta(days=1)).date(),
                CounselorScheduleException.exception_date
                <= (window_end + timedelta(days=1)).date(),
            )
        )
    ).scalars().all()

    sessions = (
        await db.execute(
            select(
                CounselorSession.counselor_id,
                CounselorSession.scheduled_at,
                CounselorSession.ends_at,
            ).where(
                CounselorSession.counselor_id.in_(ids),
                CounselorSession.status.not_in(INACTIVE_SESSION_STATUSES),
                # Any session overlapping the window, generously bounded so a
                # long session starting before it is still subtracted.
                CounselorSession.ends_at > window_start - timedelta(days=1),
                CounselorSession.scheduled_at < window_end + timedelta(days=1),
            )
        )
    ).all()

    by_counselor: dict[uuid.UUID, CounselorScheduleData] = {}
    for row in rows:
        by_counselor[row.counselor_id] = CounselorScheduleData(
            counselor_id=row.counselor_id,
            counselor_name=f"{row.first_name} {row.last_name}".strip(),
            timezone_name=row.timezone or DEFAULT_TIMEZONE,
            duration_minutes=row.session_duration_minutes or 30,
            buffer_minutes=row.buffer_minutes or 0,
            schedules=[],
            exceptions=[],
            busy=[],
        )
    for schedule in schedules:
        data = by_counselor.get(schedule.counselor_id)
        if data:
            data.schedules.append(schedule)
    for exc in exceptions:
        data = by_counselor.get(exc.counselor_id)
        if data:
            data.exceptions.append(exc)
    for counselor_ref, start_at, end_at in sessions:
        data = by_counselor.get(counselor_ref)
        if data:
            data.busy.append((start_at, end_at))

    return list(by_counselor.values())


def slots_for_counselor(
    data: CounselorScheduleData,
    window_start: datetime,
    window_end: datetime,
    now: datetime,
    duration_override: int | None = None,
) -> list[Slot]:
    """Run the full pipeline for one counselor."""
    zone = resolve_zone(data.timezone_name)
    first_day = window_start.astimezone(zone).date()
    last_day = window_end.astimezone(zone).date()

    recurring = expand_recurring(data.schedules, zone, first_day, last_day)
    effective = apply_exceptions(recurring, data.exceptions, zone)

    return slots_from_intervals(
        effective,
        duration_minutes=duration_override or data.duration_minutes,
        buffer_minutes=data.buffer_minutes,
        busy=data.busy,
        counselor_id=data.counselor_id,
        counselor_name=data.counselor_name,
        not_before=now,
        window_start=window_start,
        window_end=window_end,
    )


async def find_available_slots(
    db: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    *,
    counselor_id: uuid.UUID | None = None,
    duration_minutes: int | None = None,
    now: datetime | None = None,
    limit: int | None = None,
) -> list[Slot]:
    """
    Every bookable slot in a window, across counselors, soonest first.

    `now` is injectable for tests but defaults to the server's authoritative
    UTC clock -- never a client-supplied time, which would let a caller ask for
    slots in the past.
    """
    current = now or datetime.now(timezone.utc)
    if window_end <= window_start:
        return []

    counselors = await load_counselor_schedules(
        db, window_start, window_end, counselor_id=counselor_id
    )

    slots: list[Slot] = []
    for data in counselors:
        slots.extend(
            slots_for_counselor(
                data, window_start, window_end, current, duration_override=duration_minutes
            )
        )

    slots.sort(key=lambda s: (s.start, s.counselor_name))
    return slots[:limit] if limit else slots
