"""
The controlled registry of providers and models this build of Kio supports.

The distinction this file exists to enforce:

    CODE (here)   knows HOW to talk to Gemini and OpenAI, and which models
                  have actually been exercised against Kio's prompts.
    ENV / DB      decide WHICH of those supported combinations is active.

So an admin picks from a list; they never type a model name. That matters more
here than in a generic product: `risk_detection` asks a model to judge whether
a teenager is in danger, and "whatever string someone pasted into a box" is not
an acceptable answer to "which model made that judgement". It also closes the
obvious injection route -- a model id flows into an outbound API call, and an
allowlist means a hostile string never gets that far.

Adding a model is a code change, deliberately: it should come with a prompt
review and a pricing entry, not a text field.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import config as app_config
from app.ai.errors import AIConfigurationError, AIUnknownProviderError


@dataclass(frozen=True)
class ModelSpec:
    """One supported model."""

    model_id: str
    display_name: str
    #: Whether the adapter can constrain this model to a JSON schema. Every
    #: structured Kio feature (risk detection, insights, reports, activities)
    #: needs this; a model without it would still be parsed defensively, but
    #: would fail schema validation far more often.
    supports_structured_output: bool = True


@dataclass(frozen=True)
class ProviderSpec:
    """One supported provider and the models Kio will run on it."""

    provider_id: str
    display_name: str
    #: Name of the settings attribute holding this provider's API key. The key
    #: itself is never read here -- only whether it is non-empty.
    credential_setting: str
    models: tuple[ModelSpec, ...]


SUPPORTED_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        provider_id="gemini",
        display_name="Google Gemini",
        credential_setting="GEMINI_API_KEY",
        models=(
            ModelSpec("gemini-2.5-flash", "Gemini 2.5 Flash"),
        ),
    ),
    ProviderSpec(
        provider_id="openai",
        display_name="OpenAI",
        credential_setting="OPENAI_API_KEY",
        models=(
            ModelSpec("gpt-5-mini", "GPT-5 mini"),
        ),
    ),
)

_BY_ID: dict[str, ProviderSpec] = {p.provider_id: p for p in SUPPORTED_PROVIDERS}


def get_provider_spec(provider_id: str) -> ProviderSpec:
    """The spec for a provider, or AIUnknownProviderError."""
    spec = _BY_ID.get(provider_id)
    if spec is None:
        raise AIUnknownProviderError(
            f"Unsupported AI provider: {provider_id!r}", provider=provider_id
        )
    return spec


def is_supported_provider(provider_id: str) -> bool:
    return provider_id in _BY_ID


def is_supported_model(provider_id: str, model_id: str) -> bool:
    """Whether this exact provider/model pair is supported.

    Pair, not model alone: `gpt-5-mini` on Gemini is as wrong as a model that
    does not exist, and is the more likely mistake for an admin to make.
    """
    spec = _BY_ID.get(provider_id)
    if spec is None:
        return False
    return any(m.model_id == model_id for m in spec.models)


def credential_configured(provider_id: str) -> bool:
    """Whether this provider's API key is present in the server environment.

    Reads only the emptiness of the value. The key itself never leaves
    settings, is never returned, and is never logged.
    """
    spec = _BY_ID.get(provider_id)
    if spec is None:
        return False
    # Read through the module rather than an import-time binding: credential
    # presence must reflect the settings object that is live *now*. (A test
    # that reloads app.config would otherwise leave this holding a stale
    # object and reporting a key as absent when it is configured.)
    return bool(
        (getattr(app_config.settings, spec.credential_setting, "") or "").strip()
    )


def assert_usable(provider_id: str, model_id: str) -> None:
    """Raise AIConfigurationError unless this pair is supported AND credentialed.

    Called on the request path (via the factory) and on the admin save path, so
    the same three rules -- known provider, allowed model, key present -- decide
    both "may this be saved" and "may this be called".
    """
    spec = get_provider_spec(provider_id)

    if not is_supported_model(provider_id, model_id):
        allowed = ", ".join(m.model_id for m in spec.models)
        raise AIConfigurationError(
            f"Model {model_id!r} is not supported for provider {provider_id!r}. "
            f"Supported: {allowed}",
            provider=provider_id,
        )

    if not credential_configured(provider_id):
        raise AIConfigurationError(
            f"{spec.display_name} is supported, but {spec.credential_setting} "
            f"is not configured on this server.",
            provider=provider_id,
        )


def describe_registry() -> list[dict]:
    """Registry as plain data for the admin UI.

    Carries credential *availability* as a boolean and nothing else -- the admin
    page needs to know it cannot select OpenAI yet, not what the key is.
    """
    return [
        {
            "provider_id": spec.provider_id,
            "display_name": spec.display_name,
            "credential_configured": credential_configured(spec.provider_id),
            "credential_setting": spec.credential_setting,
            "models": [
                {
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "supports_structured_output": m.supports_structured_output,
                }
                for m in spec.models
            ],
        }
        for spec in SUPPORTED_PROVIDERS
    ]
