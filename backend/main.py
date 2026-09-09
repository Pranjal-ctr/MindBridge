"""
Kio API — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


_configure_logging()


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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Database connectivity check."""
    from sqlalchemy import text
    from database.session import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
