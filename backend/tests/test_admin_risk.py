"""
Cross-tenant risk oversight for the platform admin.

The reason this endpoint exists: /risk/queue filters on the CALLER's tenant, so
a platform admin calling it sees their own (empty) queue rather than the
platform. These tests pin the cross-tenant behaviour and the ordering that
makes the view useful — most severe first, then oldest, so stale rows surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token, hash_password
from database.models import RiskAssessment, StudentProfile, Tenant, User

pytestmark = pytest.mark.asyncio


async def _school_with_student(
    db: AsyncSession, name: str
) -> tuple[Tenant, StudentProfile, User]:
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name=name,
        tenant_type="school",
        school_code=f"RK{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(tenant)
    await db.flush()

    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=f"s_{uuid.uuid4().hex[:10]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="student",
        first_name="Riya",
        last_name="Sharma",
    )
    db.add(user)
    await db.flush()

    profile = StudentProfile(user_id=user.user_id, risk_level="green")
    db.add(profile)
    await db.flush()
    return tenant, profile, user


async def _assessment(
    db: AsyncSession,
    profile: StudentProfile,
    *,
    level: str = "red",
    review_status: str | None = "pending",
    created_at: datetime | None = None,
) -> RiskAssessment:
    row = RiskAssessment(
        student_id=profile.student_id,
        risk_level=level,
        risk_score=80,
        review_status=review_status,
        summary="AI summary text",
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


# -------------------------------------------------------------------
# Access control
# -------------------------------------------------------------------

async def test_counselor_cannot_use_the_admin_risk_list(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
):
    counselor = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"c_{uuid.uuid4().hex[:10]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="counselor",
        first_name="C",
        last_name="One",
    )
    db_session.add(counselor)
    await db_session.flush()

    token = create_access_token({
        "sub": str(counselor.user_id),
        "tenant_id": str(test_tenant.tenant_id),
        "role": "counselor",
    })

    resp = await client.get(
        "/admin/risk", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


# -------------------------------------------------------------------
# Cross-tenant reach
# -------------------------------------------------------------------

async def test_admin_sees_assessments_from_every_school(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    """The whole point: the risk does not live in the admin's own tenant."""
    _school_a, profile_a, _ = await _school_with_student(db_session, "Alpha High")
    _school_b, profile_b, _ = await _school_with_student(db_session, "Beta High")
    await _assessment(db_session, profile_a, level="red")
    await _assessment(db_session, profile_b, level="critical")

    resp = await client.get("/admin/risk", headers=admin_auth_headers)
    assert resp.status_code == 200

    schools = {item["school_name"] for item in resp.json()["items"]}
    assert {"Alpha High", "Beta High"} <= schools


async def test_rows_carry_school_and_student_names(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    await _school_with_student(db_session, "Gamma High")
    _school, profile, _user = await _school_with_student(db_session, "Gamma Two")
    await _assessment(db_session, profile)

    body = (await client.get("/admin/risk", headers=admin_auth_headers)).json()
    row = next(i for i in body["items"] if i["school_name"] == "Gamma Two")

    assert row["student_name"] == "Riya Sharma"
    assert row["risk_level"] == "red"
    assert row["age_hours"] >= 0


# -------------------------------------------------------------------
# Ordering
# -------------------------------------------------------------------

async def test_most_severe_first_then_oldest(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    """Severity outranks age, but within a tier the stalest row wins — this
    view exists to surface what has been waiting."""
    _school, profile, _user = await _school_with_student(db_session, "Delta High")
    now = datetime.now(timezone.utc)

    await _assessment(db_session, profile, level="yellow", created_at=now)
    new_red = await _assessment(db_session, profile, level="red", created_at=now)
    old_red = await _assessment(
        db_session, profile, level="red", created_at=now - timedelta(days=3)
    )
    critical = await _assessment(db_session, profile, level="critical", created_at=now)

    body = (await client.get(
        "/admin/risk",
        headers=admin_auth_headers,
        params={"tenant_id": str(_school.tenant_id)},
    )).json()
    ids = [i["risk_id"] for i in body["items"]]

    assert ids[0] == str(critical.risk_id)
    # Older red before newer red.
    assert ids.index(str(old_red.risk_id)) < ids.index(str(new_red.risk_id))


# -------------------------------------------------------------------
# Filters
# -------------------------------------------------------------------

async def test_filter_by_status_and_level(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    _school, profile, _user = await _school_with_student(db_session, "Eps High")
    await _assessment(db_session, profile, level="red", review_status="pending")
    await _assessment(db_session, profile, level="green", review_status="resolved")

    pending = (await client.get(
        "/admin/risk", headers=admin_auth_headers, params={"review_status": "pending"}
    )).json()
    assert pending["items"]
    assert all(i["review_status"] == "pending" for i in pending["items"])

    green = (await client.get(
        "/admin/risk", headers=admin_auth_headers, params={"risk_level": "green"}
    )).json()
    assert green["items"]
    assert all(i["risk_level"] == "green" for i in green["items"])


async def test_filter_by_school(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    school_a, profile_a, _ = await _school_with_student(db_session, "Zeta High")
    _school_b, profile_b, _ = await _school_with_student(db_session, "Eta High")
    await _assessment(db_session, profile_a)
    await _assessment(db_session, profile_b)

    body = (await client.get(
        "/admin/risk",
        headers=admin_auth_headers,
        params={"tenant_id": str(school_a.tenant_id)},
    )).json()

    assert body["items"]
    assert {i["school_name"] for i in body["items"]} == {"Zeta High"}


# -------------------------------------------------------------------
# Detail
# -------------------------------------------------------------------

async def test_detail_returns_ai_assessment_not_message_content(
    client: AsyncClient, db_session: AsyncSession, admin_auth_headers
):
    _school, profile, _user = await _school_with_student(db_session, "Theta High")
    row = await _assessment(db_session, profile)

    resp = await client.get(f"/admin/risk/{row.risk_id}", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["risk_id"] == str(row.risk_id)
    assert body["summary"] == "AI summary text"
    # The raw conversation stays behind the separate audit-logged break-glass
    # endpoint — it must not leak into risk oversight.
    assert "messages" not in body


async def test_detail_404s_for_unknown_id(client: AsyncClient, admin_auth_headers):
    resp = await client.get(
        f"/admin/risk/{uuid.uuid4()}", headers=admin_auth_headers
    )
    assert resp.status_code == 404
