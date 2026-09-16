"""
Production guards found missing in the pre-pilot audit (I1-I4).

Each of these fails only after deployment, and three of the four fail silently:
a Host header nobody checks, an email provider that reports success and
delivers nothing, a rate limit that locks out a classroom, and a staff role
that could read any user on the platform by id.
"""

import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select

from app.auth.utils import create_access_token, hash_password
from app.config import Settings
from app.rate_limit import clear_failures, note_failure
from database.models import CounselorProfile, StudentProfile, Tenant, User

# A valid production configuration. Each test below breaks exactly one thing,
# so a failure names the guard that fired rather than the first one that did.
PRODUCTION = dict(
    ENVIRONMENT="production",
    JWT_SECRET_KEY="a-real-production-secret-value",
    CORS_ORIGINS=["https://app.kio.example"],
    ALLOWED_HOSTS=["api.kio.example"],
    DB_ECHO=False,
    EMAIL_PROVIDER="resend",
    RESEND_API_KEY="re_live_key",
    GEMINI_API_KEY="gemini-key",
)


def settings_with(**overrides) -> Settings:
    return Settings(**{**PRODUCTION, **overrides})


# -------------------------------------------------------------------
# I1 - ALLOWED_HOSTS
# -------------------------------------------------------------------

class TestAllowedHostsIsEnforced:
    def test_a_valid_production_configuration_starts(self):
        assert settings_with().is_production is True

    def test_production_refuses_an_empty_allowed_hosts(self):
        """
        The regression: config.py documented a validator that did not exist, so
        main.py never installed TrustedHostMiddleware in production.
        """
        with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
            settings_with(ALLOWED_HOSTS=[])

    def test_production_refuses_a_wildcard_host(self):
        with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
            settings_with(ALLOWED_HOSTS=["*"])

    def test_development_still_allows_an_empty_list(self):
        """A developer must not have to name localhost to run the app."""
        settings = Settings(ENVIRONMENT="development", ALLOWED_HOSTS=[])
        assert settings.ALLOWED_HOSTS == []

    def test_the_middleware_is_installed_when_hosts_are_configured(self):
        """The setting only matters because main.py reads it."""
        import inspect

        import main

        source = inspect.getsource(main)
        assert "TrustedHostMiddleware" in source
        assert "if settings.ALLOWED_HOSTS:" in source


# -------------------------------------------------------------------
# I2 - email delivery
# -------------------------------------------------------------------

class TestProductionEmailMustWork:
    def test_production_refuses_the_noop_provider(self):
        """
        noop logs instead of sending. In production that means verification,
        password reset and crisis escalation all deliver nothing while every
        call reports success.
        """
        with pytest.raises(ValidationError, match="EMAIL_PROVIDER"):
            settings_with(EMAIL_PROVIDER="noop")

    def test_production_refuses_resend_without_a_key(self):
        """A blank key silently falls back to noop -- the same failure, hidden."""
        with pytest.raises(ValidationError, match="RESEND_API_KEY"):
            settings_with(RESEND_API_KEY="")

    def test_production_refuses_an_unknown_provider(self):
        with pytest.raises(ValidationError, match="not a known provider"):
            settings_with(EMAIL_PROVIDER="sendgrid")

    def test_development_still_runs_on_noop(self):
        settings = Settings(ENVIRONMENT="development", EMAIL_PROVIDER="noop")
        assert settings.EMAIL_PROVIDER == "noop"

    def test_the_guard_matches_what_the_service_actually_supports(self):
        """
        The known-provider set is duplicated in config.py to avoid a circular
        import. If someone adds a provider to the service, this fails.
        """
        from app.email.service import _PROVIDERS

        assert set(_PROVIDERS) == {"noop", "resend"}


# -------------------------------------------------------------------
# I3 - login throttling on shared school networks
# -------------------------------------------------------------------

class TestLoginThrottling:
    def test_failures_are_counted_per_account(self):
        account = f"target_{uuid.uuid4().hex[:8]}@school.example"
        for _ in range(3):
            note_failure("login", account, limit=3)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            note_failure("login", account, limit=3)
        assert excinfo.value.status_code == 429
        clear_failures("login", account)

    def test_one_accounts_failures_do_not_throttle_another(self):
        """
        The school-NAT case: two students behind one public IP. Keying on the
        account instead of the address is what keeps one of them from locking
        the other out.
        """
        victim = f"victim_{uuid.uuid4().hex[:8]}@school.example"
        bystander = f"bystander_{uuid.uuid4().hex[:8]}@school.example"

        for _ in range(5):
            note_failure("login", victim, limit=5)

        note_failure("login", bystander, limit=5)  # must not raise
        clear_failures("login", victim)
        clear_failures("login", bystander)

    def test_a_success_clears_the_count(self):
        account = f"recovered_{uuid.uuid4().hex[:8]}@school.example"
        note_failure("login", account, limit=2)
        note_failure("login", account, limit=2)
        clear_failures("login", account)

        note_failure("login", account, limit=2)  # must not raise
        clear_failures("login", account)

    def test_the_per_ip_login_limit_suits_a_shared_network(self):
        """
        10/min meant a class arriving together locked each other out. The per-IP
        limit is now flood control; guessing is stopped per account.
        """
        settings = Settings()
        assert settings.RATE_LIMIT_LOGIN_PER_MINUTE >= 60
        assert settings.AUTH_FAILED_LOGINS_PER_MINUTE <= 10

    @pytest.mark.asyncio
    async def test_repeated_bad_passwords_are_refused_for_that_account(
        self, client, db_session, test_tenant
    ):
        email = f"throttled_{uuid.uuid4().hex[:8]}@school.example"
        db_session.add(User(
            user_id=uuid.uuid4(),
            tenant_id=test_tenant.tenant_id,
            email=email,
            password_hash=hash_password("CorrectHorse123!"),
            role="student",
            first_name="Throttle",
            last_name="Test",
        ))
        await db_session.flush()

        statuses = []
        for _ in range(12):
            response = await client.post(
                "/auth/login", json={"email": email, "password": "wrong-password"}
            )
            statuses.append(response.status_code)

        assert 429 in statuses, "repeated failures against one account must throttle"
        clear_failures("login", email)


# -------------------------------------------------------------------
# I4 - tenant scoping on GET /users/{user_id}
# -------------------------------------------------------------------

class TestUserLookupIsTenantScoped:
    @pytest_asyncio.fixture
    async def other_school_student(self, db_session) -> User:
        tenant = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Other School",
            tenant_type="school",
            school_code=f"OTHER{uuid.uuid4().hex[:5].upper()}",
            status="active",
        )
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            user_id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            email=f"elsewhere_{uuid.uuid4().hex[:8]}@other.example",
            password_hash=hash_password("TestPassword123!"),
            role="student",
            first_name="Other",
            last_name="Student",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(StudentProfile(user_id=user.user_id, age=15))
        await db_session.flush()
        return user

    async def _counselor_in(self, db_session, tenant: Tenant) -> dict[str, str]:
        user = User(
            user_id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            email=f"counselor_{uuid.uuid4().hex[:8]}@school.example",
            password_hash=hash_password("TestPassword123!"),
            role="counselor",
            first_name="Local",
            last_name="Counselor",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(CounselorProfile(counselor_id=uuid.uuid4(), user_id=user.user_id))
        await db_session.flush()
        token = create_access_token({
            "sub": str(user.user_id),
            "tenant_id": str(user.tenant_id),
            "role": "counselor",
        })
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_counselor_cannot_read_a_user_from_another_school(
        self, client, db_session, test_tenant, other_school_student
    ):
        """
        The regression: the route required a staff role but passed the id
        straight through, so any counselor could read any user by id.
        """
        headers = await self._counselor_in(db_session, test_tenant)
        response = await client.get(
            f"/users/{other_school_student.user_id}", headers=headers
        )
        # 404, not 403: "exists but is not yours" is itself a fact about
        # another school's roster.
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_counselor_can_still_read_a_user_from_their_own_school(
        self, client, db_session, test_tenant, test_student_user
    ):
        headers = await self._counselor_in(db_session, test_tenant)
        response = await client.get(
            f"/users/{test_student_user.user_id}", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["user_id"] == str(test_student_user.user_id)

    @pytest.mark.asyncio
    async def test_platform_admin_is_not_scoped(
        self, client, admin_auth_headers, other_school_student
    ):
        """A platform admin administers every school; scoping them would break
        the admin console."""
        response = await client.get(
            f"/users/{other_school_student.user_id}", headers=admin_auth_headers
        )
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_a_student_cannot_read_another_user_at_all(
        self, client, student_auth_headers, other_school_student
    ):
        response = await client.get(
            f"/users/{other_school_student.user_id}", headers=student_auth_headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_users_me_still_works_unscoped(self, client, student_auth_headers):
        """The self-profile path takes its id from the token, not the URL."""
        response = await client.get("/users/me", headers=student_auth_headers)
        assert response.status_code == 200, response.text
