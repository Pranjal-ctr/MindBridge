"""
Gemini provider implementation.

Wraps google-genai. Retry/backoff lives in AIRouter, not here -- this provider
only knows how to make one call and report whether a given exception is transient.
"""

from __future__ import annotations

from google import genai

from app.ai.providers.base import AIProvider, ProviderResponse
from app.config import settings

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


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
    ) -> ProviderResponse:
        client = _get_client()
        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=genai.types.GenerateContentConfig(**config_kwargs),
        )

        usage = response.usage_metadata
        return ProviderResponse(
            text=response.text or "",
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            model=model,
        )

    def is_retryable(self, exc: Exception) -> bool:
        error_str = str(exc)
        return "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
