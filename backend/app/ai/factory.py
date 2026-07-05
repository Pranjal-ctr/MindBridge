"""
AIProviderFactory: name -> AIProvider instance.

To add a new provider (Claude, OpenAI, Ollama, ...):
1. Create app/ai/providers/<name>.py implementing AIProvider.
2. Add it to _REGISTRY below.
That's it -- AIRouter and everything upstream is provider-agnostic.
"""

from __future__ import annotations

from app.ai.providers.base import AIProvider
from app.ai.providers.gemini import GeminiProvider

_REGISTRY: dict[str, type[AIProvider]] = {
    "gemini": GeminiProvider,
}

_instances: dict[str, AIProvider] = {}


def get_provider(provider_name: str) -> AIProvider:
    """Lazily instantiate and cache a singleton provider instance by name."""
    if provider_name not in _REGISTRY:
        raise ValueError(f"Unknown AI provider: {provider_name!r}")

    if provider_name not in _instances:
        _instances[provider_name] = _REGISTRY[provider_name]()

    return _instances[provider_name]
