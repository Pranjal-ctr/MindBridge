"""
MindBridge Test Configuration
Shared fixtures for all test modules.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.utils import create_access_token, hash_password
from app.config import settings
from database.models import Base, StudentProfile, Tenant, User
from database.session import get_db
from main import app

# -------------------------------------------------------------------
# Test database engine (uses same DB or an in-memory alternative)
# -------------------------------------------------------------------
TEST_DATABASE_URL = settings.DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session with rollback."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with dependency overrides."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        tenant_name="Test School",
        tenant_type="school",
        school_code=f"TEST{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def test_student_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test student user with profile."""
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"student_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="student",
        first_name="Test",
        last_name="Student",
    )
    db_session.add(user)
    await db_session.flush()

    profile = StudentProfile(user_id=user.user_id, age=16, risk_level="green")
    db_session.add(profile)
    await db_session.flush()

    return user


@pytest_asyncio.fixture
async def student_auth_headers(test_student_user: User) -> dict[str, str]:
    """Generate auth headers for a test student."""
    token = create_access_token({
        "sub": str(test_student_user.user_id),
        "tenant_id": str(test_student_user.tenant_id),
        "role": "student",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test admin user."""
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("TestPassword123!"),
        role="admin",
        first_name="Test",
        last_name="Admin",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_auth_headers(test_admin_user: User) -> dict[str, str]:
    """Generate auth headers for a test admin."""
    token = create_access_token({
        "sub": str(test_admin_user.user_id),
        "tenant_id": str(test_admin_user.tenant_id),
        "role": "admin",
    })
    return {"Authorization": f"Bearer {token}"}
