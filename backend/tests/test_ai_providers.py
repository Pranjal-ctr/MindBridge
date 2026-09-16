"""
Provider abstraction: registry, adapters, error mapping, retry and fallback.

No test here makes a real provider call. Gemini and OpenAI are both driven
through monkeypatched transports, which is the only way to exercise a timeout,
a 503 and a rate limit deterministically -- and the only responsible way to
test a paid API.

The organising idea in these tests is that retry and fallback must be decided
by the *class* of an error, never by matching its text. A provider rewording a
message should not be able to change Kio's failover behaviour, and the tests
below assert the classification directly rather than through string matching.
"""

import asyncio
import uuid

import httpx
import pytest

from app.ai import factory, guardrails, registry
from app.ai.config_loader import FeatureRoute
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIStructuredOutputError,
    AITimeoutError,
    AIUnknownProviderError,
)
from app.ai.providers.base import ProviderResponse
from app.ai.providers.openai import OpenAIProvider, _to_openai_messages


@pytest.fixture(autouse=True)
def _clean_guardrails():
    """Guardrail counters and breakers are process-global; isolate each test."""
    guardrails.reset_state()
    yield
    guardrails.reset_state()


# -------------------------------------------------------------------
# Registry
# -------------------------------------------------------------------

class TestRegistry:
    def test_gemini_flash_is_supported(self):
        assert registry.is_supported_provider("gemini")
        assert registry.is_supported_model("gemini", "gemini-2.5-flash")

    def test_openai_gpt5_mini_is_supported(self):
        assert registry.is_supported_provider("openai")
        assert registry.is_supported_model("openai", "gpt-5-mini")

    def test_unsupported_provider_is_rejected(self):
        assert not registry.is_supported_provider("anthropic")
        with pytest.raises(AIUnknownProviderError):
            registry.get_provider_spec("anthropic")

    def test_unsupported_model_is_rejected(self):
        assert not registry.is_supported_model("gemini", "gemini-2.5-pro")

    def test_provider_model_mismatch_is_rejected(self):
        """A real model, on the wrong provider. The likelier admin mistake."""
        assert not registry.is_supported_model("gemini", "gpt-5-mini")
        assert not registry.is_supported_model("openai", "gemini-2.5-flash")

    def test_describe_registry_never_exposes_a_key(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "sk-super-secret-value")
        payload = registry.describe_registry()
        blob = str(payload)
        assert "sk-super-secret-value" not in blob
        gemini = next(p for p in payload if p["provider_id"] == "gemini")
        # Availability, not the value.
        assert gemini["credential_configured"] is True
        assert gemini["credential_setting"] == "GEMINI_API_KEY"


class TestCredentialRules:
    def test_gemini_usable_with_only_its_own_key(self, monkeypatch):
        """The current deployment: Gemini key present, OpenAI key absent."""
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "g-key")
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        registry.assert_usable("gemini", "gemini-2.5-flash")  # must not raise

    def test_missing_openai_key_does_not_affect_gemini(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "g-key")
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        assert registry.credential_configured("gemini") is True
        assert registry.credential_configured("openai") is False
        registry.assert_usable("gemini", "gemini-2.5-flash")

    def test_openai_unusable_without_its_key(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
        with pytest.raises(AIConfigurationError) as exc:
            registry.assert_usable("openai", "gpt-5-mini")
        # The message must name the variable so an operator knows what to set.
        assert "OPENAI_API_KEY" in str(exc.value)

    def test_missing_gemini_key_makes_gemini_unusable(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "   ")
        with pytest.raises(AIConfigurationError):
            registry.assert_usable("gemini", "gemini-2.5-flash")


class TestFactory:
    def test_resolves_both_supported_providers(self):
        assert factory.get_provider("gemini").name == "gemini"
        assert factory.get_provider("openai").name == "openai"

    def test_unknown_provider_raises(self):
        with pytest.raises(AIUnknownProviderError):
            factory.get_provider("llama")


# -------------------------------------------------------------------
# OpenAI adapter (mocked transport)
# -------------------------------------------------------------------

def _openai_response(status_code: int, payload: dict | None = None, text: str = ""):
    """Build an httpx.Response as the adapter would receive it."""
    return httpx.Response(
        status_code=status_code,
        json=payload if payload is not None else None,
        text=text if payload is None else None,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def _install_openai_transport(monkeypatch, handler):
    """Route the adapter's httpx client through `handler(request) -> Response`."""

    async def fake_post(self, url, **kwargs):  # noqa: ANN001
        return handler(kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)


_OK_BODY = {
    "model": "gpt-5-mini",
    "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
}


class TestOpenAIAdapter:
    @pytest.mark.asyncio
    async def test_successful_call_is_normalized(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        _install_openai_transport(monkeypatch, lambda kw: _openai_response(200, _OK_BODY))

        result = await OpenAIProvider().generate(
            model="gpt-5-mini",
            system_prompt="be kind",
            contents=[{"role": "user", "parts": [{"text": "hi"}]}],
            temperature=0.7,
            max_output_tokens=256,
        )

        # Normalized into Kio's shape -- nothing OpenAI-specific escapes.
        assert isinstance(result, ProviderResponse)
        assert result.text == "hello"
        assert result.input_tokens == 11
        assert result.output_tokens == 7
        assert result.total_tokens == 18
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_missing_key_is_a_configuration_error_not_a_call(self, monkeypatch):
        """No key means no request is made at all -- and no fallback."""
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")

        called = False

        def handler(kw):
            nonlocal called
            called = True
            return _openai_response(200, _OK_BODY)

        _install_openai_transport(monkeypatch, handler)

        with pytest.raises(AIConfigurationError) as exc:
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
            )
        assert called is False
        assert exc.value.fallback_eligible is False
        assert exc.value.retryable is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,expected",
        [
            (401, AIAuthenticationError),
            (403, AIAuthenticationError),
            (429, AIRateLimitError),
            (404, AIConfigurationError),
            (500, AIProviderUnavailableError),
            (503, AIProviderUnavailableError),
        ],
    )
    async def test_status_codes_map_to_kio_errors(self, monkeypatch, status_code, expected):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        _install_openai_transport(
            monkeypatch, lambda kw: _openai_response(status_code, text="upstream detail")
        )

        with pytest.raises(expected):
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
            )

    @pytest.mark.asyncio
    async def test_auth_error_never_echoes_the_response_body(self, monkeypatch):
        """A 401 body can quote request context; it must not be re-raised."""
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        _install_openai_transport(
            monkeypatch,
            lambda kw: _openai_response(401, text="Incorrect API key sk-leaked-abc123"),
        )

        with pytest.raises(AIAuthenticationError) as exc:
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
            )
        assert "sk-leaked-abc123" not in str(exc.value)

    @pytest.mark.asyncio
    async def test_timeout_maps_to_timeout_error(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")

        async def fake_post(self, url, **kwargs):  # noqa: ANN001
            raise httpx.ReadTimeout("too slow")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(AITimeoutError) as exc:
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
            )
        assert exc.value.fallback_eligible is True

    @pytest.mark.asyncio
    async def test_malformed_body_is_an_invalid_response(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        _install_openai_transport(
            monkeypatch, lambda kw: _openai_response(200, {"unexpected": "shape"})
        )

        with pytest.raises(AIInvalidResponseError):
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
            )

    @pytest.mark.asyncio
    async def test_empty_structured_output_is_a_structured_output_error(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        body = {
            "model": "gpt-5-mini",
            "choices": [{"message": {"content": "  "}, "finish_reason": "stop"}],
            "usage": {},
        }
        _install_openai_transport(monkeypatch, lambda kw: _openai_response(200, body))

        with pytest.raises(AIStructuredOutputError) as exc:
            await OpenAIProvider().generate(
                model="gpt-5-mini", system_prompt="", contents=[],
                temperature=0.7, max_output_tokens=10,
                response_schema={"type": "object"},
            )
        # Never fallback-eligible: a second model is not a fix for unusable output.
        assert exc.value.fallback_eligible is False

    @pytest.mark.asyncio
    async def test_structured_request_sets_json_schema_response_format(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        captured: dict = {}

        def handler(kw):
            captured.update(kw.get("json") or {})
            return _openai_response(200, _OK_BODY)

        _install_openai_transport(monkeypatch, handler)

        await OpenAIProvider().generate(
            model="gpt-5-mini", system_prompt="", contents=[],
            temperature=0.7, max_output_tokens=10,
            response_schema={"type": "object", "properties": {"a": {"type": "string"}}},
        )
        assert captured["response_format"]["type"] == "json_schema"
        assert captured["response_format"]["json_schema"]["schema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_gpt5_family_omits_temperature_and_uses_max_completion_tokens(
        self, monkeypatch
    ):
        """gpt-5-mini rejects a non-default temperature; the adapter absorbs that."""
        monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
        captured: dict = {}

        def handler(kw):
            captured.update(kw.get("json") or {})
            return _openai_response(200, _OK_BODY)

        _install_openai_transport(monkeypatch, handler)

        await OpenAIProvider().generate(
            model="gpt-5-mini", system_prompt="", contents=[],
            temperature=0.9, max_output_tokens=321,
        )
        assert "temperature" not in captured
        assert captured["max_completion_tokens"] == 321
        assert "max_tokens" not in captured

    def test_message_translation_from_kio_shape(self):
        """Kio's internal history is Gemini-shaped; the adapter converts it."""
        messages = _to_openai_messages(
            "system rules",
            [
                {"role": "user", "parts": [{"text": "hello"}]},
                {"role": "model", "parts": [{"text": "hi there"}]},
            ],
        )
        assert messages == [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "hello"},
            # "model" (Gemini) becomes "assistant" (OpenAI).
            {"role": "assistant", "content": "hi there"},
        ]


# -------------------------------------------------------------------
# Gemini adapter error mapping (no network)
# -------------------------------------------------------------------

class TestGeminiErrorMapping:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (asyncio.TimeoutError(), AITimeoutError),
            (Exception("429 RESOURCE_EXHAUSTED"), AIRateLimitError),
            (Exception("503 UNAVAILABLE"), AIProviderUnavailableError),
            (Exception("API_KEY_INVALID"), AIAuthenticationError),
            (Exception("NOT_FOUND: model"), AIConfigurationError),
            (Exception("connection reset"), AIProviderUnavailableError),
        ],
    )
    def test_exceptions_map_to_kio_categories(self, exc, expected):
        from app.ai.providers.gemini import _map_exception

        assert isinstance(_map_exception(exc), expected)

    def test_auth_mapping_does_not_echo_provider_text(self):
        from app.ai.providers.gemini import _map_exception

        mapped = _map_exception(Exception("API_KEY_INVALID key=AIzaSyLEAKED"))
        assert "AIzaSyLEAKED" not in str(mapped)


# -------------------------------------------------------------------
# Retry and fallback policy
# -------------------------------------------------------------------

class _ScriptedProvider:
    """A provider that yields a scripted sequence of outcomes."""

    def __init__(self, name, outcomes):
        self.name = name
        self.outcomes = list(outcomes)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcomes
        if isinstance(outcome, Exception):
            raise outcome
        return ProviderResponse(
            text=outcome, input_tokens=1, output_tokens=1,
            model=kwargs.get("model", "m"), provider=self.name,
        )


@pytest.fixture
def scripted(monkeypatch):
    """Install scripted providers and skip real backoff sleeps."""
    installed: dict[str, _ScriptedProvider] = {}

    def install(primary_outcomes, fallback_outcomes=None):
        installed["gemini"] = _ScriptedProvider("gemini", primary_outcomes)
        installed["openai"] = _ScriptedProvider("openai", fallback_outcomes or [])
        monkeypatch.setattr(
            "app.ai.factory.get_provider", lambda name: installed[name]
        )
        # Both providers are credentialed for these tests: the subject is the
        # retry/fallback policy, not the credential rules.
        monkeypatch.setattr("app.ai.registry.assert_usable", lambda p, m: None)

        async def no_sleep(_seconds):
            return None

        monkeypatch.setattr("app.ai.router.asyncio.sleep", no_sleep)
        return installed

    return install


def _route(fallback=True, max_retries=2):
    return FeatureRoute(
        feature_name="comrade_chat",
        primary_provider="gemini",
        primary_model="gemini-2.5-flash",
        fallback_provider="openai" if fallback else None,
        fallback_model="gpt-5-mini" if fallback else None,
        max_retries=max_retries,
        source="platform_config",
    )


async def _run(db, route, **kwargs):
    from app.ai import router as ai_router

    return await ai_router._attempt(
        db, route, "comrade_chat",
        system_prompt="sys",
        contents=[{"role": "user", "parts": [{"text": "hi"}]}],
        temperature=0.7,
        max_output_tokens=256,
        response_schema=None,
        conversation_id=None,
        student_id=None,
        **kwargs,
    )


class TestRetryAndFallback:
    @pytest.mark.asyncio
    async def test_timeout_falls_back_to_secondary(self, db_session, scripted):
        providers = scripted(
            [AITimeoutError("slow", provider="gemini")] * 3,
            ["from openai"],
        )
        text, metadata = await _run(db_session, _route())

        assert text == "from openai"
        assert metadata["provider"] == "openai"
        assert metadata["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_transient_5xx_falls_back(self, db_session, scripted):
        scripted(
            [AIProviderUnavailableError("503", provider="gemini")] * 3,
            ["from openai"],
        )
        text, metadata = await _run(db_session, _route())
        assert metadata["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_retries_are_bounded_then_fall_back(self, db_session, scripted):
        providers = scripted(
            [AITimeoutError("slow", provider="gemini")] * 10,
            ["ok"],
        )
        await _run(db_session, _route(max_retries=2))
        # 1 initial attempt + 2 retries, then stop. Not 10.
        assert providers["gemini"].calls == 3

    @pytest.mark.asyncio
    async def test_route_cannot_request_unbounded_retries(self, db_session, scripted):
        """A DB row asking for 99 retries is capped by the router's ceiling."""
        providers = scripted([AITimeoutError("slow")] * 50, ["ok"])
        await _run(db_session, _route(max_retries=99))
        from app.ai.router import _MAX_RETRIES_CEILING

        assert providers["gemini"].calls == _MAX_RETRIES_CEILING + 1

    @pytest.mark.asyncio
    async def test_permanent_auth_error_does_not_fall_back(self, db_session, scripted):
        """An invalid key is an operator problem, not an availability one.

        Failing over here would quietly serve every request from the paid
        secondary provider while the primary's credential stays broken.
        """
        providers = scripted(
            [AIAuthenticationError("bad key", provider="gemini")],
            ["from openai"],
        )
        with pytest.raises(AIAuthenticationError):
            await _run(db_session, _route())

        assert providers["gemini"].calls == 1      # not retried
        assert providers["openai"].calls == 0      # not failed over

    @pytest.mark.asyncio
    async def test_rate_limit_retries_but_does_not_fall_back(self, db_session, scripted):
        """429 is retryable but not fallback-eligible -- a cost decision.

        Redirecting throttled traffic at a second paid provider converts a
        throttle into a bill, so the classification separates the two.
        """
        providers = scripted(
            [AIRateLimitError("429", provider="gemini")] * 5,
            ["from openai"],
        )
        with pytest.raises(AIRateLimitError):
            await _run(db_session, _route(max_retries=2))

        assert providers["gemini"].calls == 3   # retried
        assert providers["openai"].calls == 0   # but never failed over

    @pytest.mark.asyncio
    async def test_configuration_error_does_not_fall_back(self, db_session, scripted):
        providers = scripted(
            [AIConfigurationError("unsupported model", provider="gemini")],
            ["from openai"],
        )
        with pytest.raises(AIConfigurationError):
            await _run(db_session, _route())
        assert providers["openai"].calls == 0

    @pytest.mark.asyncio
    async def test_fallback_disabled_means_no_second_provider(self, db_session, scripted):
        providers = scripted([AITimeoutError("slow")] * 5, ["from openai"])
        with pytest.raises(AITimeoutError):
            await _run(db_session, _route(fallback=False))
        assert providers["openai"].calls == 0

    @pytest.mark.asyncio
    async def test_no_loop_back_to_primary_when_both_fail(self, db_session, scripted):
        """PRIMARY -> FALLBACK -> stop. Never PRIMARY -> FALLBACK -> PRIMARY."""
        providers = scripted(
            [AITimeoutError("slow")] * 10,
            [AITimeoutError("also slow")] * 10,
        )
        with pytest.raises(AITimeoutError):
            await _run(db_session, _route(max_retries=1))

        assert providers["gemini"].calls == 2   # 1 + 1 retry
        assert providers["openai"].calls == 2   # 1 + 1 retry
        # Four calls total, bounded. No third round.

    @pytest.mark.asyncio
    async def test_invalid_response_is_not_re_asked_of_another_model(
        self, db_session, scripted
    ):
        """Unusable output must never be laundered through a second provider.

        This is the pattern that would turn a provider swap into a way around
        validation: "the model said something we could not use, so ask a
        different model and take that instead".
        """
        providers = scripted(
            [AIInvalidResponseError("garbage", provider="gemini")],
            ["clean text from openai"],
        )
        with pytest.raises(AIInvalidResponseError):
            await _run(db_session, _route())
        assert providers["openai"].calls == 0
