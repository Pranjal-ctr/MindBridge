"""
Runtime AI configuration: precedence, validation, admin API, and the
guarantee that changing the model does not touch anybody's session.

The session tests are the point of this file. Kio's AI provider is a piece of
operational configuration; a student's login is not. Those two things share no
table, no cache and no code path, and these tests exist to keep it that way --
because the failure they guard against ("we switched the model and everyone got
logged out mid-conversation") would land on teenagers in the middle of asking
for help.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.ai import guardrails, runtime_config
from app.ai.config_loader import load_feature_route
from app.ai.errors import AIConfigurationError
from app.ai.runtime_config import (
    ResolvedAIConfig,
    get_active_config,
    invalidate_cache,
    validate_config,
)
from app.auth.utils import hash_password
from database.models import AIFeatureRoute, AIRuntimeConfig, AuditLog, RefreshSession, StudentProfile, Tenant, User


@pytest.fixture(autouse=True)
def _isolate_ai_state(monkeypatch):
    """The runtime config cache and guardrails are process-global."""
    invalidate_cache()
    guardrails.reset_state()
    # Both providers credentialed by default so tests target the logic under
    # test rather than the credential rules; individual tests override.
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "g-key")
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "o-key")
    yield
    invalidate_cache()
    guardrails.reset_state()


def _cfg(**overrides) -> ResolvedAIConfig:
    base = dict(
        primary_provider="gemini",
        primary_model="gemini-2.5-flash",
        fallback_provider="openai",
        fallback_model="gpt-5-mini",
        fallback_enabled=False,
        source="database",
    )
    base.update(overrides)
    return ResolvedAIConfig(**base)


# -------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------

class TestValidation:
    def test_gemini_primary_is_valid(self):
        validate_config(_cfg())

    def test_unsupported_provider_rejected(self):
        with pytest.raises(AIConfigurationError):
            validate_config(_cfg(primary_provider="anthropic", primary_model="claude"))

    def test_unsupported_model_rejected(self):
        with pytest.raises(AIConfigurationError):
            validate_config(_cfg(primary_model="gemini-9.9-ultra"))

    def test_provider_model_mismatch_rejected(self):
        with pytest.raises(AIConfigurationError):
            validate_config(_cfg(primary_model="gpt-5-mini"))  # on gemini

    def test_missing_primary_credential_rejected(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
        with pytest.raises(AIConfigurationError) as exc:
            validate_config(_cfg(primary_provider="openai", primary_model="gpt-5-mini"))
        assert "OPENAI_API_KEY" in str(exc.value)

    def test_fallback_credential_only_required_when_enabled(self, monkeypatch):
        """The current deployment exactly: OpenAI configured as an off fallback."""
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        validate_config(_cfg(fallback_enabled=False))  # fine

        with pytest.raises(AIConfigurationError):
            validate_config(_cfg(fallback_enabled=True))

    def test_identical_primary_and_fallback_rejected(self):
        with pytest.raises(AIConfigurationError) as exc:
            validate_config(_cfg(
                fallback_provider="gemini",
                fallback_model="gemini-2.5-flash",
                fallback_enabled=True,
            ))
        assert "differ" in str(exc.value)

    def test_enabled_fallback_must_be_fully_specified(self):
        with pytest.raises(AIConfigurationError):
            validate_config(_cfg(
                fallback_provider=None, fallback_model=None, fallback_enabled=True
            ))


# -------------------------------------------------------------------
# Precedence
# -------------------------------------------------------------------

class TestPrecedence:
    @pytest.mark.asyncio
    async def test_environment_is_used_when_no_db_row(self, db_session, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_PRIMARY_PROVIDER", "gemini")
        monkeypatch.setattr("app.config.settings.AI_PRIMARY_MODEL", "gemini-2.5-flash")

        config = await get_active_config(db_session)
        assert config.source == "environment"
        assert config.primary_model == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_db_row_overrides_environment(self, db_session, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_PRIMARY_PROVIDER", "gemini")
        db_session.add(AIRuntimeConfig(
            config_id=runtime_config.SINGLETON_ID,
            primary_provider="openai",
            primary_model="gpt-5-mini",
            fallback_enabled=False,
        ))
        await db_session.flush()
        invalidate_cache()

        config = await get_active_config(db_session)
        assert config.source == "database"
        assert config.primary_provider == "openai"

    @pytest.mark.asyncio
    async def test_unusable_db_row_falls_back_to_environment(self, db_session, monkeypatch):
        """A stored preference that went stale must not break every AI request.

        The case: an admin selected OpenAI, then the key was removed from the
        environment. Kio keeps answering on whatever is still usable.
        """
        db_session.add(AIRuntimeConfig(
            config_id=runtime_config.SINGLETON_ID,
            primary_provider="openai",
            primary_model="gpt-5-mini",
            fallback_enabled=False,
        ))
        await db_session.flush()
        invalidate_cache()
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        config = await get_active_config(db_session)
        assert config.source == "environment"
        assert config.primary_provider == "gemini"

    @pytest.mark.asyncio
    async def test_active_feature_override_beats_platform_config(self, db_session):
        db_session.add(AIRuntimeConfig(
            config_id=runtime_config.SINGLETON_ID,
            primary_provider="openai", primary_model="gpt-5-mini",
            fallback_enabled=False,
        ))
        route = (await db_session.execute(
            select(AIFeatureRoute).where(AIFeatureRoute.feature_name == "risk_detection")
        )).scalar_one()
        route.is_active = True
        route.primary_provider = "gemini"
        route.primary_model = "gemini-2.5-flash"
        await db_session.flush()
        invalidate_cache()

        resolved = await load_feature_route(db_session, "risk_detection")
        assert resolved.source == "feature_override"
        assert resolved.primary_provider == "gemini"

    @pytest.mark.asyncio
    async def test_inactive_feature_route_is_ignored(self, db_session):
        """The seeded rows are parked defaults, not overrides (migration 019)."""
        db_session.add(AIRuntimeConfig(
            config_id=runtime_config.SINGLETON_ID,
            primary_provider="openai", primary_model="gpt-5-mini",
            fallback_enabled=False,
        ))
        await db_session.flush()
        invalidate_cache()

        resolved = await load_feature_route(db_session, "comrade_chat")
        assert resolved.source == "platform_config"
        assert resolved.primary_provider == "openai"

    @pytest.mark.asyncio
    async def test_disabled_fallback_is_not_routed_to(self, db_session):
        db_session.add(AIRuntimeConfig(
            config_id=runtime_config.SINGLETON_ID,
            primary_provider="gemini", primary_model="gemini-2.5-flash",
            fallback_provider="openai", fallback_model="gpt-5-mini",
            fallback_enabled=False,
        ))
        await db_session.flush()
        invalidate_cache()

        resolved = await load_feature_route(db_session, "comrade_chat")
        assert resolved.fallback_provider is None

    @pytest.mark.asyncio
    async def test_cache_is_invalidated_on_save(self, db_session):
        first = await get_active_config(db_session)
        assert first.primary_provider == "gemini"

        await runtime_config.save_config(
            db_session,
            primary_provider="openai", primary_model="gpt-5-mini",
            fallback_provider=None, fallback_model=None, fallback_enabled=False,
            actor_user_id=None,
        )
        second = await get_active_config(db_session)
        assert second.primary_provider == "openai"


# -------------------------------------------------------------------
# Admin API
# -------------------------------------------------------------------

class TestAdminApi:
    @pytest.mark.asyncio
    async def test_read_returns_registry_without_any_key(
        self, client: AsyncClient, admin_auth_headers, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "sk-gemini-secret")
        resp = await client.get("/admin/ai/config", headers=admin_auth_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert "sk-gemini-secret" not in resp.text
        providers = {p["provider_id"] for p in body["providers"]}
        assert providers == {"gemini", "openai"}
        assert body["primary_provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_valid_switch_is_saved_and_takes_effect(
        self, client: AsyncClient, admin_auth_headers, db_session
    ):
        resp = await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": "openai",
                "primary_model": "gpt-5-mini",
                "fallback_provider": "gemini",
                "fallback_model": "gemini-2.5-flash",
                "fallback_enabled": True,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["primary_provider"] == "openai"
        assert resp.json()["source"] == "database"

        # And new requests resolve to it -- no restart involved.
        resolved = await load_feature_route(db_session, "comrade_chat")
        assert resolved.primary_provider == "openai"

    @pytest.mark.asyncio
    async def test_invalid_switch_cannot_replace_a_valid_config(
        self, client: AsyncClient, admin_auth_headers, db_session, monkeypatch
    ):
        """Scenario D: OpenAI selected with no key. Gemini must survive intact."""
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        before = await get_active_config(db_session)
        assert before.primary_provider == "gemini"

        resp = await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": "openai",
                "primary_model": "gpt-5-mini",
                "fallback_provider": None,
                "fallback_model": None,
                "fallback_enabled": False,
            },
        )
        assert resp.status_code == 422
        assert "OPENAI_API_KEY" in resp.json()["detail"]

        # No partial save: no row written, cache still Gemini, AI still works.
        invalidate_cache()
        after = await get_active_config(db_session)
        assert after.primary_provider == "gemini"
        stored = (await db_session.execute(select(AIRuntimeConfig))).scalar_one_or_none()
        assert stored is None

    @pytest.mark.asyncio
    async def test_arbitrary_model_string_is_refused(
        self, client: AsyncClient, admin_auth_headers
    ):
        resp = await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": "gemini",
                "primary_model": "../../etc/passwd",
                "fallback_provider": None, "fallback_model": None,
                "fallback_enabled": False,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["student", "parent", "counselor", "school_admin"])
    async def test_only_platform_admin_may_read_or_change(
        self, client: AsyncClient, db_session, test_tenant: Tenant, role
    ):
        from app.auth.utils import create_access_token

        user = User(
            user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
            email=f"{role}_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("TestPassword123!"),
            role=role, first_name="R", last_name="T",
        )
        db_session.add(user)
        await db_session.flush()
        headers = {"Authorization": "Bearer " + create_access_token(
            {"sub": str(user.user_id), "tenant_id": str(user.tenant_id), "role": role}
        )}

        assert (await client.get("/admin/ai/config", headers=headers)).status_code == 403
        assert (await client.put(
            "/admin/ai/config", headers=headers,
            json={
                "primary_provider": "openai", "primary_model": "gpt-5-mini",
                "fallback_provider": None, "fallback_model": None,
                "fallback_enabled": False,
            },
        )).status_code == 403

    @pytest.mark.asyncio
    async def test_change_is_audited_with_identifiers_only(
        self, client: AsyncClient, admin_auth_headers, db_session
    ):
        await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": "openai", "primary_model": "gpt-5-mini",
                "fallback_provider": None, "fallback_model": None,
                "fallback_enabled": False,
            },
        )
        row = (await db_session.execute(
            select(AuditLog).where(AuditLog.action == "admin.ai_configuration_changed")
            .order_by(AuditLog.created_at.desc())
        )).scalars().first()

        assert row is not None
        assert row.details["previous_provider"] == "gemini"
        assert row.details["new_provider"] == "openai"
        assert row.severity == "critical"
        # Provider and model names are safe identifiers; nothing else is here.
        assert "key" not in str(row.details).lower()

    @pytest.mark.asyncio
    async def test_rejected_change_is_also_audited(
        self, client: AsyncClient, admin_auth_headers, db_session, test_admin_user,
        monkeypatch,
    ):
        # A refused change rolls the request back, so the audit row is written
        # by log_audit_detached in its own session -- which means the acting
        # admin has to be committed for the row's foreign key to resolve.
        await db_session.commit()
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
        await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": "openai", "primary_model": "gpt-5-mini",
                "fallback_provider": None, "fallback_model": None,
                "fallback_enabled": False,
            },
        )
        rows = (await db_session.execute(
            select(AuditLog).where(AuditLog.action == "admin.ai_configuration_changed")
        )).scalars().all()
        failures = [r for r in rows if r.result == "failure"]
        assert failures, "a refused configuration change was not audited"


# -------------------------------------------------------------------
# Authentication / session isolation  -- the headline guarantee
# -------------------------------------------------------------------

@pytest_asyncio.fixture
async def signed_in_student(db_session, test_tenant: Tenant):
    """A committed, genuinely signed-in student with a live refresh session."""
    password = "AiSwitchPass9!"
    user = User(
        user_id=uuid.uuid4(), tenant_id=test_tenant.tenant_id,
        email=f"aiswitch_{uuid.uuid4().hex[:8]}@student.rhs.edu",
        password_hash=hash_password(password), role="student",
        first_name="Ai", last_name="Switch", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(StudentProfile(user_id=user.user_id, age=16, risk_level="green"))
    await db_session.commit()
    return user, password


class TestSessionsSurviveConfigChange:
    async def _switch(self, client, admin_auth_headers, provider, model):
        resp = await client.put(
            "/admin/ai/config",
            headers=admin_auth_headers,
            json={
                "primary_provider": provider, "primary_model": model,
                "fallback_provider": None, "fallback_model": None,
                "fallback_enabled": False,
            },
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_session_and_refresh_survive_both_directions(
        self, client: AsyncClient, admin_auth_headers, db_session, signed_in_student
    ):
        user, password = signed_in_student

        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        assert login.status_code == 200
        tokens = login.json()["tokens"]
        access, refresh = tokens["access_token"], tokens["refresh_token"]
        auth = {"Authorization": f"Bearer {access}"}

        sessions_before = {
            (r.session_id, r.revoked_at)
            for r in (await db_session.execute(
                select(RefreshSession).where(RefreshSession.user_id == user.user_id)
            )).scalars().all()
        }

        # --- Gemini -> OpenAI -------------------------------------------
        await self._switch(client, admin_auth_headers, "openai", "gpt-5-mini")

        # Still authenticated: the access token was not revoked.
        assert (await client.get("/auth/me", headers=auth)).status_code == 200

        # No session record was touched by the AI change.
        sessions_after = {
            (r.session_id, r.revoked_at)
            for r in (await db_session.execute(
                select(RefreshSession).where(RefreshSession.user_id == user.user_id)
            )).scalars().all()
        }
        assert sessions_after == sessions_before

        # --- OpenAI -> Gemini -------------------------------------------
        await self._switch(client, admin_auth_headers, "gemini", "gemini-2.5-flash")
        assert (await client.get("/auth/me", headers=auth)).status_code == 200

        # The refresh token still works -- and only now does the session table
        # change, by ordinary rotation rather than by the config change.
        refreshed = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert refreshed.status_code == 200
        assert refreshed.json()["access_token"]

    @pytest.mark.asyncio
    async def test_config_change_writes_no_user_or_session_rows(
        self, client: AsyncClient, admin_auth_headers, db_session, signed_in_student
    ):
        """Nothing in users or refresh_sessions moves when the model changes."""
        user, password = signed_in_student
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        assert login.status_code == 200

        before_user = (await db_session.execute(
            select(User).where(User.user_id == user.user_id)
        )).scalar_one()
        snapshot = (
            before_user.password_hash,
            before_user.is_active,
            before_user.is_verified,
            before_user.google_sub,
            before_user.last_login,
        )
        session_count_before = len((await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == user.user_id)
        )).scalars().all())

        await self._switch(client, admin_auth_headers, "openai", "gpt-5-mini")

        await db_session.refresh(before_user)
        assert (
            before_user.password_hash,
            before_user.is_active,
            before_user.is_verified,
            before_user.google_sub,
            before_user.last_login,
        ) == snapshot

        session_count_after = len((await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == user.user_id)
        )).scalars().all())
        assert session_count_after == session_count_before

    def test_ai_config_module_cannot_reach_auth(self):
        """Structural guarantee, not a behavioural one.

        The reason an AI configuration change cannot revoke a session is that
        there is no code path from one to the other. This asserts the import
        graph directly, so a future edit that reaches into auth from the AI
        config layer fails here rather than in production.
        """
        import ast
        import inspect

        import app.ai.runtime_config as mod

        # Parsed, not grepped: the module's own docstring explains that it
        # avoids app.auth, and a substring check would match that explanation.
        tree = ast.parse(inspect.getsource(mod))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                imported.update(f"{node.module}.{a.name}" for a in node.names)

        auth_reaching = {
            name for name in imported
            if name.startswith("app.auth")
            or "RefreshSession" in name
            or "Session" in name and "AsyncSession" not in name
        }
        assert auth_reaching == set(), (
            f"AI runtime config reaches authentication code: {auth_reaching}"
        )
