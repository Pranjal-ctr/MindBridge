"""
Provider-neutral AI error taxonomy.

The rest of Kio must never see a `google.genai` exception or an httpx status
error. Adapters map their provider's failures onto these types, and the router
makes retry and fallback decisions from two flags rather than from string
matching on exception text:

    retryable          -- worth trying the SAME provider again shortly
    fallback_eligible  -- worth trying a DIFFERENT provider

Those are deliberately separate. A 429 is retryable (backoff may clear it) but
is *not* fallback-eligible by default: a rate limit on Gemini usually means Kio
is sending more traffic than planned, and quietly redirecting that flood at a
second paid provider turns a throttle into a bill. A timeout is both. A missing
API key is neither -- no amount of retrying fixes it, and falling back would
mask a misconfiguration that an operator needs to see.

`category` is the safe, low-cardinality label that goes into telemetry and
`ai_usage_logs.failure_category`. It never contains provider text.
"""

from __future__ import annotations


class AIError(Exception):
    """Base class for every AI-layer failure.

    `safe_message` is what may cross a trust boundary (logs, telemetry, admin
    UI). The exception's own str() may carry more detail for server-side logs,
    but adapters must still never put a credential in either.
    """

    category: str = "unknown"
    retryable: bool = False
    fallback_eligible: bool = False

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider

    @property
    def safe_message(self) -> str:
        """Provider-neutral description, safe to log or show an admin."""
        return f"{self.category} error from AI provider"


class AIConfigurationError(AIError):
    """Missing/unknown provider, model not allowed, credential absent.

    Permanent by definition: the request cannot succeed until an operator
    changes something. Never retried, never failed over -- falling back here
    would hide the very misconfiguration that needs fixing.
    """

    category = "configuration"


class AIUnknownProviderError(AIConfigurationError):
    """A provider name that is not in the registry."""

    category = "unknown_provider"


class AIAuthenticationError(AIError):
    """Credential rejected by the provider (401/403).

    Not fallback-eligible: an invalid key is an operator problem, and silently
    serving every request from the paid secondary provider while the primary's
    key is dead is exactly the failure mode that produces a surprise invoice.
    """

    category = "authentication"


class AITimeoutError(AIError):
    """The provider did not answer within AI_REQUEST_TIMEOUT_SECONDS."""

    category = "timeout"
    retryable = True
    fallback_eligible = True


class AIRateLimitError(AIError):
    """Provider throttled the request (429).

    Retryable with backoff, but NOT fallback-eligible by default -- see the
    module docstring. Redirecting throttled traffic to a second provider is a
    cost decision, not an availability one.
    """

    category = "rate_limit"
    retryable = True
    fallback_eligible = False


class AIProviderUnavailableError(AIError):
    """Provider-side outage: 5xx, connection failure, DNS."""

    category = "provider_unavailable"
    retryable = True
    fallback_eligible = True


class AIInvalidRequestError(AIError):
    """The provider rejected the request as malformed (4xx that is not auth/429).

    Permanent: the same request will be rejected by anyone. Usually a Kio bug
    or an unsupported parameter for that model.
    """

    category = "invalid_request"


class AIInvalidResponseError(AIError):
    """The provider answered, but with something unusable (e.g. empty body).

    Not fallback-eligible. Kio's safe-failure behaviour handles this; asking a
    second model and accepting whatever it says is precisely the pattern that
    would let a provider swap become a way around validation.
    """

    category = "invalid_response"


class AIStructuredOutputError(AIInvalidResponseError):
    """Structured output was requested and the provider could not honour it."""

    category = "structured_output"


class AIGuardrailError(AIError):
    """A Kio-side guardrail refused to make the call at all.

    Raised *before* any provider is contacted, so no cost is incurred and no
    fallback is attempted -- the guardrail applies to every provider equally.
    """

    category = "guardrail"

    def __init__(
        self, message: str, *, guardrail: str, retry_after_seconds: int | None = None
    ) -> None:
        super().__init__(message)
        self.guardrail = guardrail
        self.retry_after_seconds = retry_after_seconds

    @property
    def safe_message(self) -> str:
        return f"blocked by AI guardrail: {self.guardrail}"


class AICircuitOpenError(AIError):
    """The provider is in cooldown after repeated transient failures.

    Fallback-eligible -- that is the entire point of the breaker: stop
    hammering a provider that is down and use the configured alternative.
    Not retryable against the same provider, which is what "open" means.
    """

    category = "circuit_open"
    retryable = False
    fallback_eligible = True
