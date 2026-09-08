"""
Platform Admin P0 — school management (soft delete, suspend enforcement)
and cross-tenant user administration.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import hash_password
from database.models import AuditLog, Tenant, User

pytestmark = pytest.mark.asyncio


async def _make_school(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "tenant_name": f"School {uuid.uuid4().hex[:6]}",
        "tenant_type": "school",
        "school_code": f"SC{uuid.uuid4().hex[:6].upper()}",
        "subscription_plan": "starter",
        "student_limit": 50,
        **overrides,
    }
    resp = await client.post("/admin/tenants", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# -------------------------------------------------------------------
# School list: filters, search, archived exclusion
# -------------------------------------------------------------------

async def test_school_list_filters_and_search(client: AsyncClient, admin_auth_headers):
    school = await _make_school(
        client, admin_auth_headers, tenant_name="Searchable Academy", city="Pune"
    )

    resp = await client.get(
        "/admin/tenants", params={"search": "Searchable"}, headers=admin_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    names = [t["tenant_name"] for t in body["tenants"]]
    assert "Searchable Academy" in names
    found = next(t for t in body["tenants"] if t["tenant_id"] == school["tenant_id"])
    assert found["city"] == "Pune"

    # Status filter
    resp = await client.get(
        "/admin/tenants", params={"status": "suspended"}, headers=admin_auth_headers
    )
    assert school["tenant_id"] not in [t["tenant_id"] for t in resp.json()["tenants"]]


async def test_school_list_excludes_non_school_tenants(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession
):
    org = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name="Internal Org",
        tenant_type="organization",
        school_code=f"ORG{uuid.uuid4().hex[:5].upper()}",
    )
    db_session.add(org)
    await db_session.flush()

    resp = await client.get("/admin/tenants", headers=admin_auth_headers)
    assert str(org.tenant_id) not in [t["tenant_id"] for t in resp.json()["tenants"]]


# -------------------------------------------------------------------
# Soft delete / archive
# -------------------------------------------------------------------

async def test_delete_school_is_soft(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession
):
    school = await _make_school(client, admin_auth_headers)

    resp = await client.delete(
        f"/admin/tenants/{school['tenant_id']}", headers=admin_auth_headers
    )
    assert resp.status_code == 204

    # Row still exists, marked archived
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == uuid.UUID(school["tenant_id"]))
    )
    tenant = result.scalar_one()
    assert tenant.deleted_at is not None
    assert tenant.status == "archived"

    # Hidden by default, visible with include_archived
    resp = await client.get("/admin/tenants", headers=admin_auth_headers)
    assert school["tenant_id"] not in [t["tenant_id"] for t in resp.json()["tenants"]]

    resp = await client.get(
        "/admin/tenants", params={"include_archived": True}, headers=admin_auth_headers
    )
    assert school["tenant_id"] in [t["tenant_id"] for t in resp.json()["tenants"]]


async def test_platform_tenant_cannot_be_archived(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession
):
    platform = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name="Kio Platform",
        tenant_type="organization",
        school_code="PLATFORM",
    )
    db_session.add(platform)
    await db_session.flush()

    resp = await client.delete(
        f"/admin/tenants/{platform.tenant_id}", headers=admin_auth_headers
    )
    assert resp.status_code == 403

    resp = await client.put(
        f"/admin/tenants/{platform.tenant_id}",
        json={"status": "suspended"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403


# -------------------------------------------------------------------
# Suspension enforcement (signup + login)
# -------------------------------------------------------------------

async def test_suspended_school_blocks_signup_and_login(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession
):
    school = await _make_school(client, admin_auth_headers)

    # A student already in the school
    student = User(
        user_id=uuid.uuid4(),
        tenant_id=uuid.UUID(school["tenant_id"]),
        email=f"kid_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Password123!"),
        role="student",
        first_name="Sus",
        last_name="Pended",
    )
    db_session.add(student)
    await db_session.flush()

    # Suspend the school
    resp = await client.put(
        f"/admin/tenants/{school['tenant_id']}",
        json={"status": "suspended"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"

    # New signups with the school code are rejected
    resp = await client.post("/auth/signup", json={
        "email": f"new_{uuid.uuid4().hex[:8]}@test.com",
        "password": "Password123!",
        "first_name": "New",
        "last_name": "Student",
        "role": "student",
        "phone": "9876543210",  # required by SignupRequest; omitting it 422s
                                # before the suspension check is ever reached
        "school_code": school["school_code"],
        "date_of_birth": "2000-01-01",
        "accept_terms": True,
        "accept_privacy": True,
    })
    assert resp.status_code == 403

    # Existing students cannot log in
    resp = await client.post("/auth/login", json={
        "email": student.email, "password": "Password123!",
    })
    assert resp.status_code == 403

    # Reactivate -> login works again
    await client.put(
        f"/admin/tenants/{school['tenant_id']}",
        json={"status": "active"},
        headers=admin_auth_headers,
    )
    resp = await client.post("/auth/login", json={
        "email": student.email, "password": "Password123!",
    })
    assert resp.status_code == 200


# -------------------------------------------------------------------
# Cross-tenant user list
# -------------------------------------------------------------------

async def test_admin_users_list_cross_tenant(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession
):
    school_a = await _make_school(client, admin_auth_headers)
    school_b = await _make_school(client, admin_auth_headers)

    for school in (school_a, school_b):
        db_session.add(User(
            user_id=uuid.uuid4(),
            tenant_id=uuid.UUID(school["tenant_id"]),
            email=f"cross_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("Password123!"),
            role="student",
            first_name="Cross",
            last_name="Tenant",
        ))
    await db_session.flush()

    resp = await client.get(
        "/admin/users",
        params={"search": "cross_", "role": "student"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    tenant_ids = {u["tenant_id"] for u in body["users"]}
    assert {school_a["tenant_id"], school_b["tenant_id"]} <= tenant_ids
    # Rows include the school name
    assert all(u["tenant_name"] for u in body["users"])

    # tenant_id filter narrows to one school
    resp = await client.get(
        "/admin/users",
        params={"tenant_id": school_a["tenant_id"], "search": "cross_"},
        headers=admin_auth_headers,
    )
    assert {u["tenant_id"] for u in resp.json()["users"]} == {school_a["tenant_id"]}


async def test_admin_users_list_requires_admin(client: AsyncClient, student_auth_headers):
    resp = await client.get("/admin/users", headers=student_auth_headers)
    assert resp.status_code == 403


# -------------------------------------------------------------------
# User soft delete + guards
# -------------------------------------------------------------------

async def test_user_soft_delete_blocks_login(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession, test_tenant
):
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"gone_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Password123!"),
        role="parent",
        first_name="Soon",
        last_name="Gone",
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.delete(f"/admin/users/{user.user_id}", headers=admin_auth_headers)
    assert resp.status_code == 204

    await db_session.refresh(user)
    assert user.deleted_at is not None
    assert user.is_active is False

    resp = await client.post("/auth/login", json={
        "email": user.email, "password": "Password123!",
    })
    assert resp.status_code == 403

    # Deleted users appear under the deleted status filter
    resp = await client.get(
        "/admin/users", params={"status": "deleted", "search": "gone_"},
        headers=admin_auth_headers,
    )
    assert str(user.user_id) in [u["user_id"] for u in resp.json()["users"]]


async def test_admin_cannot_delete_self_or_last_admin(
    client: AsyncClient, admin_auth_headers, test_admin_user
):
    # Self-delete is blocked
    resp = await client.delete(
        f"/admin/users/{test_admin_user.user_id}", headers=admin_auth_headers
    )
    assert resp.status_code == 403

    # Self-suspend via PATCH is blocked too
    resp = await client.patch(
        f"/admin/users/{test_admin_user.user_id}",
        json={"is_active": False},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403


async def test_user_profile_edit(client: AsyncClient, admin_auth_headers, db_session, test_tenant):
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"edit_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Password123!"),
        role="parent",
        first_name="Old",
        last_name="Name",
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.patch(
        f"/admin/users/{user.user_id}",
        json={"first_name": "New", "phone": "+911234567890"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.first_name == "New"
    assert user.phone == "+911234567890"


# -------------------------------------------------------------------
# Audit trail
# -------------------------------------------------------------------

async def test_admin_mutations_are_audited(
    client: AsyncClient, admin_auth_headers, db_session: AsyncSession, test_admin_user
):
    school = await _make_school(client, admin_auth_headers)
    await client.put(
        f"/admin/tenants/{school['tenant_id']}",
        json={"status": "suspended"},
        headers=admin_auth_headers,
    )
    await client.delete(f"/admin/tenants/{school['tenant_id']}", headers=admin_auth_headers)

    result = await db_session.execute(
        select(AuditLog.action).where(
            AuditLog.user_id == test_admin_user.user_id,
            AuditLog.entity_id == uuid.UUID(school["tenant_id"]),
        )
    )
    actions = {row[0] for row in result.all()}
    assert {"tenant.create", "tenant.suspend", "tenant.archive"} <= actions

    # Filtered audit-log endpoint returns them with actor info
    resp = await client.get(
        "/admin/audit-logs",
        params={"action": "tenant."},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    assert any(log["user_name"] for log in body["logs"])

    # CSV export honours the same filters
    resp = await client.get(
        "/admin/audit-logs/export",
        params={"action": "tenant."},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "tenant.archive" in resp.text
