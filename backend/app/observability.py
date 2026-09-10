"""
Request correlation, structured logging, and error reporting.

Kio handles mental-health data belonging largely to minors, so the governing
rule here is that operational visibility must never become a second copy of
the thing being protected. Every log line carries enough to trace a request --
id, route, status, duration -- and nothing that identifies what a student
said, only that they said something.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

# The id of the request currently being served, readable from anywhere in the
# call stack without threading a parameter through every function.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"

# A client-supplied id is accepted so a trace can span the browser and the API,
# but it is echoed into logs and headers, so it is only allowed to be a short
# opaque token. Without this a caller could inject newlines and forge log
# lines, or wedge megabytes into every record.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Paths that must not fill the log with noise. Health checks run every few
# seconds forever; logging each one buries the requests that matter.
_QUIET_PATHS = frozenset({"/health", "/health/db", "/favicon.ico"})


def get_request_id() -> str:
    """The current request's id, or '-' outside a request."""
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Attaches the current request id to every record, for the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns a request id, logs the outcome, and returns the id to the caller.

    The id is on the response whether the request succeeded or failed --
    especially when it failed, because a user reporting "it broke" with a
    reference is the difference between finding the log line and guessing.
    """

    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if _SAFE_REQUEST_ID.match(supplied) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            # The exception handler builds the client response; this only
            # records that the request died and how long it took to do so.
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed method=%s path=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                duration_ms,
            )
            request_id_var.reset(token)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        if request.url.path not in _QUIET_PATHS:
            # Path only, never the query string: reset and verification tokens
            # travel there, and a log file is not where they belong.
            level = logging.WARNING if response.status_code >= 500 else logging.INFO
            logger.log(
                level,
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        request_id_var.reset(token)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Response hardening headers.

    The API serves JSON to a separate origin, so its own CSP can be maximally
    strict -- it renders nothing. The frontend's policy lives in the nginx
    config, where it can be written against what the page actually loads.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Never let a browser second-guess a declared content type; that is how
        # a JSON error body becomes executable script.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # This origin returns data, never a document, so nothing may be loaded
        # or framed from it at all.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )
        # Only in production, and only over TLS: sending HSTS from a local
        # http:// dev server would pin the developer's browser to https for
        # localhost and break every other project on the machine.
        if settings.is_production and request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def scrub_event(event: dict, _hint: dict) -> dict | None:
    """
    Sentry `before_send`: strip anything that could carry personal content.

    Sentry is for knowing that something broke and where. It is not a place to
    put a student's message to Comrade, their email address, or a token that
    would let someone act as them. Request bodies are dropped wholesale rather
    than filtered field by field, because a deny-list has to be kept in step
    with every schema change and a drop does not.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        # Strip query strings: verification and password-reset tokens ride there.
        if isinstance(request.get("query_string"), str):
            request["query_string"] = ""
        url = request.get("url")
        if isinstance(url, str) and "?" in url:
            request["url"] = url.split("?", 1)[0]
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in {"authorization", "cookie", "x-api-key", "set-cookie"}:
                    headers.pop(name, None)
    # Usernames and emails identify a specific child; the id is enough to find
    # the account if an on-call engineer genuinely needs to.
    user = event.get("user")
    if isinstance(user, dict):
        user.pop("email", None)
        user.pop("username", None)
        user.pop("ip_address", None)
    return event


def init_sentry() -> bool:
    """
    Start Sentry when a DSN is configured. Returns whether it was enabled.

    Absence of a DSN is the off switch, so development and CI cannot report
    into a production project by forgetting a flag. A missing SDK is not fatal:
    error reporting is important, but not so important that its absence should
    stop students reaching a counselor.
    """
    if not settings.sentry_enabled:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping.")
        return False

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        # send_default_pii would attach headers, cookies and user identifiers
        # by default. For this application that is precisely the wrong default.
        send_default_pii=False,
        before_send=scrub_event,
        integrations=[
            StarletteIntegration(failed_request_status_codes={500, 599}),
            FastApiIntegration(failed_request_status_codes={500, 599}),
        ],
    )
    logger.info("Sentry initialised for environment=%s", settings.ENVIRONMENT)
    return True


def report_exception(exc: BaseException, **context) -> None:
    """
    Send an exception to Sentry if enabled, and never fail because of it.

    Used by background work, where there is no request to attach to and no
    caller left to notice that reporting itself went wrong.
    """
    if not settings.sentry_enabled:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("request_id", get_request_id())
            for key, value in context.items():
                scope.set_tag(key, str(value))
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 - reporting must never mask the original
        logger.exception("Failed to report an exception to Sentry")
