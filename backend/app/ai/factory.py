"""
AIProviderFactory: provider id -> AIProvider instance.

To add a new provider:
1. Create app/ai/providers/<name>.py implementing AIProvider.
2. Add it to _REGISTRY below.
3. Declare the provider and its models in app/ai/registry.py.

Step 3 is what makes it selectable. A class registered here but absent from
registry.py can never be chosen, which is the intended direction of the
dependency: the registry is the policy, this map is the wiring.
"""

from __future__ import annotations

from app.ai import registry
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openai import OpenAIProvider

_REGISTRY: dict[str, type[AIProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}

_instances: dict[str, AIProvider] = {}


def get_provider(provider_name: str) -> AIProvider:
    """Lazily instantiate and cache a singleton provider instance by name.

    Raises AIUnknownProviderError for a name outside the registry. Note this
    checks support, not credentials: a caller that needs the credential
    guarantee too should use registry.assert_usable(provider, model), which
    the router does before it gets here.
    """
    registry.get_provider_spec(provider_name)  # raises AIUnknownProviderError

    if provider_name not in _instances:
        _instances[provider_name] = _REGISTRY[provider_name]()

    return _instances[provider_name]


def reset_instances() -> None:
    """Drop cached provider instances. For tests."""
    _instances.clear()
