"""
Kio Consent Service.

Records consent grants, runs the age gate, and drives the guardian consent
round trip.

Design notes:
  * Consent rows are append-only. Nothing here updates a grant in place; a
    withdrawal stamps `revoked_at` and a new version writes a new row.
  * The guardian token is a signed JWT carrying the student's id, not a row in
    a table. It needs no storage, expires on its own, and — because it embeds
    the student's current consent status — stops working once a decision is
    recorded, so a forwarded link cannot be replayed to flip the answer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.consent.policy import (
    GUARDIAN_CONSENT_TOKEN_HOURS,
    GUARDIAN_VERIFICATION_METHOD,
    PRIVACY_VERSION,
    TERMS_VERSION,
    calculate_age,
    is_below_minimum_age,
    requires_guardian_consent,
)
from app.consent.schemas import (
    ConsentRecord,
    ConsentStatusResponse,
    GuardianConsentContext,
)
from database.models import StudentProfile, Tenant, User, UserConsent

_GUARDIAN_PURPOSE = "guardian_consent"


# -------------------------------------------------------------------
# Request metadata
# -------------------------------------------------------------------

def _client_metadata(request: Request | None) -> tuple[str | None, str | None]:
    """IP and user-agent for the consent record.

    An online consent record is only defensible if it captures who agreed, from
    where, and with what. Behind a proxy the first X-Forwarded-For hop is the
    real client; uvicorn is started with --proxy-headers so request.client is
    usually already correct, but the header is checked first for hosts that
    don't rewrite it.
    """
    if request is None:
        return None, None

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None

    return ip, request.headers.get("user-agent")


# -------------------------------------------------------------------
# Recording consent
# -------------------------------------------------------------------

async def record_consent(
    db: AsyncSession,
    user_id: uuid.UUID,
    consent_type: str,
    policy_version: str,
    *,
    request: Request | None = None,
    granted_by_email: str | None = None,
    verification_method: str | None = None,
) -> UserConsent:
    """Append a consent grant. Never updates an existing row."""
    ip, user_agent = _client_metadata(request)

    row = UserConsent(
        user_id=user_id,
        consent_type=consent_type,
        policy_version=policy_version,
        ip_address=ip,
        user_agent=user_agent,
        granted_by_email=granted_by_email,
        verification_method=verification_method,
    )
    db.add(row)
    await db.flush()
    return row


async def record_signup_consent(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> None:
    """Record acceptance of the current terms and privacy versions."""
    await record_consent(db, user_id, "terms", TERMS_VERSION, request=request)
    await record_consent(db, user_id, "privacy", PRIVACY_VERSION, request=request)


# -------------------------------------------------------------------
# Age gate
# -------------------------------------------------------------------

def enforce_age_gate(date_of_birth) -> str:
    """Validate a date of birth and return the guardian consent status to store.

    Raises 422 below the minimum age — refusing the account outright rather
    than creating one we would have to delete. Returns "pending" for minors and
    "not_required" for adults.
    """
    today = datetime.now(timezone.utc).date()

    if date_of_birth > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Date of birth cannot be in the future.",
        )

    if calculate_age(date_of_birth, today=today) > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid date of birth.",
        )

    if is_below_minimum_age(date_of_birth, today=today):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Kio is not available to children under 13. If you are a parent "
                "looking for support, you can create a parent account."
            ),
        )

    return "pending" if requires_guardian_consent(date_of_birth, today=today) else "not_required"


# -------------------------------------------------------------------
# Status
# -------------------------------------------------------------------

async def get_consent_status(db: AsyncSession, user: User) -> ConsentStatusResponse:
    """Everything the client needs to decide what to prompt for."""
    rows = (
        await db.execute(
            select(UserConsent)
            .where(UserConsent.user_id == user.user_id)
            .order_by(UserConsent.granted_at.desc())
        )
    ).scalars().all()

    active = [r for r in rows if r.revoked_at is None]

    def accepted(consent_type: str, version: str) -> bool:
        return any(
            r.consent_type == consent_type and r.policy_version == version
            for r in active
        )

    has_terms = accepted("terms", TERMS_VERSION)
    has_privacy = accepted("privacy", PRIVACY_VERSION)

    # Consented to *something*, just not the current text — the state that
    # should prompt a re-accept rather than a first-run consent screen.
    consented_before = any(r.consent_type in ("terms", "privacy") for r in active)

    guardian_row = next((r for r in active if r.consent_type == "guardian"), None)

    age = calculate_age(user.date_of_birth) if user.date_of_birth else None

    return ConsentStatusResponse(
        date_of_birth=user.date_of_birth,
        age=age,
        is_minor=user.guardian_consent_status in ("pending", "granted", "denied"),
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        has_accepted_terms=has_terms,
        has_accepted_privacy=has_privacy,
        needs_reconsent=consented_before and not (has_terms and has_privacy),
        guardian_consent_status=user.guardian_consent_status or "unknown",
        guardian_email=guardian_row.granted_by_email if guardian_row else None,
        records=[ConsentRecord.model_validate(r) for r in rows],
    )


# -------------------------------------------------------------------
# Guardian consent round trip
# -------------------------------------------------------------------

def _guardian_token(user: User, guardian_email: str) -> str:
    payload = {
        "sub": str(user.user_id),
        "purpose": _GUARDIAN_PURPOSE,
        "email": guardian_email.lower(),
        "exp": datetime.now(timezone.utc) + timedelta(hours=GUARDIAN_CONSENT_TOKEN_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_guardian_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This consent link is invalid or has expired. Ask your child to send a new one.",
        )

    if payload.get("purpose") != _GUARDIAN_PURPOSE:
        # A token minted for another purpose (login, password reset) must never
        # be usable to grant consent.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This consent link is invalid.",
        )
    return payload


async def request_guardian_consent(
    db: AsyncSession,
    user: User,
    guardian_email: str,
    guardian_name: str | None,
    *,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Email a guardian a one-time link to approve or decline."""
    if user.guardian_consent_status == "not_required":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account does not require guardian consent.",
        )
    if user.guardian_consent_status == "granted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guardian consent has already been granted for this account.",
        )

    token = _guardian_token(user, guardian_email)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/guardian-consent?token={token}"

    from app.email.service import try_send
    from app.email.templates import guardian_consent_email

    subject, text, html = guardian_consent_email(
        guardian_name=guardian_name or "",
        student_name=f"{user.first_name} {user.last_name}".strip(),
        link=link,
        expires_hours=GUARDIAN_CONSENT_TOKEN_HOURS,
    )

    message = {"to": guardian_email, "subject": subject, "body": text, "html": html}
    if background_tasks is not None:
        # Mail latency must not block the request, matching the signup path.
        background_tasks.add_task(try_send, **message)
    else:
        await try_send(**message)


async def get_guardian_context(
    db: AsyncSession, token: str
) -> GuardianConsentContext:
    """Resolve a consent link into what the guardian needs to see."""
    payload = _decode_guardian_token(token)
    user_id = uuid.UUID(payload["sub"])

    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found."
        )

    school_name = (
        await db.execute(
            select(Tenant.tenant_name).where(Tenant.tenant_id == user.tenant_id)
        )
    ).scalar()

    return GuardianConsentContext(
        student_first_name=user.first_name,
        student_last_name=user.last_name,
        school_name=school_name,
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        already_decided=user.guardian_consent_status in ("granted", "denied"),
    )


async def decide_guardian_consent(
    db: AsyncSession,
    token: str,
    granted: bool,
    *,
    request: Request | None = None,
) -> str:
    """Record a guardian's decision. Returns the resulting status."""
    payload = _decode_guardian_token(token)
    user_id = uuid.UUID(payload["sub"])
    guardian_email = payload.get("email")

    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found."
        )

    # A decision is final for this link. Re-deciding needs a fresh request from
    # the student, so a forwarded email cannot be used to flip the answer.
    if user.guardian_consent_status in ("granted", "denied"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A decision has already been recorded for this account.",
        )

    user.guardian_consent_status = "granted" if granted else "denied"

    if granted:
        # One row, versioned against the privacy policy. Parental consent under
        # both COPPA and DPDP is consent to the *processing of personal data*,
        # and the privacy policy is the document that describes it — the terms
        # of service govern the student's own use of the product. Recording a
        # second row against TERMS_VERSION would imply the guardian agreed to
        # something they were not actually asked about.
        await record_consent(
            db, user.user_id, "guardian", PRIVACY_VERSION,
            request=request,
            granted_by_email=guardian_email,
            verification_method=GUARDIAN_VERIFICATION_METHOD,
        )

    await db.flush()
    return user.guardian_consent_status


# -------------------------------------------------------------------
# Student profile helper
# -------------------------------------------------------------------

async def sync_student_age(db: AsyncSession, user: User) -> None:
    """Mirror the derived age onto student_profiles.

    That column predates the age gate and is read by the AI prompt builder and
    the parent insight payload. Keeping it in sync means those keep working
    without every caller learning about date_of_birth.
    """
    if user.date_of_birth is None or user.role != "student":
        return

    profile = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == user.user_id)
        )
    ).scalar_one_or_none()

    if profile is not None:
        profile.age = calculate_age(user.date_of_birth)
        await db.flush()
