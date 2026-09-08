"""
Tests for emailed one-time links: address verification and password reset.

Email delivery itself is never exercised — `try_send` is replaced with a
recorder so tests assert on what *would* have been sent (recipient, subject,
and the tokenised link) without touching a provider.
"""

from __future__ import annotations

import re
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token, hash_password
from database.models import Tenant, User

pytestmark = pytest.mark.asyncio

TOKEN_RE = re.compile(r"token=([A-Za-z0-9._\-]+)")


@pytest.fixture
def sent_emails(monkeypatch) -> list[dict]:
    """Capture outbound email instead of sending it."""
    captured: list[dict] = []

    async def fake_try_send(*, to: str, subject: str, body: str, html: str | None = None) -> bool:
        captured.append({"to": to, "subject": subject, "body": body, "html": html})
        return True

    monkeypatch.setattr("app.auth.service.try_send", fake_try_send)
    return captured


def link_token(email: dict) -> str:
    """Pull the one-time token out of a captured email body."""
    match = TOKEN_RE.search(email["body"])
    assert match, f"no token found in email body: {email['body'][:200]}"
    return match.group(1)


async def signup_student(client: AsyncClient, tenant: Tenant) -> tuple[str, str]:
    """Register a student; returns (email, password)."""
    email = f"verify_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPassword123!"
    resp = await client.post("/auth/signup", json={
        "email": email,
        "password": password,
        "first_name": "Verify",
        "last_name": "Tester",
        "role": "student",
        "phone": "+919876543210",
        "school_code": tenant.school_code,
        "date_of_birth": "2000-01-01",
        "accept_terms": True,
        "accept_privacy": True,
    })
    assert resp.status_code == 201, resp.text
    return email, password


# -------------------------------------------------------------------
# Email verification
# -------------------------------------------------------------------

async def test_signup_sends_verification_link(client, test_tenant, sent_emails):
    email, _ = await signup_student(client, test_tenant)

    assert len(sent_emails) == 1
    message = sent_emails[0]
    assert message["to"] == email
    assert "verify" in message["subject"].lower()
    assert "/verify-email?token=" in message["body"]


async def test_signup_response_reports_unverified(client, test_tenant, sent_emails):
    email = f"unver_{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post("/auth/signup", json={
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Un",
        "last_name": "Verified",
        "role": "student",
        "phone": "+919876543210",
        "school_code": test_tenant.school_code,
        "date_of_birth": "2000-01-01",
        "accept_terms": True,
        "accept_privacy": True,
    })
    assert resp.status_code == 201
    assert resp.json()["user"]["is_verified"] is False


async def test_verify_marks_user_verified(client, test_tenant, sent_emails):
    email, password = await signup_student(client, test_tenant)
    token = link_token(sent_emails[0])

    resp = await client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"

    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.json()["user"]["is_verified"] is True


async def test_verify_is_idempotent(client, test_tenant, sent_emails):
    await signup_student(client, test_tenant)
    token = link_token(sent_emails[0])

    assert (await client.post("/auth/verify", json={"token": token})).status_code == 200
    assert (await client.post("/auth/verify", json={"token": token})).status_code == 200


async def test_verify_rejects_token_with_wrong_purpose(client, test_student_user):
    # A normal access token must not double as a verification link.
    token = create_access_token({"sub": str(test_student_user.user_id)})
    resp = await client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 400
    assert "invalid or has expired" in resp.json()["detail"].lower()


async def test_verify_rejects_garbage_token(client):
    resp = await client.post("/auth/verify", json={"token": "not-a-real-jwt-at-all"})
    assert resp.status_code == 400


async def test_resend_verification_sends_again(client, test_tenant, sent_emails):
    email, password = await signup_student(client, test_tenant)
    login = await client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

    sent_emails.clear()
    resp = await client.post("/auth/verify/resend", headers=headers)
    assert resp.status_code == 200
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == email


async def test_resend_verification_conflicts_when_already_verified(
    client, test_tenant, sent_emails
):
    email, password = await signup_student(client, test_tenant)
    await client.post("/auth/verify", json={"token": link_token(sent_emails[0])})

    login = await client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

    resp = await client.post("/auth/verify/resend", headers=headers)
    assert resp.status_code == 409


async def test_resend_verification_requires_auth(client):
    assert (await client.post("/auth/verify/resend")).status_code in (401, 403)


# -------------------------------------------------------------------
# Password reset
# -------------------------------------------------------------------

async def test_forgot_password_sends_link(client, test_tenant, sent_emails):
    email, _ = await signup_student(client, test_tenant)
    sent_emails.clear()

    resp = await client.post("/auth/password/forgot", json={"email": email})
    assert resp.status_code == 200
    assert len(sent_emails) == 1
    assert "/reset-password?token=" in sent_emails[0]["body"]


async def test_forgot_password_does_not_leak_unknown_accounts(client, sent_emails):
    """Unknown addresses get the same 200 and no email — no enumeration oracle."""
    resp = await client.post(
        "/auth/password/forgot", json={"email": "nobody-here@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert sent_emails == []


async def test_password_reset_changes_the_password(client, test_tenant, sent_emails):
    email, old_password = await signup_student(client, test_tenant)
    sent_emails.clear()
    await client.post("/auth/password/forgot", json={"email": email})
    token = link_token(sent_emails[0])

    new_password = "BrandNewPassword456!"
    resp = await client.post("/auth/password/reset", json={"token": token, "password": new_password})
    assert resp.status_code == 200

    assert (await client.post(
        "/auth/login", json={"email": email, "password": old_password}
    )).status_code == 401
    ok = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert ok.status_code == 200


async def test_password_reset_link_is_single_use(client, test_tenant, sent_emails):
    email, _ = await signup_student(client, test_tenant)
    sent_emails.clear()
    await client.post("/auth/password/forgot", json={"email": email})
    token = link_token(sent_emails[0])

    first = await client.post(
        "/auth/password/reset", json={"token": token, "password": "FirstNewPassword1!"}
    )
    assert first.status_code == 200

    replay = await client.post(
        "/auth/password/reset", json={"token": token, "password": "SecondNewPassword2!"}
    )
    assert replay.status_code == 400


async def test_completed_reset_also_verifies_the_email(client, test_tenant, sent_emails):
    email, _ = await signup_student(client, test_tenant)
    sent_emails.clear()
    await client.post("/auth/password/forgot", json={"email": email})
    token = link_token(sent_emails[0])

    new_password = "ProvesInboxControl9!"
    await client.post("/auth/password/reset", json={"token": token, "password": new_password})

    login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert login.json()["user"]["is_verified"] is True


async def test_password_reset_rejects_short_password(client, test_tenant, sent_emails):
    email, _ = await signup_student(client, test_tenant)
    sent_emails.clear()
    await client.post("/auth/password/forgot", json={"email": email})
    token = link_token(sent_emails[0])

    resp = await client.post("/auth/password/reset", json={"token": token, "password": "short"})
    assert resp.status_code == 422


async def test_google_only_account_gets_no_reset_email(
    client, db_session: AsyncSession, test_tenant, sent_emails
):
    email = f"google_{uuid.uuid4().hex[:8]}@test.com"
    db_session.add(User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=email,
        password_hash=None,
        google_sub=f"sub-{uuid.uuid4().hex}",
        auth_provider="google",
        role="student",
        first_name="Google",
        last_name="User",
        is_verified=True,
    ))
    await db_session.flush()

    resp = await client.post("/auth/password/forgot", json={"email": email})
    assert resp.status_code == 200  # same response as any other address
    assert sent_emails == []


async def test_reset_rejected_for_google_only_account(
    client, db_session: AsyncSession, test_tenant
):
    user_id = uuid.uuid4()
    db_session.add(User(
        user_id=user_id,
        tenant_id=test_tenant.tenant_id,
        email=f"google2_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=None,
        google_sub=f"sub-{uuid.uuid4().hex}",
        auth_provider="google",
        role="student",
        first_name="Google",
        last_name="User",
        is_verified=True,
    ))
    await db_session.flush()

    token = create_access_token(
        {"sub": str(user_id), "purpose": "password_reset", "pwf": "whatever"}
    )
    resp = await client.post(
        "/auth/password/reset", json={"token": token, "password": "NewPassword123!"}
    )
    assert resp.status_code == 400
    assert "google" in resp.json()["detail"].lower()


async def test_reset_rejects_token_with_wrong_purpose(client, test_student_user):
    token = create_access_token({"sub": str(test_student_user.user_id), "purpose": "email_verify"})
    resp = await client.post(
        "/auth/password/reset", json={"token": token, "password": "NewPassword123!"}
    )
    assert resp.status_code == 400


async def test_reset_rejects_tampered_fingerprint(
    client, db_session: AsyncSession, test_student_user
):
    """A token minted against a different password hash must not work."""
    token = create_access_token(
        {"sub": str(test_student_user.user_id), "purpose": "password_reset", "pwf": "0" * 16}
    )
    resp = await client.post(
        "/auth/password/reset", json={"token": token, "password": "NewPassword123!"}
    )
    assert resp.status_code == 400


# -------------------------------------------------------------------
# Provider selection
# -------------------------------------------------------------------

async def test_resend_provider_falls_back_to_noop_without_api_key(monkeypatch):
    from app.email import service as email_service

    monkeypatch.setattr(email_service.settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(email_service.settings, "RESEND_API_KEY", "")
    email_service.reset_email_service()

    assert email_service.get_email_service().name == "noop"
    email_service.reset_email_service()


async def test_resend_provider_selected_when_configured(monkeypatch):
    from app.email import service as email_service

    monkeypatch.setattr(email_service.settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(email_service.settings, "RESEND_API_KEY", "re_test_key")
    email_service.reset_email_service()

    assert email_service.get_email_service().name == "resend"
    email_service.reset_email_service()
