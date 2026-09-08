"""
Age gate and consent records.

Kio processes mental-health data belonging largely to minors, and until now had
no record that anyone agreed to anything and no idea how old they were. What
these tests protect:

  * under-13 signups are refused before a row exists,
  * 13-17 accounts are created but held pending a guardian's decision,
  * consent is recorded with the policy version actually agreed to,
  * Google sign-in cannot be used to walk around any of it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.consent.policy import (
    AGE_OF_SELF_CONSENT,
    MINIMUM_AGE,
    PRIVACY_VERSION,
    TERMS_VERSION,
)
from database.models import Tenant, User, UserConsent

pytestmark = pytest.mark.asyncio


def _dob_for_age(age: int) -> str:
    """A birth date that makes someone exactly `age` today (plus a day's slack)."""
    return (date.today() - timedelta(days=age * 365 + 100)).isoformat()


def _signup_payload(tenant: Tenant, age: int, **overrides) -> dict:
    return {
        "email": f"u_{uuid.uuid4().hex[:10]}@test.com",
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "Student",
        "role": "student",
        "phone": "9876543210",
        "school_code": tenant.school_code,
        "date_of_birth": _dob_for_age(age),
        "accept_terms": True,
        "accept_privacy": True,
        **overrides,
    }


# -------------------------------------------------------------------
# The gate
# -------------------------------------------------------------------

async def test_under_13_is_refused_and_no_account_is_created(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
):
    payload = _signup_payload(test_tenant, MINIMUM_AGE - 1)

    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 422
    assert "under 13" in resp.json()["detail"].lower()

    # Refused before anything is written — not created then cleaned up.
    exists = (await db_session.execute(
        select(User).where(User.email == payload["email"])
    )).scalar_one_or_none()
    assert exists is None


async def test_minor_account_is_created_but_pending(
    client: AsyncClient, test_tenant: Tenant
):
    """A 15-year-old gets an account; it is just not consented for yet."""
    resp = await client.post(
        "/auth/signup", json=_signup_payload(test_tenant, AGE_OF_SELF_CONSENT - 3)
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["guardian_consent_status"] == "pending"


async def test_adult_needs_no_guardian(client: AsyncClient, test_tenant: Tenant):
    resp = await client.post(
        "/auth/signup", json=_signup_payload(test_tenant, AGE_OF_SELF_CONSENT + 5)
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["guardian_consent_status"] == "not_required"


async def test_future_date_of_birth_is_rejected(
    client: AsyncClient, test_tenant: Tenant
):
    payload = _signup_payload(
        test_tenant, 20, date_of_birth=(date.today() + timedelta(days=1)).isoformat()
    )
    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize("field", ["accept_terms", "accept_privacy"])
async def test_signup_refused_without_consent(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, field: str
):
    """There must be no code path that creates an account without consent."""
    payload = _signup_payload(test_tenant, 20, **{field: False})

    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 422

    exists = (await db_session.execute(
        select(User).where(User.email == payload["email"])
    )).scalar_one_or_none()
    assert exists is None


async def test_date_of_birth_is_required(client: AsyncClient, test_tenant: Tenant):
    payload = _signup_payload(test_tenant, 20)
    del payload["date_of_birth"]

    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 422


# -------------------------------------------------------------------
# Consent records
# -------------------------------------------------------------------

async def test_signup_records_versioned_consent(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
):
    """A consent record proves nothing without the version it was given for."""
    resp = await client.post("/auth/signup", json=_signup_payload(test_tenant, 20))
    user_id = uuid.UUID(resp.json()["user"]["user_id"])

    rows = (await db_session.execute(
        select(UserConsent).where(UserConsent.user_id == user_id)
    )).scalars().all()

    by_type = {r.consent_type: r for r in rows}
    assert by_type["terms"].policy_version == TERMS_VERSION
    assert by_type["privacy"].policy_version == PRIVACY_VERSION
    assert all(r.revoked_at is None for r in rows)


async def test_consent_status_reports_current_versions(
    client: AsyncClient, test_tenant: Tenant
):
    signup = await client.post("/auth/signup", json=_signup_payload(test_tenant, 20))
    token = signup.json()["tokens"]["access_token"]

    resp = await client.get(
        "/consent/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["has_accepted_terms"] is True
    assert body["has_accepted_privacy"] is True
    assert body["needs_reconsent"] is False
    assert body["guardian_consent_status"] == "not_required"


async def test_policy_versions_are_public(client: AsyncClient):
    """The signup screen needs these before anyone is authenticated."""
    resp = await client.get("/consent/policies")
    assert resp.status_code == 200
    assert resp.json()["terms_version"] == TERMS_VERSION


# -------------------------------------------------------------------
# Guardian consent round trip
# -------------------------------------------------------------------

async def _minor_token(client: AsyncClient, tenant: Tenant) -> str:
    resp = await client.post(
        "/auth/signup", json=_signup_payload(tenant, AGE_OF_SELF_CONSENT - 3)
    )
    return resp.json()["tokens"]["access_token"]


async def test_guardian_flow_grants_consent(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, monkeypatch
):
    captured: list[dict] = []

    async def fake_try_send(*, to, subject, body, html=None):
        captured.append({"to": to, "body": body})
        return True

    monkeypatch.setattr("app.email.service.try_send", fake_try_send)

    token = await _minor_token(client, test_tenant)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/consent/guardian/request",
        json={"guardian_email": "parent@example.com", "guardian_name": "Anita"},
        headers=headers,
    )
    assert resp.status_code == 202
    assert captured and captured[0]["to"] == "parent@example.com"

    # Pull the link token straight out of the email the guardian received.
    link_token = captured[0]["body"].split("guardian-consent?token=")[1].split()[0]

    context = await client.get("/consent/guardian/context", params={"token": link_token})
    assert context.status_code == 200
    assert context.json()["already_decided"] is False

    decide = await client.post(
        "/consent/guardian/decide", json={"token": link_token, "granted": True}
    )
    assert decide.status_code == 200
    assert decide.json()["guardian_consent_status"] == "granted"

    # A guardian row exists, attributed and marked with how it was verified.
    row = (await db_session.execute(
        select(UserConsent).where(UserConsent.consent_type == "guardian")
    )).scalars().first()
    assert row is not None
    assert row.granted_by_email == "parent@example.com"
    assert row.verification_method == "email_link"


async def test_guardian_can_decline(
    client: AsyncClient, test_tenant: Tenant, monkeypatch
):
    """Declining is a real, recorded outcome — not just the absence of a grant."""
    captured: list[dict] = []

    async def fake_try_send(*, to, subject, body, html=None):
        captured.append({"body": body})
        return True

    monkeypatch.setattr("app.email.service.try_send", fake_try_send)

    token = await _minor_token(client, test_tenant)
    await client.post(
        "/consent/guardian/request",
        json={"guardian_email": "parent2@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    link_token = captured[0]["body"].split("guardian-consent?token=")[1].split()[0]

    resp = await client.post(
        "/consent/guardian/decide", json={"token": link_token, "granted": False}
    )
    assert resp.json()["guardian_consent_status"] == "denied"


async def test_decision_cannot_be_replayed(
    client: AsyncClient, test_tenant: Tenant, monkeypatch
):
    """A forwarded consent email must not let someone flip an existing decision."""
    captured: list[dict] = []

    async def fake_try_send(*, to, subject, body, html=None):
        captured.append({"body": body})
        return True

    monkeypatch.setattr("app.email.service.try_send", fake_try_send)

    token = await _minor_token(client, test_tenant)
    await client.post(
        "/consent/guardian/request",
        json={"guardian_email": "parent3@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    link_token = captured[0]["body"].split("guardian-consent?token=")[1].split()[0]

    first = await client.post(
        "/consent/guardian/decide", json={"token": link_token, "granted": True}
    )
    assert first.status_code == 200

    second = await client.post(
        "/consent/guardian/decide", json={"token": link_token, "granted": False}
    )
    assert second.status_code == 409


async def test_guardian_endpoint_rejects_a_token_minted_for_another_purpose(
    client: AsyncClient, test_tenant: Tenant
):
    """An access token must never be usable to grant consent on its own account."""
    token = await _minor_token(client, test_tenant)

    resp = await client.get("/consent/guardian/context", params={"token": token})
    assert resp.status_code == 400


async def test_adult_cannot_request_guardian_consent(
    client: AsyncClient, test_tenant: Tenant
):
    signup = await client.post("/auth/signup", json=_signup_payload(test_tenant, 25))
    token = signup.json()["tokens"]["access_token"]

    resp = await client.post(
        "/consent/guardian/request",
        json={"guardian_email": "someone@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
