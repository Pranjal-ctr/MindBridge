"""
AIProvider abstract interface.

Every LLM provider (Gemini, Claude, OpenAI, Ollama, ...) implements this interface.
The AIRouter and AIProviderFactory only ever depend on this contract -- adding a new
provider means creating a new file in this package that implements AIProvider and
registering it in app/ai/factory.py. Nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ProviderResponse:
    """Normalized result of a single generation call, regardless of provider."""

    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str


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
    ) -> ProviderResponse:
        """Generate a completion. Raises on failure -- the router handles retry/fallback.

        `response_schema` (a plain JSON-schema dict) requests structured JSON
        output; providers that support it must constrain the response, others
        may ignore it (callers must still parse defensively).
        """
        ...

    @abstractmethod
    def is_retryable(self, exc: Exception) -> bool:
        """Whether this exception represents a transient error worth retrying (e.g. rate limit)."""
        ...
