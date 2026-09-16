"""
AIProvider abstract interface.

Every LLM provider (Gemini, OpenAI, ...) implements this interface. The
AIRouter and AIProviderFactory only ever depend on this contract -- adding a
new provider means creating a new file in this package that implements
AIProvider, registering the class in app/ai/factory.py, and declaring its
models in app/ai/registry.py. Nothing else changes.

Two rules hold this boundary:

1. Provider SDKs and provider-specific request/response shapes live *only*
   inside an adapter. Nothing upstream may import `google.genai`, know what a
   `response_format` is, or branch on which provider answered.

2. Adapters raise app.ai.errors types, never raw SDK exceptions. The router
   decides retry and fallback from the error class, not from string matching,
   so a provider changing its message wording cannot silently change Kio's
   failover behaviour.

Adapters do not implement retry, backoff, timeout policy, or fallback. They
make one call, with the deadline they are handed, and report what happened.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ProviderResponse:
    """Normalized result of a single generation call, regardless of provider.

    Token counts are `None` when the provider did not report them. They are
    never estimated: a fabricated count would flow into cost reporting and
    token ceilings, and a guardrail enforced against invented numbers is worse
    than no guardrail.
    """

    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str
    #: Which adapter produced this. Set by the router from the resolved route.
    provider: str | None = None
    #: The provider's own request identifier, when it returns one safely in a
    #: response header. Useful when escalating to a provider's support; it is
    #: an opaque id, never content.
    provider_request_id: str | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


class AIProvider(ABC):
    """Abstract base class all AI providers must implement."""

    name: ClassVar[str]

    @abstractmethod
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
        """Generate a completion.

        `contents` is Kio's neutral history shape: a list of
        ``{"role": "user"|"model", "parts": [{"text": ...}]}``. Adapters
        translate it to their provider's format.

        `response_schema` (a plain JSON-schema dict) requests structured JSON
        output. Providers that support it must constrain the response; callers
        still parse defensively through app/intelligence/parsing.py, because
        "constrained" is not the same as "guaranteed".

        Raises an app.ai.errors.AIError subclass on failure. The router owns
        retry, backoff and fallback.
        """
        ...
