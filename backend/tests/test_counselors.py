"""
MindBridge Platform Counselor & Booking Tests
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.utils import create_access_token, hash_password
from database.models import (
    CounselorAvailability,
    CounselorProfile,
    Tenant,
    User,
)


@pytest_asyncio.fixture
async def platform_counselor(db_session):
    """A verified, available counselor in a *different* tenant than the student."""
    tenant = Tenant(
        tenant_id=uuid.uuid4(), tenant_name="MindBridge Platform",
        tenant_type="organization", school_code=f"PLAT{uuid.uuid4().hex[:5].upper()}",
        status="active",
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        user_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
        email=f"counselor_{uuid.uuid4().hex[:8]}@mindbridge.ai",
        password_hash=hash_password("x"), role="counselor",
        first_name="Dana", last_name="Counsel", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    profile = CounselorProfile(
        counselor_id=uuid.uuid4(), user_id=user.user_id,
        bio="Here to help", qualification="LMFT",
        specializations=["Anxiety", "Stress"], languages=["English"],
        experience_years=8, is_verified=True, is_available=True,
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


@pytest.mark.asyncio
async def test_directory_lists_platform_counselor(client: AsyncClient, student_auth_headers, platform_counselor):
    resp = await client.get("/counselors/directory", headers=student_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [c["counselor_id"] for c in data["counselors"]]
    assert str(platform_counselor.counselor_id) in ids


@pytest.mark.asyncio
async def test_unverified_counselor_hidden(client: AsyncClient, student_auth_headers, db_session, platform_counselor):
    platform_counselor.is_verified = False
    await db_session.flush()
    resp = await client.get("/counselors/directory", headers=student_auth_headers)
    ids = [c["counselor_id"] for c in resp.json()["counselors"]]
    assert str(platform_counselor.counselor_id) not in ids


@pytest.mark.asyncio
async def test_cross_tenant_student_books_slot(client: AsyncClient, student_auth_headers, db_session, platform_counselor):
    # Counselor offers a slot (student is in a different tenant)
    slot = CounselorAvailability(
        slot_id=uuid.uuid4(), counselor_id=platform_counselor.counselor_id,
        start_at=datetime.now(timezone.utc) + timedelta(days=1),
        end_at=datetime.now(timezone.utc) + timedelta(days=1, minutes=45),
    )
    db_session.add(slot)
    await db_session.flush()

    book = await client.post("/counselors/book", json={"slot_id": str(slot.slot_id)}, headers=student_auth_headers)
    assert book.status_code == 201
    assert book.json()["counselor_name"] == "Dana Counsel"

    # Second booking of the same slot fails
    again = await client.post("/counselors/book", json={"slot_id": str(slot.slot_id)}, headers=student_auth_headers)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_booked_slot_not_in_open_list(client: AsyncClient, student_auth_headers, db_session, platform_counselor):
    slot = CounselorAvailability(
        slot_id=uuid.uuid4(), counselor_id=platform_counselor.counselor_id,
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        end_at=datetime.now(timezone.utc) + timedelta(days=2, minutes=45),
    )
    db_session.add(slot)
    await db_session.flush()

    await client.post("/counselors/book", json={"slot_id": str(slot.slot_id)}, headers=student_auth_headers)

    slots = await client.get(f"/counselors/{platform_counselor.counselor_id}/slots", headers=student_auth_headers)
    open_ids = [s["slot_id"] for s in slots.json()["slots"]]
    assert str(slot.slot_id) not in open_ids
