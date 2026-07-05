"""
MindBridge Test Configuration
Shared fixtures for all test modules.

Tests run against an isolated database (TEST_DATABASE_URL env var, or the
configured DATABASE_URL with the database name swapped to `mindbridge_test`).
The database is created automatically if missing; schema comes from the
SQLAlchemy models.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.utils import create_access_token, hash_password
from app.config import settings
from database.models import Base, StudentProfile, Tenant, User
from database.session import get_db
from main import app

# -------------------------------------------------------------------
# Test database (isolated from dev DB)
# -------------------------------------------------------------------

def _default_test_url() -> str:
    base, _, _dbname = settings.DATABASE_URL.rpartition("/")
    return f"{base}/mindbridge_test"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _default_test_url()

# NullPool: pytest-asyncio gives each test its own event loop, and pooled
# asyncpg connections cannot be reused across loops.
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

async def _create_database_and_schema() -> None:
    base, _, dbname = TEST_DATABASE_URL.rpartition("/")
    admin_engine = create_async_engine(
        f"{base}/postgres", isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    async with admin_engine.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": dbname}
        )
        if not exists.scalar():
            await conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    await admin_engine.dispose()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database():
    """Create the test database (if missing) and a fresh schema for the run."""
    asyncio.run(_create_database_and_schema())

    # Point the app's module-level session factory at the test DB so code that
    # opens its own sessions (safety logging, background hooks) stays isolated.
    import database.session as db_session_module
    original_factory = db_session_module.async_session_factory
    db_session_module.async_session_factory = test_session_factory

    yield

    db_session_module.async_session_factory = original_factory


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate-limiter state is module-global; clear it between tests."""
    from app.rate_limit import _hits
    _hits.clear()
    yield
    _hits.clear()


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
