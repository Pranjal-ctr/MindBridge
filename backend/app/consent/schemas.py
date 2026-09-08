"""
Kio Consent Schemas
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class ConsentRecord(BaseModel):
    """One consent grant."""
    consent_id: uuid.UUID
    consent_type: str
    policy_version: str
    granted_at: datetime
    granted_by_email: str | None = None
    verification_method: str | None = None
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConsentStatusResponse(BaseModel):
    """Everything the client needs to decide what to prompt for.

    `needs_reconsent` is the important one: it is true when the user has a
    valid grant for an OLDER policy version, which is a different state from
    never having consented, and is what drives a re-consent prompt after the
    text changes.
    """
    date_of_birth: date | None = None
    age: int | None = None
    is_minor: bool = False

    terms_version: str
    privacy_version: str

    has_accepted_terms: bool = False
    has_accepted_privacy: bool = False
    needs_reconsent: bool = False

    # not_required | pending | granted | denied | unknown
    guardian_consent_status: str = "unknown"
    guardian_email: str | None = None

    records: list[ConsentRecord] = []


class GuardianConsentRequest(BaseModel):
    """Send (or resend) a consent request to a guardian."""
    guardian_email: EmailStr
    guardian_name: str | None = Field(None, max_length=200)


class GuardianConsentDecision(BaseModel):
    """A guardian's decision, made from the emailed link."""
    token: str = Field(..., min_length=10)
    # Explicit rather than implied by which endpoint was hit: a refusal is a
    # meaningful record, not just the absence of a grant.
    granted: bool


class GuardianConsentContext(BaseModel):
    """What the guardian sees before deciding. Resolved from the token.

    Deliberately minimal — a token holder is not yet an authenticated user, so
    this exposes only what is needed to make an informed decision about a named
    child, and nothing about their wellness data.
    """
    student_first_name: str
    student_last_name: str
    school_name: str | None = None
    terms_version: str
    privacy_version: str
    already_decided: bool = False


class AcceptPolicyRequest(BaseModel):
    """Record acceptance of the current terms/privacy versions."""
    accept_terms: bool = True
    accept_privacy: bool = True
