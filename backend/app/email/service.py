"""
Kio Email Service — provider-agnostic delivery.

A concrete provider is selected by EMAIL_PROVIDER. The abstract EmailService
interface means call sites never change when swapping providers:

    from app.email.service import try_send
    await try_send(to="parent@example.com", subject="...", body="...", html="...")

Providers:
    noop    — logs instead of sending. Default. Safe with no credentials, used
              by dev and the test suite so nothing ever leaves the machine.
    resend  — Resend HTTP API (https://resend.com). Uses httpx, which is already
              a dependency, so no extra package is required.

Delivery is best-effort at the call site: `try_send()` never raises, so an email
outage can never turn a successful signup into a 500. Call
`get_email_service().send()` directly only when the caller must handle failure.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 10.0


class EmailDeliveryError(RuntimeError):
    """Raised by a provider when an email could not be handed off for delivery."""


class EmailService(ABC):
    """Abstract email provider. Implement send() for each concrete provider."""

    name: str

    @abstractmethod
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        """Send an email. Raises EmailDeliveryError if the provider rejects it."""
        ...


class NoopEmailProvider(EmailService):
    """Default no-op provider: logs instead of sending. Safe with no credentials."""

    name = "noop"

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        logger.info("[email:noop] would send to=%s subject=%r (not delivered)", to, subject)


class ResendEmailProvider(EmailService):
    """
    Resend (https://resend.com) transactional email over its REST API.

    Requires RESEND_API_KEY and an EMAIL_FROM address on a domain verified in
    the Resend dashboard (SPF/DKIM DNS records). Until a domain is verified,
    Resend only accepts its shared `onboarding@resend.dev` sender, which can
    deliver solely to the account owner's own address.
    """

    name = "resend"
    API_URL = "https://api.resend.com/emails"

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        payload: dict[str, object] = {
            "from": settings.EMAIL_FROM,
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if html:
            payload["html"] = html
        if settings.EMAIL_REPLY_TO:
            payload["reply_to"] = settings.EMAIL_REPLY_TO

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(f"Resend request failed: {exc}") from exc

        if response.status_code >= 400:
            # Body carries Resend's reason (unverified domain, bad key, ...).
            raise EmailDeliveryError(
                f"Resend rejected the message (HTTP {response.status_code}): {response.text[:300]}"
            )

        logger.info("[email:resend] sent to=%s subject=%r", to, subject)


# Registry of available providers. Future: add "sendgrid", "ses", "smtp".
_PROVIDERS: dict[str, type[EmailService]] = {
    "noop": NoopEmailProvider,
    "resend": ResendEmailProvider,
}

_instance: EmailService | None = None


def get_email_service() -> EmailService:
    """Return the configured email provider singleton (EMAIL_PROVIDER env)."""
    global _instance
    if _instance is not None:
        return _instance

    configured = (settings.EMAIL_PROVIDER or "noop").strip().lower()
    provider_cls = _PROVIDERS.get(configured)

    if provider_cls is None:
        logger.warning("Unknown EMAIL_PROVIDER=%r; falling back to noop.", configured)
        provider_cls = NoopEmailProvider
    elif provider_cls is ResendEmailProvider and not settings.RESEND_API_KEY:
        # Misconfiguration should degrade to "log the link", never to a crash loop.
        logger.warning("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty; falling back to noop.")
        provider_cls = NoopEmailProvider

    _instance = provider_cls()
    return _instance


def reset_email_service() -> None:
    """Clear the cached provider. Used by tests that change EMAIL_PROVIDER."""
    global _instance
    _instance = None


async def try_send(*, to: str, subject: str, body: str, html: str | None = None) -> bool:
    """
    Best-effort send. Logs and returns False on failure instead of raising.

    Email delivery is never allowed to fail a user-facing request: a signup that
    succeeded must still return 201 even if the welcome mail bounced.
    """
    try:
        await get_email_service().send(to=to, subject=subject, body=body, html=html)
        return True
    except Exception:  # noqa: BLE001 - deliberately broad; delivery is best-effort
        logger.exception("Email delivery failed for to=%s subject=%r", to, subject)
        return False
