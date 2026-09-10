"""
Security smoke tests: the properties that must hold across every feature.

Feature tests check that a feature works. These check the things that stay
true regardless of feature — that an unauthenticated caller gets nothing, that
roles cannot reach past themselves, and above all that the operational
plumbing added for production does not become a second, unguarded copy of the
data the product exists to protect.
"""

import logging
import uuid

import pytest
from httpx import AsyncClient

from app.auth.utils import create_access_token, hash_password
from database.models import StudentProfile, Tenant, User


# -------------------------------------------------------------------
# Authentication
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/auth/me"),
        ("get", "/counselors/schedules"),
        ("get", "/counselors/students"),
        ("get", "/analytics/overview"),
        ("get", "/admin/risk"),
        ("get", "/admin/tenants"),
        ("get", "/notifications/"),
        ("get", "/wellness/insights"),
    ],
)
@pytest.mark.asyncio
async def test_protected_endpoints_reject_anonymous_callers(client, method, path):
    response = await getattr(client, method)(path)
    assert response.status_code in (401, 403), f"{path} answered {response.status_code}"


@pytest.mark.asyncio
async def test_a_garbage_token_is_rejected(client):
    for token in ("not-a-jwt", "Bearer", "a.b.c", ""):
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        # 401 from token validation, 403 from the bearer scheme parser. Both
        # refuse; which one fires depends on how malformed the value is.
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_an_expired_access_token_is_rejected(client, db_session, test_tenant):
    from datetime import timedelta

    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"exp_{uuid.uuid4().hex[:8]}@rhs.edu",
        password_hash=hash_password("x"),
        role="student",
        first_name="Ex",
        last_name="Pired",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    expired = create_access_token(
        {"sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": "student"},
        expires_delta=timedelta(seconds=-30),
    )
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


# -------------------------------------------------------------------
# RBAC
# -------------------------------------------------------------------


def _token(user: User, role: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + create_access_token(
            {"sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": role}
        )
    }


@pytest.mark.asyncio
async def test_a_student_cannot_reach_counselor_or_admin_surfaces(
    client, test_student_user
):
    headers = _token(test_student_user, "student")
    for path in (
        "/counselors/students",
        "/counselors/schedules",
        "/counselors/sessions",
        "/admin/risk",
        "/admin/tenants",
        "/analytics/overview",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 403, f"student reached {path}"


@pytest.mark.asyncio
async def test_a_school_admin_cannot_use_platform_admin_endpoints(
    client, db_session, test_tenant
):
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"sa_{uuid.uuid4().hex[:8]}@rhs.edu",
        password_hash=hash_password("x"),
        role="school_admin",
        first_name="School",
        last_name="Admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    headers = _token(user, "school_admin")
    # Cross-tenant oversight belongs to the platform, not to one school.
    for path in ("/admin/risk", "/admin/tenants", "/admin/analytics/platform"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 403, f"school admin reached {path}"


@pytest.mark.asyncio
async def test_a_role_claim_alone_does_not_grant_access(client, test_student_user):
    """
    A student's own id with an elevated role claim must fail.

    Tokens are signed, so this is only reachable if the signing key leaks --
    but the check that matters is that authorisation is not decided by the
    claim alone downstream of the token.
    """
    forged = _token(test_student_user, "admin")
    response = await client.get("/admin/tenants", headers=forged)
    # Either the role gate or the profile lookup must refuse; a 200 would mean
    # the claim by itself was sufficient.
    assert response.status_code != 200


# -------------------------------------------------------------------
# Privacy of operational data
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_logs_record_the_path_but_never_the_query_string(
    client, caplog
):
    """
    Verification, password-reset and guardian-consent tokens all travel in the
    query string. A log line containing one is a working credential sitting in
    a file that is far more widely readable than the database.
    """
    token = "super-secret-one-time-token-value"
    with caplog.at_level(logging.INFO):
        await client.get(f"/health?token={token}")
        await client.post("/auth/verify", json={"token": token})

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert token not in combined


@pytest.mark.asyncio
async def test_a_password_never_reaches_the_logs(client, caplog):
    password = "correct-horse-battery-staple-9!"
    with caplog.at_level(logging.DEBUG):
        await client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": password}
        )

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert password not in combined


@pytest.mark.asyncio
async def test_a_bearer_token_never_reaches_the_logs(client, test_student_user, caplog):
    headers = _token(test_student_user, "student")
    raw = headers["Authorization"].split(" ", 1)[1]

    with caplog.at_level(logging.DEBUG):
        await client.get("/auth/me", headers=headers)

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert raw not in combined


@pytest.mark.asyncio
async def test_an_error_response_carries_no_internal_detail(client):
    """A 404 should say what failed, not where in the codebase."""
    response = await client.get(f"/counselors/sessions/{uuid.uuid4()}/notes")
    body = response.text
    for leak in ("Traceback", "/app/", "sqlalchemy", "asyncpg", "postgresql://"):
        assert leak not in body


# -------------------------------------------------------------------
# Safety configuration
# -------------------------------------------------------------------


def test_parent_crisis_email_is_off_by_default():
    """
    Emailing a parent that their child is at risk cannot be unsent and can out
    a student who has not chosen to tell anyone. It stays a deliberate,
    explicit decision.
    """
    from app.intelligence.config import DEFAULTS

    crisis = DEFAULTS.get("crisis", {})
    assert crisis.get("email_parents") is False
    assert crisis.get("email_staff") is True


def test_the_crisis_alert_email_names_no_student_in_its_subject():
    """Lock-screen previews show subjects to whoever is holding the phone."""
    from app.email.templates import crisis_alert_email

    subject, text, html = crisis_alert_email(
        staff_first_name="Dana",
        student_name="Riya Sharma",
        risk_level="critical",
        link="https://app.kio.example/counselor",
    )
    assert "Riya" not in subject
    assert "Sharma" not in subject

    # And the body carries no message content or categories, only who and how urgent.
    for body in (text, html):
        assert "hopeless" not in body.lower()
