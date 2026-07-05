"""
MindBridge Guardian Management Tests
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.utils import create_access_token, hash_password
from database.models import ParentProfile, Tenant, User


@pytest_asyncio.fixture
async def test_parent_user(db_session, test_tenant: Tenant) -> User:
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"gparent_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="parent", first_name="Guard", last_name="Parent",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ParentProfile(user_id=user.user_id))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def parent_auth_headers(test_parent_user: User) -> dict[str, str]:
    token = create_access_token({
        "sub": str(test_parent_user.user_id),
        "tenant_id": str(test_parent_user.tenant_id),
        "role": "parent",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_guardian_crud(client: AsyncClient, student_auth_headers):
    # Create
    create = await client.post("/linking/guardians", json={
        "name": "Mary Doe", "email": "mary@example.com", "phone": "+1 555 111 2222",
        "relationship": "mother", "is_primary": True,
    }, headers=student_auth_headers)
    assert create.status_code == 201
    gid = create.json()["guardian_id"]
    assert create.json()["is_primary"] is True

    # List
    lst = await client.get("/linking/guardians", headers=student_auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["guardians"]) == 1

    # Update
    upd = await client.patch(f"/linking/guardians/{gid}", json={"phone": "+1 999 000 1111"},
                             headers=student_auth_headers)
    assert upd.status_code == 200
    assert upd.json()["phone"] == "+1 999 000 1111"

    # Delete
    dele = await client.delete(f"/linking/guardians/{gid}", headers=student_auth_headers)
    assert dele.status_code == 204
    empty = await client.get("/linking/guardians", headers=student_auth_headers)
    assert empty.json()["guardians"] == []


@pytest.mark.asyncio
async def test_only_one_primary_guardian(client: AsyncClient, student_auth_headers):
    await client.post("/linking/guardians", json={
        "name": "A", "relationship": "mother", "is_primary": True,
    }, headers=student_auth_headers)
    await client.post("/linking/guardians", json={
        "name": "B", "relationship": "father", "is_primary": True,
    }, headers=student_auth_headers)

    lst = await client.get("/linking/guardians", headers=student_auth_headers)
    primaries = [g for g in lst.json()["guardians"] if g["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["name"] == "B"


@pytest.mark.asyncio
async def test_guardian_code_redeem_marks_linked(
    client: AsyncClient, student_auth_headers, parent_auth_headers
):
    create = await client.post("/linking/guardians", json={
        "name": "Dad", "relationship": "father",
    }, headers=student_auth_headers)
    gid = create.json()["guardian_id"]

    code_resp = await client.post(f"/linking/guardians/{gid}/invite-code", headers=student_auth_headers)
    assert code_resp.status_code == 201
    code = code_resp.json()["code"]

    redeem = await client.post("/linking/redeem", json={
        "invite_code": code, "relationship": "father",
    }, headers=parent_auth_headers)
    assert redeem.status_code in (200, 201)

    lst = await client.get("/linking/guardians", headers=student_auth_headers)
    guardian = next(g for g in lst.json()["guardians"] if g["guardian_id"] == gid)
    assert guardian["status"] == "linked"
