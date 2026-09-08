"""
Kio Consent Router.

The guardian endpoints are deliberately unauthenticated: the person deciding is
a parent who has no Kio account and never will. Their authorisation is the
signed, expiring token in the emailed link, which is why decisions are one-shot
(see decide_guardian_consent).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.consent.policy import PRIVACY_VERSION, TERMS_VERSION
from app.consent.schemas import (
    AcceptPolicyRequest,
    ConsentStatusResponse,
    GuardianConsentContext,
    GuardianConsentDecision,
    GuardianConsentRequest,
)
from app.consent.service import (
    decide_guardian_consent,
    get_consent_status,
    get_guardian_context,
    record_consent,
    request_guardian_consent,
)
from app.dependencies import CurrentUser
from app.rate_limit import rate_limit
from database.session import get_db

router = APIRouter()


@router.get("/policies")
async def get_policy_versions():
    """Current published policy versions.

    Public: the login and signup screens need it before anyone is authenticated.
    """
    return {"terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION}


@router.get("/me", response_model=ConsentStatusResponse)
async def my_consent_status(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """What the signed-in user has consented to, and what is still outstanding."""
    return await get_consent_status(db, current_user)


@router.post("/accept", response_model=ConsentStatusResponse)
async def accept_policies(
    payload: AcceptPolicyRequest,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Accept the current terms and/or privacy versions.

    Used for re-consent after a policy version bumps, and by accounts created
    before the consent layer existed.
    """
    if payload.accept_terms:
        await record_consent(
            db, current_user.user_id, "terms", TERMS_VERSION, request=request
        )
    if payload.accept_privacy:
        await record_consent(
            db, current_user.user_id, "privacy", PRIVACY_VERSION, request=request
        )
    return await get_consent_status(db, current_user)


# -------------------------------------------------------------------
# Guardian consent
# -------------------------------------------------------------------

@router.post(
    "/guardian/request",
    status_code=202,
    dependencies=[Depends(rate_limit("guardian_consent", 5))],
)
async def send_guardian_request(
    payload: GuardianConsentRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Email a guardian a link to approve or decline this account."""
    await request_guardian_consent(
        db,
        current_user,
        payload.guardian_email,
        payload.guardian_name,
        background_tasks=background_tasks,
    )
    return {"status": "sent", "guardian_email": payload.guardian_email}


@router.get("/guardian/context", response_model=GuardianConsentContext)
async def guardian_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., min_length=10),
):
    """Resolve an emailed consent link into what the guardian needs to see.

    Unauthenticated by design — the token is the authorisation.
    """
    return await get_guardian_context(db, token)


@router.post(
    "/guardian/decide",
    dependencies=[Depends(rate_limit("guardian_decide", 10))],
)
async def guardian_decide(
    payload: GuardianConsentDecision,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Record the guardian's decision. One-shot per account."""
    result = await decide_guardian_consent(
        db, payload.token, payload.granted, request=request
    )
    return {"guardian_consent_status": result}
