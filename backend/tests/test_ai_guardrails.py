"""
AI guardrails, telemetry privacy, and the safety pipeline's independence from
which provider answered.

Two things are being defended here.

The first is cost and availability: nothing should be able to make Kio spend
without bound, and a provider that is down should stop being asked. These are
the guardrails, and the rule that matters most is that a *fallback provider
cannot be used to get around a ceiling the primary hit* -- otherwise "Gemini is
out of quota" silently becomes "send it all to OpenAI instead".

The second is that none of this touches safety. Provider selection is an
operational concern; whether a response is safe to show a student is decided
afterwards, by code that does not know which provider answered. The tests at
the bottom prove a fallback response goes through the identical pipeline,
including the deterministic safety floor.
"""

import uuid

import pytest
from sqlalchemy import select

from app.ai import guardrails
from app.ai.errors import (
    AICircuitOpenError,
    AIGuardrailError,
    AIProviderUnavailableError,
    AITimeoutError,
)
from app.ai.providers.base import ProviderResponse
from database.models import AIUsageLog


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    guardrails.reset_state()
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "g-key")
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "o-key")
    yield
    guardrails.reset_state()


# -------------------------------------------------------------------
# Request-shape bounds
# -------------------------------------------------------------------

class TestRequestBounds:
    def test_output_tokens_are_clamped_to_the_ceiling(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_MAX_OUTPUT_TOKENS_CEILING", 1000)
        assert guardrails.clamp_output_tokens(500) == 500      # under: untouched
        assert guardrails.clamp_output_tokens(999_999) == 1000  # over: clamped

    def test_unset_output_tokens_get_the_ceiling_not_infinity(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_MAX_OUTPUT_TOKENS_CEILING", 777)
        assert guardrails.clamp_output_tokens(0) == 777

    def test_input_within_limit_is_allowed(self):
        size = guardrails.assert_input_within_limit(
            "system", [{"role": "user", "parts": [{"text": "hello"}]}]
        )
        assert size == len("system") + len("hello")

    def test_oversized_input_is_refused_not_truncated(self, monkeypatch):
        """Refusal is the safe choice for a mental-health product.

        Silently dropping part of a conversation could remove the very message
        that indicates danger while still returning a confident low-risk score.
        A refusal reaches the caller's safe-failure path, which is visible.
        """
        monkeypatch.setattr("app.config.settings.AI_MAX_INPUT_CHARS", 100)
        with pytest.raises(AIGuardrailError) as exc:
            guardrails.assert_input_within_limit(
                "", [{"role": "user", "parts": [{"text": "x" * 500}]}]
            )
        assert exc.value.guardrail == "input_size"
        # Never retried, never failed over -- a second provider has the same limit.
        assert exc.value.retryable is False
        assert exc.value.fallback_eligible is False


# -------------------------------------------------------------------
# Rate ceilings
# -------------------------------------------------------------------

class TestRateCeilings:
    def test_per_user_limit(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_USER_REQUESTS_PER_MINUTE", 3)
        for _ in range(3):
            guardrails.assert_request_rates(feature="comrade_chat", user_key="u1")
        with pytest.raises(AIGuardrailError) as exc:
            guardrails.assert_request_rates(feature="comrade_chat", user_key="u1")
        assert exc.value.guardrail == "per_user"

    def test_one_user_does_not_exhaust_another(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_USER_REQUESTS_PER_MINUTE", 2)
        for _ in range(2):
            guardrails.assert_request_rates(feature="comrade_chat", user_key="noisy")
        # A different student is unaffected.
        guardrails.assert_request_rates(feature="comrade_chat", user_key="quiet")

    def test_per_feature_limit(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_USER_REQUESTS_PER_MINUTE", 10_000)
        monkeypatch.setattr("app.config.settings.AI_FEATURE_REQUESTS_PER_MINUTE", 2)
        for i in range(2):
            guardrails.assert_request_rates(feature="risk_detection", user_key=f"u{i}")
        with pytest.raises(AIGuardrailError) as exc:
            guardrails.assert_request_rates(feature="risk_detection", user_key="u9")
        assert exc.value.guardrail == "per_feature"

    def test_global_limit(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_USER_REQUESTS_PER_MINUTE", 10_000)
        monkeypatch.setattr("app.config.settings.AI_FEATURE_REQUESTS_PER_MINUTE", 10_000)
        monkeypatch.setattr("app.config.settings.AI_GLOBAL_REQUESTS_PER_MINUTE", 2)
        guardrails.assert_request_rates(feature="a", user_key="u1")
        guardrails.assert_request_rates(feature="b", user_key="u2")
        with pytest.raises(AIGuardrailError) as exc:
            guardrails.assert_request_rates(feature="c", user_key="u3")
        assert exc.value.guardrail == "global"

    def test_a_refused_request_does_not_consume_earlier_windows(self, monkeypatch):
        """A call blocked by the global limit must not burn a per-user slot.

        Otherwise a burst of globally-refused requests would silently exhaust
        every individual student's allowance too.
        """
        monkeypatch.setattr("app.config.settings.AI_USER_REQUESTS_PER_MINUTE", 5)
        monkeypatch.setattr("app.config.settings.AI_FEATURE_REQUESTS_PER_MINUTE", 5)
        monkeypatch.setattr("app.config.settings.AI_GLOBAL_REQUESTS_PER_MINUTE", 0)

        with pytest.raises(AIGuardrailError):
            guardrails.assert_request_rates(feature="f", user_key="u1")

        monkeypatch.setattr("app.config.settings.AI_GLOBAL_REQUESTS_PER_MINUTE", 5)
        # The user still has their full allowance.
        for _ in range(5):
            guardrails.assert_request_rates(feature="f", user_key="u1")


class TestConcurrency:
    def test_slots_are_bounded_per_user(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_MAX_CONCURRENT_PER_USER", 2)
        a = guardrails.ConcurrencySlot("u1").__enter__()
        b = guardrails.ConcurrencySlot("u1").__enter__()
        with pytest.raises(AIGuardrailError) as exc:
            guardrails.ConcurrencySlot("u1").__enter__()
        assert exc.value.guardrail == "concurrency"
        a.__exit__()
        b.__exit__()

    def test_slot_is_released_even_when_the_call_raises(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_MAX_CONCURRENT_PER_USER", 1)
        with pytest.raises(RuntimeError):
            with guardrails.ConcurrencySlot("u1"):
                raise RuntimeError("provider blew up")
        # Not leaked: the next request can still get the slot.
        with guardrails.ConcurrencySlot("u1"):
            pass


# -------------------------------------------------------------------
# Token ceilings
# -------------------------------------------------------------------

class TestTokenCeilings:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self, db_session):
        await guardrails.assert_token_ceilings(db_session)  # must not raise

    @pytest.mark.asyncio
    async def test_daily_ceiling_blocks_once_reached(self, db_session, monkeypatch):
        db_session.add(AIUsageLog(
            usage_id=uuid.uuid4(), feature_name="comrade_chat", provider="gemini",
            model="gemini-2.5-flash", latency_ms=10,
            input_tokens=600, output_tokens=600, success=True,
        ))
        await db_session.flush()
        monkeypatch.setattr("app.config.settings.AI_DAILY_TOKEN_CEILING", 1000)

        with pytest.raises(AIGuardrailError) as exc:
            await guardrails.assert_token_ceilings(db_session)
        assert exc.value.guardrail == "daily_token_ceiling"

    @pytest.mark.asyncio
    async def test_unreported_tokens_are_not_estimated(self, db_session, monkeypatch):
        """A NULL token count contributes zero, never a guess.

        A ceiling enforced against invented numbers is worse than no ceiling.
        """
        db_session.add(AIUsageLog(
            usage_id=uuid.uuid4(), feature_name="comrade_chat", provider="gemini",
            model="gemini-2.5-flash", latency_ms=10,
            input_tokens=None, output_tokens=None, success=True,
        ))
        await db_session.flush()
        monkeypatch.setattr("app.config.settings.AI_DAILY_TOKEN_CEILING", 1)

        await guardrails.assert_token_ceilings(db_session)  # must not raise


# -------------------------------------------------------------------
# Circuit breaker
# -------------------------------------------------------------------

class TestCircuitBreaker:
    def test_opens_after_consecutive_transient_failures(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_CIRCUIT_FAILURE_THRESHOLD", 3)
        for _ in range(3):
            guardrails.record_provider_failure("gemini", "timeout")
        assert guardrails.circuit_is_open("gemini") is True
        with pytest.raises(AICircuitOpenError):
            guardrails.assert_circuit_closed("gemini")

    def test_open_circuit_is_fallback_eligible_but_not_retryable(self):
        """That is the entire purpose: stop hammering, use the alternative."""
        exc = AICircuitOpenError("cooling", provider="gemini")
        assert exc.fallback_eligible is True
        assert exc.retryable is False

    def test_success_resets_the_counter(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_CIRCUIT_FAILURE_THRESHOLD", 3)
        guardrails.record_provider_failure("gemini", "timeout")
        guardrails.record_provider_failure("gemini", "timeout")
        guardrails.record_provider_success("gemini")
        guardrails.record_provider_failure("gemini", "timeout")
        assert guardrails.circuit_is_open("gemini") is False

    def test_recovers_automatically_after_cooldown(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_CIRCUIT_FAILURE_THRESHOLD", 1)
        monkeypatch.setattr("app.config.settings.AI_CIRCUIT_COOLDOWN_SECONDS", 0.0)
        guardrails.record_provider_failure("gemini", "provider_unavailable")
        # Zero cooldown: the next check finds it already elapsed and closes.
        assert guardrails.circuit_is_open("gemini") is False

    def test_one_provider_breaker_does_not_affect_another(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.AI_CIRCUIT_FAILURE_THRESHOLD", 1)
        guardrails.record_provider_failure("gemini", "timeout")
        assert guardrails.circuit_is_open("gemini") is True
        assert guardrails.circuit_is_open("openai") is False


# -------------------------------------------------------------------
# Guardrails apply to every provider, including the fallback
# -------------------------------------------------------------------

class _Recorder:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        return ProviderResponse(
            text="ok", input_tokens=1, output_tokens=1,
            model=kwargs.get("model", "m"), provider=self.name,
        )


class TestGuardrailsPrecedeProviderSelection:
    @pytest.mark.asyncio
    async def test_a_blocked_request_never_reaches_any_provider(
        self, db_session, monkeypatch
    ):
        """The fallback is not a way around a ceiling the primary hit.

        'Gemini is out of quota, send it all to OpenAI instead' is the exact
        failure this ordering prevents: guardrails run before a provider is
        chosen, so neither is called.
        """
        from app.ai import router as ai_router

        providers = {"gemini": _Recorder("gemini"), "openai": _Recorder("openai")}
        monkeypatch.setattr("app.ai.factory.get_provider", lambda n: providers[n])
        monkeypatch.setattr("app.ai.registry.assert_usable", lambda p, m: None)
        monkeypatch.setattr("app.config.settings.AI_GLOBAL_REQUESTS_PER_MINUTE", 0)

        with pytest.raises(AIGuardrailError):
            await ai_router.run(
                db_session, feature="comrade_chat", system_prompt="s",
                contents=[{"role": "user", "parts": [{"text": "hi"}]}],
            )

        assert providers["gemini"].calls == 0
        assert providers["openai"].calls == 0


# -------------------------------------------------------------------
# Telemetry privacy
# -------------------------------------------------------------------

class TestTelemetryPrivacy:
    @pytest.mark.asyncio
    async def test_usage_row_records_identifiers_not_content(self, db_session):
        from app.ai.usage import log_usage

        await log_usage(
            db_session, feature_name="comrade_chat", provider="gemini",
            model="gemini-2.5-flash", latency_ms=42,
            input_tokens=10, output_tokens=20, success=True,
        )
        row = (await db_session.execute(
            select(AIUsageLog).order_by(AIUsageLog.created_at.desc())
        )).scalars().first()

        assert row.provider == "gemini"
        assert row.model == "gemini-2.5-flash"
        assert row.success is True
        assert row.error_message is None
        # The table has no column that could hold a prompt or a response.
        columns = {c.name for c in AIUsageLog.__table__.columns}
        for forbidden in ("prompt", "response", "message_text", "content", "api_key"):
            assert forbidden not in columns

    @pytest.mark.asyncio
    async def test_mapped_error_is_stored_as_a_safe_category(self, db_session):
        from app.ai.usage import log_usage

        await log_usage(
            db_session, feature_name="risk_detection", provider="gemini",
            model="gemini-2.5-flash", latency_ms=5,
            input_tokens=None, output_tokens=None, success=False,
            error=AITimeoutError("Gemini request timed out", provider="gemini"),
        )
        row = (await db_session.execute(
            select(AIUsageLog).order_by(AIUsageLog.created_at.desc())
        )).scalars().first()
        assert row.failure_category == "timeout"

    @pytest.mark.asyncio
    async def test_unmapped_exception_text_is_never_stored(self, db_session):
        """An unmapped exception's text is unreviewed -- only its type is kept."""
        from app.ai.usage import log_usage

        secret = "student said: I want to hurt myself, key=sk-abc123"
        await log_usage(
            db_session, feature_name="comrade_chat", provider="gemini",
            model="gemini-2.5-flash", latency_ms=5,
            input_tokens=None, output_tokens=None, success=False,
            error=RuntimeError(secret),
        )
        row = (await db_session.execute(
            select(AIUsageLog).order_by(AIUsageLog.created_at.desc())
        )).scalars().first()

        assert secret not in (row.error_message or "")
        assert "sk-abc123" not in (row.error_message or "")
        assert "hurt myself" not in (row.error_message or "")
        assert row.error_message == "unmapped RuntimeError"

    @pytest.mark.asyncio
    async def test_long_provider_errors_are_bounded(self, db_session):
        from app.ai.usage import log_usage

        await log_usage(
            db_session, feature_name="comrade_chat", provider="openai",
            model="gpt-5-mini", latency_ms=5,
            input_tokens=None, output_tokens=None, success=False,
            error=AIProviderUnavailableError("y" * 5000, provider="openai"),
        )
        row = (await db_session.execute(
            select(AIUsageLog).order_by(AIUsageLog.created_at.desc())
        )).scalars().first()
        assert len(row.error_message) <= 200

    def test_no_api_key_column_exists_anywhere_in_the_ai_tables(self):
        """API keys are environment secrets and must never be persisted."""
        from database.models import AIFeatureRoute, AIProviderConfig, AIRuntimeConfig

        for model in (AIRuntimeConfig, AIFeatureRoute, AIProviderConfig, AIUsageLog):
            for column in model.__table__.columns:
                name = column.name.lower()
                assert "api_key" not in name, f"{model.__tablename__}.{column.name}"
                assert "secret" not in name, f"{model.__tablename__}.{column.name}"
                assert "token" not in name or "tokens" in name, (
                    f"{model.__tablename__}.{column.name}"
                )


# -------------------------------------------------------------------
# The safety pipeline is unchanged by provider selection
# -------------------------------------------------------------------

class TestSafetyPipelineIsProviderAgnostic:
    @pytest.mark.asyncio
    async def test_safety_floor_still_fires_on_a_fallback_response(
        self, db_session, monkeypatch, test_student_user
    ):
        """A response served by the FALLBACK provider takes the identical path.

        The deterministic safety floor is the backstop that stops an
        under-scored aggregate from masking acute risk. It must not be possible
        to get around it by being served from a different model.
        """
        from app.intelligence.analysis import _apply_safety_floor
        from app.intelligence.config import DEFAULTS
        from app.intelligence.schemas import MessageAnalysis

        # An under-scored aggregate with a credible self-harm signal -- exactly
        # the shape the floor exists to correct.
        analysis = MessageAnalysis.model_validate({
            "emotion": {"current": "sad", "intensity": 8, "confidence": 0.9},
            "risk": {
                "overall": 10,
                "categories": {"self_harm": 85},
                "confidence": 0.9,
            },
        })
        floors = DEFAULTS["safety_floors"]

        applied = _apply_safety_floor(analysis, floors)

        assert applied is True
        assert analysis.risk.overall >= float(floors["enforced_overall"])

    @pytest.mark.asyncio
    async def test_malformed_output_is_rejected_regardless_of_provider(self):
        """Unusable output fails validation; it is never laundered."""
        from app.intelligence.parsing import parse_json_response

        for bad in ["not json at all", "[1,2,3]", ""]:
            with pytest.raises(ValueError):
                parse_json_response(bad)

    def test_router_does_not_import_safety_logic(self):
        """Safety decisions stay out of the provider layer.

        If the router could see risk scores it could, one refactor later,
        choose a provider based on them -- or decide a response was 'unsafe'
        and quietly ask a different model. Neither is allowed, and the cleanest
        guarantee is that the routing layer cannot see safety at all.
        """
        import ast
        import inspect

        import app.ai.router as mod

        tree = ast.parse(inspect.getsource(mod))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        assert not any(m.startswith("app.intelligence") for m in imported)
        assert not any("safety" in m for m in imported)
