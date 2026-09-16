"""
Gemini provider implementation.

Wraps google-genai. Retry/backoff and fallback live in AIRouter, not here --
this adapter makes one call, within the deadline it is given, and translates
whatever happens into app.ai.errors.

Kio's neutral `contents` shape is already Gemini's native shape
(``{"role", "parts": [{"text"}]}``), which is why it is the internal one: the
primary provider needs no translation, and the OpenAI adapter does the work.
"""

from __future__ import annotations

import asyncio
import logging

from google import genai

from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidRequestError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.providers.base import AIProvider, ProviderResponse
from app import config as app_config

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_client_timeout_ms: int | None = None


def _get_client(timeout_seconds: float) -> genai.Client:
    """Cached client, rebuilt if the effective timeout changes.

    The SDK takes its timeout at construction, so a changed
    AI_REQUEST_TIMEOUT_SECONDS would otherwise never take effect without a
    restart. Rebuilding on change keeps the cache (one client for the whole
    process, as before) while letting the setting mean what it says.
    """
    global _client, _client_timeout_ms

    timeout_ms = int(timeout_seconds * 1000)
    if _client is None or _client_timeout_ms != timeout_ms:
        _client = genai.Client(
            api_key=app_config.settings.GEMINI_API_KEY,
            http_options=genai.types.HttpOptions(timeout=timeout_ms),
        )
        _client_timeout_ms = timeout_ms
    return _client


def reset_client() -> None:
    """Drop the cached client. For tests and credential rotation."""
    global _client, _client_timeout_ms
    _client = None
    _client_timeout_ms = None


def _map_exception(exc: Exception) -> Exception:
    """Translate a google-genai failure into Kio's provider-neutral taxonomy.

    google-genai does not expose a stable exception hierarchy for every case,
    so this inspects a status code where one is available and falls back to
    matching the canonical Google error *codes* (RESOURCE_EXHAUSTED,
    UNAVAILABLE) rather than human-readable prose, which changes.

    The mapped exception carries no provider text for the authentication case:
    an auth error can echo request context, and the safest assumption is that
    anything the SDK hands back may quote what was sent.
    """
    if isinstance(exc, asyncio.TimeoutError):
        return AITimeoutError("Gemini request timed out", provider="gemini")

    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc)

    if status_code == 401 or status_code == 403 or "API_KEY_INVALID" in text or "PERMISSION_DENIED" in text:
        # Deliberately does not include `text`.
        return AIAuthenticationError("Gemini rejected the API credential", provider="gemini")
    if status_code == 429 or "RESOURCE_EXHAUSTED" in text or "429" in text:
        return AIRateLimitError("Gemini rate limit", provider="gemini")
    if (isinstance(status_code, int) and 500 <= status_code < 600) or "UNAVAILABLE" in text or "INTERNAL" in text:
        return AIProviderUnavailableError("Gemini is unavailable", provider="gemini")
    if status_code == 404 or "NOT_FOUND" in text:
        return AIConfigurationError("Gemini rejected the model id", provider="gemini")
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return AIInvalidRequestError("Gemini rejected the request", provider="gemini")
    if isinstance(exc, (TimeoutError, asyncio.CancelledError)):
        return AITimeoutError("Gemini request timed out", provider="gemini")

    # Connection-level failures surface as httpx/socket errors with no code.
    lowered = text.lower()
    if any(k in lowered for k in ("timeout", "timed out", "deadline")):
        return AITimeoutError("Gemini request timed out", provider="gemini")
    if any(k in lowered for k in ("connection", "unreachable", "dns", "ssl")):
        return AIProviderUnavailableError("Gemini is unreachable", provider="gemini")

    return AIProviderUnavailableError("Gemini call failed", provider="gemini")


class GeminiProvider(AIProvider):
    name = "gemini"

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        contents: list[dict],
        temperature: float,
        max_output_tokens: int,
        response_schema: dict | None = None,
        timeout_seconds: float | None = None,
    ) -> ProviderResponse:
        timeout = timeout_seconds or app_config.settings.AI_REQUEST_TIMEOUT_SECONDS
        client = _get_client(timeout)

        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        try:
            # wait_for as well as the SDK timeout: the SDK's applies per HTTP
            # attempt, and a provider that trickles bytes or an SDK-internal
            # retry can outlive it. This is the deadline the caller was
            # promised, and a student waiting on a chat reply is the reason it
            # has to be one.
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=genai.types.GenerateContentConfig(**config_kwargs),
                ),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 -- mapped, then re-raised
            raise _map_exception(exc) from exc

        text = response.text or ""
        if not text.strip():
            # A blocked or empty candidate. Structured callers would fail
            # schema validation anyway; failing here gives the router a precise
            # category instead of an opaque parse error downstream.
            raise AIInvalidResponseError(
                "Gemini returned an empty response", provider="gemini"
            )

        usage = response.usage_metadata
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            model=model,
            provider=self.name,
        )
