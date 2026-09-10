"""
Refresh-token lifecycle: rotation, revocation, and replay.

The threat these describe is concrete. Kio is used from shared school
machines. Before this, logging out deleted the client's copy of a refresh
token and nothing else, so anyone who had captured it could keep minting
sessions for the full refresh lifetime.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.utils import create_refresh_token, hash_password
from database.models import RefreshSession, StudentProfile, Tenant, User


@pytest_asyncio.fixture
async def account(db_session, test_tenant: Tenant):
    """A signed-in-able student with a known password."""
    password = "CorrectHorse9!"
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"sess_{uuid.uuid4().hex[:8]}@student.rhs.edu",
        password_hash=hash_password(password),
        role="student",
        first_name="Sess",
        last_name="Tester",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(StudentProfile(student_id=uuid.uuid4(), user_id=user.user_id))
    await db_session.flush()
    return user, password


async def login(client: AsyncClient, account) -> dict:
    user, password = account
    response = await client.post(
        "/auth/login", json={"email": user.email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["tokens"]


# -------------------------------------------------------------------
# Issue and rotate
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_records_a_refresh_session(client, db_session, account):
    tokens = await login(client, account)
    user, _ = account

    rows = (
        await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == user.user_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None
    assert tokens["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_rotates_and_spends_the_old_token(client, db_session, account):
    tokens = await login(client, account)

    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    user, _ = account
    rows = (
        await db_session.execute(
            select(RefreshSession)
            .where(RefreshSession.user_id == user.user_id)
            .order_by(RefreshSession.issued_at)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[0].revoked_at is not None and rows[0].revoked_reason == "rotated"
    assert rows[1].revoked_at is None
    # Same lineage, so one logout can end all of it.
    assert rows[0].family_id == rows[1].family_id


@pytest.mark.asyncio
async def test_the_rotated_token_works(client, account):
    tokens = await login(client, account)
    first = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    second = await client.post(
        "/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert second.status_code == 200


# -------------------------------------------------------------------
# Replay
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reusing_a_spent_token_is_refused_and_kills_the_family(
    client, db_session, account
):
    """
    The core protection. A spent token turning up again means a copy exists,
    so the whole lineage goes -- including the successor the legitimate client
    is holding, which forces a real re-login rather than a silent shared
    session.
    """
    tokens = await login(client, account)
    rotated = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200
    live_token = rotated.json()["refresh_token"]

    replay = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401

    # The successor is dead too.
    after = await client.post("/auth/refresh", json={"refresh_token": live_token})
    assert after.status_code == 401

    user, _ = account
    rows = (
        await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == user.user_id)
        )
    ).scalars().all()
    assert all(row.revoked_at is not None for row in rows)
    assert any(row.revoked_reason == "replay" for row in rows)


# -------------------------------------------------------------------
# Logout
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_revokes_the_session(client, db_session, account):
    tokens = await login(client, account)

    out = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 200
    assert out.json()["status"] == "logged_out"

    reuse = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401, "a revoked refresh token must not mint sessions"


@pytest.mark.asyncio
async def test_logout_all_devices_revokes_every_session(client, db_session, account):
    """The shared-school-laptop case."""
    first = await login(client, account)
    second = await login(client, account)
    assert first["refresh_token"] != second["refresh_token"]

    out = await client.post(
        "/auth/logout",
        json={"refresh_token": first["refresh_token"], "all_devices": True},
    )
    assert out.status_code == 200

    for token in (first["refresh_token"], second["refresh_token"]):
        assert (
            await client.post("/auth/refresh", json={"refresh_token": token})
        ).status_code == 401


@pytest.mark.asyncio
async def test_logging_out_one_device_leaves_the_others_alone(client, account):
    first = await login(client, account)
    second = await login(client, account)

    await client.post("/auth/logout", json={"refresh_token": first["refresh_token"]})

    assert (
        await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    ).status_code == 401
    assert (
        await client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    ).status_code == 200


@pytest.mark.asyncio
async def test_logout_never_reports_failure(client):
    """
    Garbage in, success out. A user seeing "logout failed" has no next move,
    and an unusable token is already the outcome they wanted.
    """
    for token in ("not-a-jwt", "", "a.b.c"):
        response = await client.post("/auth/logout", json={"refresh_token": token})
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


# -------------------------------------------------------------------
# Rejected tokens
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_expired_refresh_token_is_refused(client, db_session, account):
    tokens = await login(client, account)
    user, _ = account

    row = (
        await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == user.user_id)
        )
    ).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_a_token_naming_an_unknown_session_is_refused(client, account):
    """A well-signed token whose session was never issued, or was purged."""
    user, _ = account
    forged = create_refresh_token(
        {
            "sub": str(user.user_id),
            "tenant_id": str(user.tenant_id),
            "role": "student",
            "sid": str(uuid.uuid4()),
            "fam": str(uuid.uuid4()),
        }
    )
    response = await client.post("/auth/refresh", json={"refresh_token": forged})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_a_legacy_token_without_a_session_is_refused(client, account):
    """
    Tokens issued before this change carry no `sid`. Honouring them would
    leave the un-revocable tokens this exists to kill working.
    """
    user, _ = account
    legacy = create_refresh_token(
        {"sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": "student"}
    )
    response = await client.post("/auth/refresh", json={"refresh_token": legacy})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_an_access_token_cannot_be_used_to_refresh(client, account):
    tokens = await login(client, account)
    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_every_refusal_says_the_same_thing(client, account):
    """
    Unknown, expired and revoked must be indistinguishable, or the response
    tells whoever holds a stolen token exactly what they hold.
    """
    user, _ = account
    tokens = await login(client, account)
    await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    revoked = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    unknown = await client.post(
        "/auth/refresh",
        json={
            "refresh_token": create_refresh_token(
                {
                    "sub": str(user.user_id),
                    "tenant_id": str(user.tenant_id),
                    "role": "student",
                    "sid": str(uuid.uuid4()),
                    "fam": str(uuid.uuid4()),
                }
            )
        },
    )
    assert revoked.status_code == unknown.status_code == 401
    assert revoked.json()["detail"] == unknown.json()["detail"]
