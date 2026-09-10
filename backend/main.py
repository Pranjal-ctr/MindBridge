"""
Kio API — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.observability import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    RequestIdFilter,
    SecurityHeadersMiddleware,
    get_request_id,
    init_sentry,
)
from database.session import engine


def _configure_logging() -> None:
    """
    Give the root logger a handler.

    uvicorn configures only its own loggers, so without this every
    ``logger.*`` call under ``app/`` propagates to a root logger with no
    handler and is discarded. Two of those matter:

    * ``auth.service`` logs the email-verification link so local development
      works with ``EMAIL_PROVIDER=noop`` — unreachable otherwise, since there
      is no other way to obtain the token.
    * ``email.service`` logs delivery failures inside ``try_send``, which
      deliberately never raises. Without a handler a production mail outage
      is completely silent.

    pytest installs its own root handler, which is why the test suite never
    caught this.
    """
    root = logging.getLogger()
    if root.handlers:  # respect a host-provided config (pytest, gunicorn, etc.)
        return
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        # The request id makes a production report ("it failed, reference
        # ab12cd") resolvable to the exact line without guesswork.
        format="%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
    )
    # The filter must sit on the handlers: records reaching the root logger
    # come from every module, and a formatter referencing %(request_id)s would
    # raise on any record that lacks the attribute.
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())

    # httpx logs every outbound request at INFO, full URL included. Kio calls
    # Resend and Google from the server, and a URL is exactly the place a
    # one-time token would sit. Warnings and errors still come through.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


_configure_logging()

logger = logging.getLogger("kio")


# Lifespan: startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage DB connection pool lifecycle."""
    yield
    await engine.dispose()


# Application Factory
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    # Interactive docs enumerate every endpoint, parameter and schema in the
    # product. That is a convenience in development and a map for an attacker
    # in production, so the schema is not served there at all -- None removes
    # the route rather than hiding the link to it.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "🔐 Auth", "description": "Authentication & token management"},
        {"name": "👤 Users", "description": "User profile management"},
        {"name": "💬 Conversations", "description": "ChatGPT-style AI conversation management"},
        {"name": "🧠 Memory", "description": "AI memory system for student context"},
        {"name": "💚 Wellness", "description": "Wellness records, goals, and journal entries"},
        {"name": "⚠️ Risk", "description": "Risk detection and assessment engine"},
        {"name": "👨‍👩‍👧 Parents", "description": "Parent insights and child wellness dashboard"},
        {"name": "🩺 Counselors", "description": "Counselor sessions, notes, and student profiles"},
        {"name": "📊 Analytics", "description": "School-wide anonymized analytics"},
        {"name": "🔔 Notifications", "description": "User notification management"},
        {"name": "💳 Subscriptions", "description": "Subscription and payment management"},
        {"name": "🔗 Linking", "description": "Parent-student account linking with invite codes"},
        {"name": "🎓 Onboarding", "description": "Student first-login questionnaire"},
        {"name": "📜 Consent", "description": "Age gate, policy consent, and guardian approval"},
        {"name": "⚙️ Admin", "description": "Kio platform administration"},
        {"name": "🏥 Health", "description": "System health checks"},
    ],
)

# Middleware. Starlette runs these bottom-up, so the request-id layer is added
# last and therefore runs first -- every log line and error response below it
# already has an id to quote.
app.add_middleware(SecurityHeadersMiddleware)

# CORS. The origin list is explicit in every environment; config.py refuses a
# wildcard outright (credentials are sent) and refuses loopback origins in
# production. Expose the request id so a browser client can read it back and
# show a reference when something fails.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)

if settings.ALLOWED_HOSTS:
    # Blocks Host-header spoofing, which otherwise turns any absolute URL the
    # app builds -- password-reset links above all -- into an attacker's domain.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

if settings.FORCE_HTTPS:
    from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(RequestContextMiddleware)

_SENTRY_ENABLED = init_sentry()


# -------------------------------------------------------------------
# Exception handling
#
# Three rules: an expected error keeps its status and message, an unexpected
# one never reaches the client as a stack trace, and nothing is swallowed.
# -------------------------------------------------------------------


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Deliberate errors (404, 403, 409...) pass through with their own detail."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": get_request_id()},
        headers={REQUEST_ID_HEADER: get_request_id()},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Malformed input. Returned as-is minus the offending values.

    Pydantic includes the rejected input in each error, which for this app can
    be a password or a message to Comrade; the field path and reason are what
    a caller needs to fix the request.
    """
    errors = [
        {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors, "request_id": get_request_id()},
        headers={REQUEST_ID_HEADER: get_request_id()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Anything unforeseen: log it in full, tell the client almost nothing.

    Without this FastAPI re-raises, and with DEBUG=true a traceback -- file
    paths, library versions, sometimes query values -- is rendered straight to
    the browser. The client gets a request id instead, which is the one piece
    of internal state that is safe to share and the only one that helps.
    """
    logger.exception(
        "Unhandled exception method=%s path=%s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Something went wrong. Please try again.",
            "request_id": get_request_id(),
        },
        headers={REQUEST_ID_HEADER: get_request_id()},
    )

# Import and register routers
from app.auth.router import router as auth_router  # noqa: E402
from app.users.router import router as users_router  # noqa: E402
from app.conversations.router import router as conversations_router  # noqa: E402
from app.memory.router import router as memory_router  # noqa: E402
from app.wellness.router import router as wellness_router  # noqa: E402
from app.risk.router import router as risk_router  # noqa: E402
from app.parents.router import router as parents_router  # noqa: E402
from app.counselors.router import router as counselors_router  # noqa: E402
from app.analytics.router import router as analytics_router  # noqa: E402
from app.notifications.router import router as notifications_router  # noqa: E402
from app.subscriptions.router import router as subscriptions_router  # noqa: E402
from app.admin.router import router as admin_router  # noqa: E402
from app.linking.router import router as linking_router  # noqa: E402
from app.onboarding.router import router as onboarding_router  # noqa: E402
from app.consent.router import router as consent_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["🔐 Auth"])
app.include_router(users_router, prefix="/users", tags=["👤 Users"])
app.include_router(conversations_router, prefix="/conversations", tags=["💬 Conversations"])
app.include_router(memory_router, prefix="/memory", tags=["🧠 Memory"])
app.include_router(wellness_router, prefix="/wellness", tags=["💚 Wellness"])
app.include_router(risk_router, prefix="/risk", tags=["⚠️ Risk"])
app.include_router(parents_router, prefix="/parents", tags=["👨‍👩‍👧 Parents"])
app.include_router(counselors_router, prefix="/counselors", tags=["🩺 Counselors"])
app.include_router(analytics_router, prefix="/analytics", tags=["📊 Analytics"])
app.include_router(notifications_router, prefix="/notifications", tags=["🔔 Notifications"])
app.include_router(subscriptions_router, prefix="/subscriptions", tags=["💳 Subscriptions"])
app.include_router(admin_router, prefix="/admin", tags=["⚙️ Admin"])
app.include_router(linking_router, prefix="/linking", tags=["🔗 Linking"])
app.include_router(onboarding_router, prefix="/onboarding", tags=["🎓 Onboarding"])
app.include_router(consent_router, prefix="/consent", tags=["📜 Consent"])



# Health Check Endpoints


@app.get("/health", tags=["🏥 Health"])
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health/db", tags=["🏥 Health"])
async def db_health_check():
    """
    Database connectivity check.

    Returns 503 when the database is unreachable. It previously returned 200
    with an "unhealthy" body, which meant every orchestrator -- Docker's
    HEALTHCHECK, Render, a load balancer -- read it as passing and kept
    routing traffic to an instance that could not serve a single request.

    The failure body names no driver, host, or credential: the exception text
    from a connection failure routinely contains the DSN. Operators get the
    detail from the logs, which are not public.
    """
    from sqlalchemy import text
    from database.session import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"},
        )
