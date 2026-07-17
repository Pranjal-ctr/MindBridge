"""
Kio Linking Tests
Parent-student invite code system.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.utils import create_access_token, hash_password
from database.models import ParentProfile, Tenant, User


@pytest_asyncio.fixture
async def test_parent_user(db_session, test_tenant: Tenant) -> User:
    """Create a test parent user with profile."""
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"parent_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="parent",
        first_name="Test",
        last_name="Parent",
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
async def test_invite_code_single_use(
    client: AsyncClient, student_auth_headers, parent_auth_headers
):
    """An invite code can be redeemed once; the second attempt gets 409."""
    gen_resp = await client.post("/linking/invite-code", headers=student_auth_headers)
    assert gen_resp.status_code in (200, 201)
    code = gen_resp.json()["code"]

    first = await client.post(
        "/linking/redeem",
        json={"invite_code": code, "relationship": "mother"},
        headers=parent_auth_headers,
    )
    assert first.status_code in (200, 201)

    second = await client.post(
        "/linking/redeem",
        json={"invite_code": code, "relationship": "mother"},
        headers=parent_auth_headers,
    )
    assert second.status_code == 409
