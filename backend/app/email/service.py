"""
Kio Email Service — provider-agnostic interface (Part 10, future-ready).

Email delivery is NOT implemented yet. Invite codes are shown to the student to
share manually. This interface exists so a real provider (Resend, SendGrid,
Amazon SES, SMTP) can be added later by implementing EmailService and
registering it in the factory -- no call-site changes required.

Usage (future):
    email = get_email_service()
    await email.send(to="parent@example.com", subject="...", body="...")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import settings

logger = logging.getLogger(__name__)


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
        """Send an email. Concrete providers plug in credentials + transport."""
        ...


class NoopEmailProvider(EmailService):
    """Default no-op provider: logs instead of sending. Safe with no credentials."""

    name = "noop"

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        logger.info("[email:noop] would send to=%s subject=%r (not delivered)", to, subject)


# Registry of available providers. Future: add "resend", "sendgrid", "ses", "smtp".
_PROVIDERS: dict[str, type[EmailService]] = {
    "noop": NoopEmailProvider,
}

_instance: EmailService | None = None


def get_email_service() -> EmailService:
    """Return the configured email provider singleton (EMAIL_PROVIDER env)."""
    global _instance
    if _instance is None:
        provider_cls = _PROVIDERS.get(settings.EMAIL_PROVIDER, NoopEmailProvider)
        _instance = provider_cls()
    return _instance
