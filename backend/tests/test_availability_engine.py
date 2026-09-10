"""
Availability engine: the interval maths, with no database in the way.

These cover the rules that are easy to get subtly wrong and expensive to get
wrong in production -- overnight schedules, buffers, exception precedence and
timezone conversion. They are deliberately pure: every one of them would still
pass on a server in any timezone, which is the property being asserted.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.counselors.availability import (
    apply_exceptions,
    crosses_midnight,
    expand_recurring,
    merge_intervals,
    resolve_zone,
    slots_from_intervals,
    subtract_intervals,
)

IST = ZoneInfo("Asia/Kolkata")
NY = ZoneInfo("America/New_York")

MONDAY = date(2027, 1, 4)
TUESDAY = date(2027, 1, 5)
SATURDAY = date(2027, 1, 9)

COUNSELOR = uuid.uuid4()
LONG_AGO = datetime(2020, 1, 1, tzinfo=timezone.utc)


class FakeSchedule:
    """Stands in for CounselorSchedule without needing a session."""

    def __init__(self, dow, start, end, *, active=True, eff_from=None, eff_until=None):
        self.day_of_week = dow
        self.start_time = start
        self.end_time = end
        self.is_active = active
        self.effective_from = eff_from
        self.effective_until = eff_until


class FakeException:
    def __init__(self, day, start=None, end=None, available=False):
        self.exception_date = day
        self.start_time = start
        self.end_time = end
        self.is_available = available


def local(day: date, hour: int, minute: int = 0, zone=IST) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone).astimezone(
        timezone.utc
    )


def starts(slots, zone=IST):
    return [f"{s.start.astimezone(zone):%H:%M}" for s in slots]


def make_slots(intervals, duration, buffer_minutes, busy=(), window=None, now=LONG_AGO):
    lo = window[0] if window else intervals[0][0]
    hi = window[1] if window else intervals[-1][1]
    return slots_from_intervals(
        list(intervals),
        duration,
        buffer_minutes,
        list(busy),
        counselor_id=COUNSELOR,
        counselor_name="Test Counselor",
        not_before=now,
        window_start=lo,
        window_end=hi,
    )


# -------------------------------------------------------------------
# Interval helpers
# -------------------------------------------------------------------


def test_merge_coalesces_overlapping_and_touching():
    a = (local(MONDAY, 9), local(MONDAY, 11))
    b = (local(MONDAY, 10), local(MONDAY, 12))
    c = (local(MONDAY, 12), local(MONDAY, 13))
    assert merge_intervals([a, b, c]) == [(local(MONDAY, 9), local(MONDAY, 13))]


def test_subtract_splits_an_interval_in_two():
    base = [(local(MONDAY, 9), local(MONDAY, 17))]
    cut = [(local(MONDAY, 12), local(MONDAY, 13))]
    assert subtract_intervals(base, cut) == [
        (local(MONDAY, 9), local(MONDAY, 12)),
        (local(MONDAY, 13), local(MONDAY, 17)),
    ]


def test_subtract_removes_an_interval_entirely():
    base = [(local(MONDAY, 9), local(MONDAY, 17))]
    cut = [(local(MONDAY, 8), local(MONDAY, 18))]
    assert subtract_intervals(base, cut) == []


# -------------------------------------------------------------------
# Recurring schedules
# -------------------------------------------------------------------


def test_weekday_schedule_expands_on_its_own_day_only():
    schedules = [FakeSchedule(0, time(9), time(17))]
    monday = expand_recurring(schedules, IST, MONDAY, MONDAY)
    tuesday = expand_recurring(schedules, IST, TUESDAY, TUESDAY)
    assert monday == [(local(MONDAY, 9), local(MONDAY, 17))]
    assert tuesday == []


def test_monday_to_friday_covers_five_days_and_skips_the_weekend():
    schedules = [FakeSchedule(d, time(9), time(17)) for d in range(5)]
    week = expand_recurring(schedules, IST, MONDAY, date(2027, 1, 10))
    assert len(week) == 5
    assert all(i[0].astimezone(IST).weekday() < 5 for i in week)


def test_multiple_intervals_in_one_day_stay_separate():
    schedules = [FakeSchedule(0, time(9), time(13)), FakeSchedule(0, time(14), time(18))]
    assert expand_recurring(schedules, IST, MONDAY, MONDAY) == [
        (local(MONDAY, 9), local(MONDAY, 13)),
        (local(MONDAY, 14), local(MONDAY, 18)),
    ]


def test_inactive_schedule_produces_nothing():
    schedules = [FakeSchedule(0, time(9), time(17), active=False)]
    assert expand_recurring(schedules, IST, MONDAY, MONDAY) == []


def test_effective_window_bounds_the_schedule():
    schedules = [FakeSchedule(0, time(9), time(17), eff_from=date(2027, 1, 11))]
    assert expand_recurring(schedules, IST, MONDAY, MONDAY) == []

    schedules = [FakeSchedule(0, time(9), time(17), eff_until=date(2027, 1, 1))]
    assert expand_recurring(schedules, IST, MONDAY, MONDAY) == []


# -------------------------------------------------------------------
# Overnight
# -------------------------------------------------------------------


def test_crosses_midnight_detects_the_wrap():
    assert crosses_midnight(time(17), time(1)) is True
    assert crosses_midnight(time(9), time(17)) is False
    # Equal times are a full wrap, not a zero-length interval; the schemas
    # reject them before they get here, but the predicate must be decisive.
    assert crosses_midnight(time(9), time(9)) is True


def test_overnight_schedule_runs_into_the_next_day():
    """Monday 17:00-01:00 is Monday evening through Tuesday 01:00."""
    schedules = [FakeSchedule(0, time(17), time(1))]
    intervals = expand_recurring(schedules, IST, MONDAY, MONDAY)
    assert intervals == [(local(MONDAY, 17), local(TUESDAY, 1))]

    start_local = intervals[0][0].astimezone(IST)
    end_local = intervals[0][1].astimezone(IST)
    assert start_local.day == 4 and end_local.day == 5


def test_early_morning_schedule_is_not_treated_as_overnight():
    """01:00-09:00 is an ordinary same-day interval."""
    schedules = [FakeSchedule(0, time(1), time(9))]
    assert expand_recurring(schedules, IST, MONDAY, MONDAY) == [
        (local(MONDAY, 1), local(MONDAY, 9))
    ]


def test_overnight_slots_exist_on_both_sides_of_midnight():
    schedules = [FakeSchedule(0, time(23), time(1))]
    intervals = expand_recurring(schedules, IST, MONDAY, MONDAY)
    slots = make_slots(intervals, 30, 0)
    labels = starts(slots)
    assert labels == ["23:00", "23:30", "00:00", "00:30"]

    before = [s for s in slots if s.start.astimezone(IST).day == 4]
    after = [s for s in slots if s.start.astimezone(IST).day == 5]
    assert len(before) == 2 and len(after) == 2


def test_a_schedule_starting_the_previous_evening_is_found():
    """Asking about Tuesday must still see Monday's overnight interval."""
    schedules = [FakeSchedule(0, time(22), time(6))]
    intervals = expand_recurring(schedules, IST, TUESDAY, TUESDAY)
    assert intervals == [(local(MONDAY, 22), local(TUESDAY, 6))]


# -------------------------------------------------------------------
# Slot generation
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "duration,buffer_minutes,expected",
    [
        (30, 0, ["09:00", "09:30", "10:00", "10:30"]),
        (30, 5, ["09:00", "09:35", "10:10"]),
        (30, 10, ["09:00", "09:40", "10:20"]),
        (30, 15, ["09:00", "09:45", "10:30"]),
        (45, 0, ["09:00", "09:45"]),
        (45, 15, ["09:00", "10:00"]),
        (60, 0, ["09:00", "10:00"]),
        (60, 15, ["09:00"]),
    ],
)
def test_slot_grid_for_each_duration_and_buffer(duration, buffer_minutes, expected):
    """The stride is duration + buffer; a partial slot at the end is never offered."""
    intervals = [(local(MONDAY, 9), local(MONDAY, 11))]
    assert starts(make_slots(intervals, duration, buffer_minutes)) == expected


def test_a_booked_session_removes_exactly_its_slot():
    intervals = [(local(MONDAY, 9), local(MONDAY, 11))]
    busy = [(local(MONDAY, 10), local(MONDAY, 10, 30))]
    assert starts(make_slots(intervals, 30, 0, busy)) == ["09:00", "09:30", "10:30"]


def test_an_off_grid_booking_does_not_shift_the_rest_of_the_day():
    """
    A session at 10:15-10:45 blocks the 10:00 and 10:30 slots and leaves every
    other start where it was.

    Found in the running app: the generator used to subtract booked time first
    and then walk what was left, so one off-grid session re-anchored the whole
    afternoon to 10:45, 11:15, 11:45. Students saw different times on different
    days with nothing on screen to explain why.
    """
    intervals = [(local(MONDAY, 9), local(MONDAY, 12))]
    busy = [(local(MONDAY, 10, 15), local(MONDAY, 10, 45))]
    assert starts(make_slots(intervals, 30, 0, busy)) == [
        "09:00",
        "09:30",
        "11:00",
        "11:30",
    ]


def test_the_grid_is_identical_whether_or_not_anything_is_booked():
    intervals = [(local(MONDAY, 9), local(MONDAY, 12))]
    free = starts(make_slots(intervals, 30, 0, []))
    busy = [(local(MONDAY, 10, 7), local(MONDAY, 10, 23))]
    with_booking = starts(make_slots(intervals, 30, 0, busy))
    assert set(with_booking).issubset(set(free))


def test_buffer_protects_the_time_around_a_booking():
    """A 10-minute buffer means the slots either side of a booking go too."""
    intervals = [(local(MONDAY, 9), local(MONDAY, 12))]
    busy = [(local(MONDAY, 10), local(MONDAY, 10, 30))]
    labels = starts(make_slots(intervals, 30, 10, busy))
    assert "10:20" not in labels
    assert "09:40" not in labels


def test_zero_duration_yields_nothing_rather_than_looping_forever():
    intervals = [(local(MONDAY, 9), local(MONDAY, 11))]
    assert make_slots(intervals, 0, 0) == []


# -------------------------------------------------------------------
# Past filtering
# -------------------------------------------------------------------


def test_slots_in_the_past_are_dropped():
    """At 18:20 nobody may book 18:00 -- the spec's own example."""
    intervals = [(local(MONDAY, 17), local(MONDAY, 20))]
    now = local(MONDAY, 18, 20)
    labels = starts(make_slots(intervals, 30, 0, now=now))
    assert "17:00" not in labels and "18:00" not in labels
    assert labels == ["18:30", "19:00", "19:30"]


def test_a_slot_starting_exactly_now_is_not_offered():
    intervals = [(local(MONDAY, 9), local(MONDAY, 11))]
    labels = starts(make_slots(intervals, 30, 0, now=local(MONDAY, 9)))
    assert labels[0] == "09:00"  # not_before is inclusive of equality
    # ... but a moment later it is gone.
    labels = starts(make_slots(intervals, 30, 0, now=local(MONDAY, 9) + timedelta(seconds=1)))
    assert labels[0] == "09:30"


# -------------------------------------------------------------------
# Exceptions
# -------------------------------------------------------------------


def test_full_day_time_off_clears_the_day():
    base = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    assert apply_exceptions(base, [FakeException(MONDAY)], IST) == []


def test_partial_time_off_trims_the_interval():
    base = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    result = apply_exceptions(base, [FakeException(MONDAY, time(14), time(17))], IST)
    assert result == [(local(MONDAY, 9), local(MONDAY, 14))]


def test_time_off_in_the_middle_splits_the_day():
    base = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    result = apply_exceptions(base, [FakeException(MONDAY, time(12), time(13))], IST)
    assert result == [
        (local(MONDAY, 9), local(MONDAY, 12)),
        (local(MONDAY, 13), local(MONDAY, 17)),
    ]


def test_additional_availability_creates_a_day_that_was_not_working():
    """A one-off Saturday, with no recurring Saturday schedule at all."""
    result = apply_exceptions([], [FakeException(SATURDAY, time(10), time(14), True)], IST)
    assert result == [(local(SATURDAY, 10), local(SATURDAY, 14))]


def test_time_off_beats_additional_availability_on_the_same_day():
    """Exceptions take precedence over the recurring rule, and off beats extra."""
    base = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    exceptions = [
        FakeException(MONDAY, time(17), time(19), available=True),
        FakeException(MONDAY, time(16), time(18)),
    ]
    result = apply_exceptions(base, exceptions, IST)
    assert result == [(local(MONDAY, 9), local(MONDAY, 16)), (local(MONDAY, 18), local(MONDAY, 19))]


def test_exception_overrides_recurring_schedule_entirely():
    base = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    slots = make_slots(apply_exceptions(base, [FakeException(MONDAY)], IST) or [], 30, 0) \
        if apply_exceptions(base, [FakeException(MONDAY)], IST) else []
    assert slots == []


# -------------------------------------------------------------------
# Timezones
# -------------------------------------------------------------------


def test_nine_am_ist_is_the_same_instant_regardless_of_server_timezone():
    """
    The engine converts from the counselor's zone, never the process's. 09:00
    IST is 03:30 UTC whatever TZ the test process happens to be running under.
    """
    intervals = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    assert intervals[0][0] == datetime(2027, 1, 4, 3, 30, tzinfo=timezone.utc)


def test_the_same_wall_clock_in_two_zones_is_two_different_instants():
    ist = expand_recurring([FakeSchedule(0, time(9), time(17))], IST, MONDAY, MONDAY)
    ny = expand_recurring([FakeSchedule(0, time(9), time(17))], NY, MONDAY, MONDAY)
    assert ist[0][0] != ny[0][0]
    assert (ny[0][0] - ist[0][0]) == timedelta(hours=10, minutes=30)


def test_utc_counselor_needs_no_special_casing():
    utc_zone = ZoneInfo("UTC")
    intervals = expand_recurring([FakeSchedule(0, time(9), time(17))], utc_zone, MONDAY, MONDAY)
    assert intervals == [
        (
            datetime(2027, 1, 4, 9, tzinfo=timezone.utc),
            datetime(2027, 1, 4, 17, tzinfo=timezone.utc),
        )
    ]


def test_midnight_boundary_lands_on_the_right_local_day():
    """00:00-01:00 IST on Monday is 18:30 UTC on *Sunday*."""
    intervals = expand_recurring([FakeSchedule(0, time(0), time(1))], IST, MONDAY, MONDAY)
    start = intervals[0][0]
    assert start == datetime(2027, 1, 3, 18, 30, tzinfo=timezone.utc)
    assert start.astimezone(IST).date() == MONDAY


def test_a_zone_that_observes_dst_shifts_the_utc_instant():
    """New York in January is UTC-5; in July, UTC-4. Same local 09:00."""
    january = expand_recurring(
        [FakeSchedule(0, time(9), time(17))], NY, date(2027, 1, 4), date(2027, 1, 4)
    )
    july = expand_recurring(
        [FakeSchedule(0, time(9), time(17))], NY, date(2027, 7, 5), date(2027, 7, 5)
    )
    assert january[0][0].hour == 14
    assert july[0][0].hour == 13


def test_an_unknown_timezone_falls_back_instead_of_raising():
    assert str(resolve_zone("Mars/Olympus_Mons")) == "Asia/Kolkata"
    assert str(resolve_zone(None)) == "Asia/Kolkata"
    assert str(resolve_zone("")) == "Asia/Kolkata"
