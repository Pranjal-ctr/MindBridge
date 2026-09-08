"""
Policy versions and the age thresholds the gate enforces.

These constants are the single source of truth for both the backend gate and
the frontend copy. Bumping a version here is what forces re-consent: existing
grants reference the old string and stop counting as current.

=======================================================================
LEGAL REVIEW REQUIRED BEFORE LAUNCH
=======================================================================
The thresholds below encode a reading of COPPA and India's DPDP Act 2023 that
has NOT been reviewed by a lawyer. They are engineering defaults chosen to be
conservative, not legal advice. Two questions in particular need counsel:

  1. DPDP treats anyone under 18 as a child and restricts "tracking or
     behavioural monitoring" of children. Kio does continuous wellness scoring
     and risk detection on minors. Whether that is permitted — under a
     legitimate-use/child-welfare reading, or a §9(4) exemption, or not at all
     without further conditions — is the single biggest open legal question
     about this product, and it is not one that code can settle.

  2. What counts as "verifiable" parental consent in each target jurisdiction.
     Email confirmation (what GUARDIAN_VERIFICATION_METHOD implements) is a
     recognised low-risk method in some regimes and insufficient in others.

Neither question blocks the mechanism from being built — it is needed under any
answer — but shipping to real minors before both are answered is a decision for
the business, not a default.
"""

from __future__ import annotations

from datetime import date

# -------------------------------------------------------------------
# Published policy versions
# -------------------------------------------------------------------
# Bump when the corresponding document changes materially. Users whose latest
# grant references an older version are treated as not having consented to the
# current one; see `users_needing_reconsent`.
TERMS_VERSION = "2026-09-08"
PRIVACY_VERSION = "2026-09-08"

CONSENT_TYPES = ("terms", "privacy", "guardian")

# -------------------------------------------------------------------
# Age thresholds
# -------------------------------------------------------------------
# Hard floor. Under this age no account is created at all, consent or not:
# COPPA's verifiable-parental-consent regime for under-13s is a materially
# heavier obligation than email confirmation satisfies, and Kio has no product
# reason to serve this age group today.
MINIMUM_AGE = 13

# At or above this, a user consents for themselves. Below it (but at or above
# MINIMUM_AGE) the account is created but held in `pending` until a guardian
# confirms. DPDP uses 18; COPPA uses 13. Taking the stricter of the two.
AGE_OF_SELF_CONSENT = 18

# The only verification method implemented. Recorded on every guardian consent
# row so a later, stronger method is distinguishable in the audit trail.
GUARDIAN_VERIFICATION_METHOD = "email_link"

# How long a guardian consent link stays valid.
GUARDIAN_CONSENT_TOKEN_HOURS = 72


def calculate_age(date_of_birth: date, *, today: date | None = None) -> int:
    """Age in completed years.

    The `(m, d) < (m, d)` comparison handles "birthday hasn't happened yet this
    year", including 29 February, without any calendar arithmetic.
    """
    today = today or date.today()
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def requires_guardian_consent(date_of_birth: date, *, today: date | None = None) -> bool:
    """True when this user is a minor who cannot consent for themselves."""
    return calculate_age(date_of_birth, today=today) < AGE_OF_SELF_CONSENT


def is_below_minimum_age(date_of_birth: date, *, today: date | None = None) -> bool:
    """True when no account may be created for this date of birth."""
    return calculate_age(date_of_birth, today=today) < MINIMUM_AGE
