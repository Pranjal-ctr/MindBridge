"""
The production bootstrap creates the first admin, and only the first.

`database/bootstrap.py` exists because a freshly migrated production database
has no tenant and no admin, and every other route in is closed: seed is refused
in production, self-signup is student/parent only and needs a school code that
resolves to an existing tenant, and every admin endpoint requires a role nobody
holds yet.

The tests that matter here are the refusals. A bootstrap command that could run
twice is not a bootstrap command, it is an unauthenticated admin factory with a
polite name.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from database.bootstrap import BootstrapRefused, bootstrap
from database.models import AuditLog, SchoolAdminProfile, Tenant, User


def _env(monkeypatch, **overrides) -> None:
    """Set the bootstrap environment, with working defaults."""
    values = {
        "BOOTSTRAP_ADMIN_EMAIL": f"admin_{uuid.uuid4().hex[:8]}@kio-test.com",
        "BOOTSTRAP_ADMIN_PASSWORD": "a-long-enough-secret-9F",
        "BOOTSTRAP_SCHOOL_NAME": "Pilot School",
        "BOOTSTRAP_SCHOOL_CODE": f"PILOT{uuid.uuid4().hex[:5].upper()}",
    }
    values.update(overrides)
    for key, value in values.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


@pytest.fixture
def session_factory(db_session):
    """
    Hand bootstrap() the test's own session.

    Its commit is real and is left alone: `db_session` runs inside a
    transaction the fixture rolls back, so the commit releases a savepoint
    rather than writing an admin that later tests would then trip over.
    """
    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc_info):
            return False

    return _Factory()


class TestBootstrapCreatesTheFirstAdmin:
    @pytest.mark.asyncio
    async def test_creates_school_and_admin(
        self, db_session, session_factory, monkeypatch
    ):
        _env(monkeypatch, BOOTSTRAP_SCHOOL_CODE="PILOTONE")
        result = await bootstrap(session_factory)

        assert result["school_code"] == "PILOTONE"
        assert result["school_created"] == "True"

        admin = (
            await db_session.execute(
                select(User).where(User.email == result["admin_email"])
            )
        ).scalar_one()
        assert admin.role == "admin"
        assert admin.is_active is True
        # Verified on creation: outbound email may not be configured yet, and
        # the operator proved control of the address by typing it into the
        # server's own environment.
        assert admin.is_verified is True

        tenant = (
            await db_session.execute(
                select(Tenant).where(Tenant.tenant_id == admin.tenant_id)
            )
        ).scalar_one()
        assert tenant.school_code == "PILOTONE"
        assert tenant.status == "active"

    @pytest.mark.asyncio
    async def test_password_is_hashed_not_stored(
        self, db_session, session_factory, monkeypatch
    ):
        password = "a-long-enough-secret-9F"
        _env(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD=password)
        result = await bootstrap(session_factory)

        admin = (
            await db_session.execute(
                select(User).where(User.email == result["admin_email"])
            )
        ).scalar_one()
        assert admin.password_hash != password
        assert admin.password_hash.startswith("$2")

    @pytest.mark.asyncio
    async def test_creates_the_role_profile(
        self, db_session, session_factory, monkeypatch
    ):
        _env(monkeypatch)
        result = await bootstrap(session_factory)
        admin = (
            await db_session.execute(
                select(User).where(User.email == result["admin_email"])
            )
        ).scalar_one()
        profile = (
            await db_session.execute(
                select(SchoolAdminProfile).where(
                    SchoolAdminProfile.user_id == admin.user_id
                )
            )
        ).scalar_one_or_none()
        assert profile is not None

    @pytest.mark.asyncio
    async def test_reuses_an_existing_school_with_the_same_code(
        self, db_session, session_factory, monkeypatch, test_tenant
    ):
        _env(monkeypatch, BOOTSTRAP_SCHOOL_CODE=test_tenant.school_code)
        result = await bootstrap(session_factory)

        assert result["school_created"] == "False"
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(Tenant)
                .where(Tenant.school_code == test_tenant.school_code)
            )
        ).scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_the_creation_is_audited_without_the_password(
        self, db_session, session_factory, monkeypatch
    ):
        password = "a-long-enough-secret-9F"
        _env(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD=password)
        result = await bootstrap(session_factory)

        rows = (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "user.create")
            )
        ).scalars().all()
        via_bootstrap = [
            row for row in rows if (row.details or {}).get("via") == "database.bootstrap"
        ]
        assert via_bootstrap, "bootstrap must leave an audit trail"
        for row in via_bootstrap:
            assert password not in str(row.details)
            assert row.details["role"] == "admin"
            assert row.details["email"] == result["admin_email"]


class TestBootstrapRefuses:
    @pytest.mark.asyncio
    async def test_refuses_when_an_admin_already_exists(
        self, db_session, session_factory, monkeypatch, test_admin_user
    ):
        """
        The property that makes this one-time rather than an admin factory.
        `test_admin_user` is an existing platform admin.
        """
        _env(monkeypatch)
        with pytest.raises(BootstrapRefused, match="already exist"):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    async def test_running_twice_refuses_the_second_time(
        self, db_session, session_factory, monkeypatch
    ):
        _env(monkeypatch)
        await bootstrap(session_factory)

        _env(monkeypatch)  # fresh email and school code
        with pytest.raises(BootstrapRefused, match="already exist"):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    async def test_refuses_a_short_password(
        self, db_session, session_factory, monkeypatch
    ):
        _env(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD="short1!")
        with pytest.raises(BootstrapRefused, match="at least"):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    async def test_refuses_the_published_seed_password(
        self, db_session, session_factory, monkeypatch
    ):
        """
        The seed password is in this repository and its git history. Length
        alone would let it through.
        """
        _env(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD="MindBridge2026!")
        with pytest.raises(BootstrapRefused, match="known or published"):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "missing",
        [
            "BOOTSTRAP_ADMIN_EMAIL",
            "BOOTSTRAP_ADMIN_PASSWORD",
            "BOOTSTRAP_SCHOOL_NAME",
            "BOOTSTRAP_SCHOOL_CODE",
        ],
    )
    async def test_refuses_without_required_configuration(
        self, db_session, session_factory, monkeypatch, missing
    ):
        _env(monkeypatch, **{missing: None})
        with pytest.raises(BootstrapRefused, match=missing):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    async def test_refuses_a_duplicate_email(
        self, db_session, session_factory, monkeypatch, test_student_user
    ):
        """A taken address must fail cleanly, not as a unique-constraint 500."""
        _env(monkeypatch, BOOTSTRAP_ADMIN_EMAIL=test_student_user.email)
        with pytest.raises(BootstrapRefused, match="already exists"):
            await bootstrap(session_factory)

    @pytest.mark.asyncio
    async def test_no_admin_is_created_when_it_refuses(
        self, db_session, session_factory, monkeypatch
    ):
        """A refusal must leave nothing behind."""
        _env(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD="short1!")
        email = "leftover_check@kio-test.com"
        monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)

        with pytest.raises(BootstrapRefused):
            await bootstrap(session_factory)

        assert (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none() is None


class TestBootstrapIsNotReachableOverHttp:
    @pytest.mark.asyncio
    async def test_no_route_exposes_bootstrap(self):
        """
        It must stay a shell command. An HTTP route -- even an admin-only one --
        would be an unauthenticated admin factory the moment the guard regressed.
        """
        from main import app

        paths = {route.path for route in app.routes}
        assert not [p for p in paths if "bootstrap" in p.lower()]

    @pytest.mark.asyncio
    async def test_bootstrap_endpoint_returns_404(self, client):
        for path in ("/bootstrap", "/admin/bootstrap", "/auth/bootstrap"):
            response = await client.post(path, json={})
            assert response.status_code == 404, path
