"""
OpenAI provider implementation.

Implemented and supported, but inactive on this deployment: there is no
OPENAI_API_KEY here yet. Nothing in this module runs until an operator adds
that secret AND a platform admin selects OpenAI, so its presence costs
nothing and makes the switch a configuration change rather than a code change.

Built on httpx rather than the `openai` SDK, deliberately:

  - httpx is already a declared Kio dependency (Resend, Google token
    verification), so this adds no package, no transitive tree, and no second
    async HTTP stack.
  - The Chat Completions surface Kio needs is one POST. An SDK would buy
    little and bring its own retry/timeout behaviour that would overlap with
    AIRouter's, which is exactly the duplicated-retry problem to avoid.
  - Explicit control of the timeout, which is the guardrail that matters most.

Everything provider-specific stops here: the role mapping, the request body,
the structured-output mechanism, and the error shapes are all translated into
Kio's neutral types before returning.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidRequestError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIStructuredOutputError,
    AITimeoutError,
)
from app.ai.providers.base import AIProvider, ProviderResponse
from app import config as app_config

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"

#: Models that reject a non-default `temperature`. The gpt-5 family accepts
#: only the default, and sending one is a 400 -- a permanent error that would
#: look like a Kio bug rather than a parameter mismatch. Callers keep passing
#: temperature; this adapter decides whether the model can honour it.
_FIXED_TEMPERATURE_MODELS = frozenset({"gpt-5-mini"})

#: Models that take `max_completion_tokens` instead of `max_tokens`.
_MAX_COMPLETION_TOKENS_MODELS = frozenset({"gpt-5-mini"})


def _to_openai_messages(system_prompt: str, contents: list[dict]) -> list[dict]:
    """Translate Kio's neutral history shape into OpenAI chat messages.

    Kio's internal shape is Gemini-native
    (``{"role": "user"|"model", "parts": [{"text": ...}]}``); OpenAI wants
    ``{"role": "user"|"assistant", "content": "..."}`` with the system prompt
    as the first message rather than a separate field.
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for item in contents:
        role = "assistant" if item.get("role") == "model" else "user"
        parts = item.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if text:
            messages.append({"role": role, "content": text})
    return messages


def _wrap_schema(response_schema: dict) -> dict:
    """Build OpenAI's json_schema response_format from a plain JSON schema.

    OpenAI's strict structured-output mode requires `additionalProperties:
    false` on every object node and every property listed in `required`. Kio's
    schemas are written for Gemini, which has neither requirement, so rather
    than rewriting them for the stricter dialect (and risking the two drifting)
    this uses non-strict json_schema mode. The model is still constrained to
    the schema; the result is still validated by Pydantic downstream, which is
    where correctness is actually decided.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "kio_structured_response",
            "schema": response_schema,
            "strict": False,
        },
    }


def _map_status(status_code: int, body_snippet: str) -> Exception:
    """HTTP status -> Kio error. `body_snippet` is never included in auth errors."""
    if status_code in (401, 403):
        return AIAuthenticationError(
            "OpenAI rejected the API credential", provider="openai"
        )
    if status_code == 429:
        return AIRateLimitError("OpenAI rate limit", provider="openai")
    if status_code == 404:
        return AIConfigurationError("OpenAI rejected the model id", provider="openai")
    if 500 <= status_code < 600:
        return AIProviderUnavailableError("OpenAI is unavailable", provider="openai")
    if 400 <= status_code < 500:
        return AIInvalidRequestError(
            f"OpenAI rejected the request ({status_code}): {body_snippet}",
            provider="openai",
        )
    return AIProviderUnavailableError(
        f"OpenAI returned an unexpected status {status_code}", provider="openai"
    )


class OpenAIProvider(AIProvider):
    name = "openai"

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
        api_key = (app_config.settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            # Defence in depth. The registry and the admin validator both
            # refuse to select OpenAI without a key, so reaching here means a
            # configuration path was missed -- a permanent error, never
            # retried and never failed over.
            raise AIConfigurationError(
                "OPENAI_API_KEY is not configured on this server", provider="openai"
            )

        timeout = timeout_seconds or app_config.settings.AI_REQUEST_TIMEOUT_SECONDS

        payload: dict = {
            "model": model,
            "messages": _to_openai_messages(system_prompt, contents),
        }
        if model in _MAX_COMPLETION_TOKENS_MODELS:
            payload["max_completion_tokens"] = max_output_tokens
        else:
            payload["max_tokens"] = max_output_tokens
        if model not in _FIXED_TEMPERATURE_MODELS:
            payload["temperature"] = temperature
        if response_schema is not None:
            payload["response_format"] = _wrap_schema(response_schema)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await asyncio.wait_for(
                    client.post(
                        _API_URL,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    ),
                    timeout=timeout,
                )
        except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
            raise AITimeoutError("OpenAI request timed out", provider="openai") from exc
        except httpx.HTTPError as exc:
            # Connection, DNS, TLS. Never includes the request, which carries
            # the Authorization header.
            raise AIProviderUnavailableError(
                "OpenAI is unreachable", provider="openai"
            ) from exc

        if response.status_code != 200:
            # Bounded and body-only: the error body may name the offending
            # parameter, which is genuinely useful, but the request (and its
            # Authorization header) is never echoed.
            raise _map_status(response.status_code, response.text[:200])

        try:
            data = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError(
                "OpenAI returned a non-JSON body", provider="openai"
            ) from exc

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError(
                "OpenAI response did not contain a message", provider="openai"
            ) from exc

        if choice.get("finish_reason") == "content_filter":
            # The provider's own filter refused. This is NOT a Kio safety
            # decision and must not be treated as one -- it is an unusable
            # response, handed to the caller's existing safe-failure path.
            raise AIInvalidResponseError(
                "OpenAI filtered the response", provider="openai"
            )

        if response_schema is not None and not text.strip():
            raise AIStructuredOutputError(
                "OpenAI returned empty structured output", provider="openai"
            )
        if not text.strip():
            raise AIInvalidResponseError(
                "OpenAI returned an empty response", provider="openai"
            )

        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            model=data.get("model") or model,
            provider=self.name,
            # Opaque correlation id for provider support escalations.
            provider_request_id=response.headers.get("x-request-id"),
        )
