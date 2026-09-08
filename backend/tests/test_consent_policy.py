"""
Age arithmetic for the consent gate.

Pure functions, no database — kept out of test_consent.py because that module
carries a module-level asyncio mark for its API tests.

The whole age gate rests on these two behaviours being exact: an off-by-one
here is the difference between a 12-year-old being admitted and a 13-year-old
being refused.
"""

from __future__ import annotations

from datetime import date

from app.consent.policy import (
    AGE_OF_SELF_CONSENT,
    MINIMUM_AGE,
    calculate_age,
    is_below_minimum_age,
    requires_guardian_consent,
)


def test_age_counts_completed_years():
    """The day before a birthday you are still the younger age."""
    today = date(2026, 9, 8)
    assert calculate_age(date(2013, 9, 9), today=today) == 12   # birthday tomorrow
    assert calculate_age(date(2013, 9, 8), today=today) == 13   # birthday today
    assert calculate_age(date(2013, 9, 7), today=today) == 13   # birthday yesterday


def test_leap_day_birthday_is_handled():
    """29 February has no anniversary in a common year. An implementation that
    does `dob.replace(year=today.year)` raises ValueError on this input."""
    assert calculate_age(date(2008, 2, 29), today=date(2026, 2, 28)) == 17
    assert calculate_age(date(2008, 2, 29), today=date(2026, 3, 1)) == 18


def test_minimum_age_boundary_is_inclusive():
    """Exactly MINIMUM_AGE is allowed; a day younger is not."""
    today = date(2026, 9, 8)
    turns_13_today = date(today.year - MINIMUM_AGE, today.month, today.day)

    assert is_below_minimum_age(turns_13_today, today=today) is False
    assert is_below_minimum_age(
        date(today.year - MINIMUM_AGE, today.month, today.day + 1), today=today
    ) is True


def test_self_consent_boundary_is_inclusive():
    """At exactly AGE_OF_SELF_CONSENT a user consents for themselves."""
    today = date(2026, 9, 8)
    turns_18_today = date(today.year - AGE_OF_SELF_CONSENT, today.month, today.day)

    assert requires_guardian_consent(turns_18_today, today=today) is False
    assert requires_guardian_consent(
        date(today.year - AGE_OF_SELF_CONSENT, today.month, today.day + 1), today=today
    ) is True
