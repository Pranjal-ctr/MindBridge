"""
Production hardening: error handling, health, docs exposure, headers, CORS.

These assert the behaviour of the deployment rather than of a feature. Most of
them exist because the failure they describe is silent: a health check that
lies passes every orchestrator, docs left on in production advertise the whole
API, and a leaked traceback looks like an ordinary error page to everyone
except the person reading it.
"""

import importlib

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.observability import REQUEST_ID_HEADER, scrub_event


# -------------------------------------------------------------------
# Request correlation
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_response_carries_a_request_id(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER)


@pytest.mark.asyncio
async def test_a_client_supplied_request_id_is_propagated(client: AsyncClient):
    """So a browser trace and an API trace can be joined."""
    response = await client.get("/health", headers={REQUEST_ID_HEADER: "trace-abc123"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-abc123"


@pytest.mark.asyncio
async def test_a_malicious_request_id_is_replaced(client: AsyncClient):
    """
    Header values reach the log file. A newline would let a caller forge log
    lines, so anything that is not a short opaque token is discarded.
    """
    forged = "abc\r\nWARNING [x] fake log line"
    response = await client.get("/health", headers={REQUEST_ID_HEADER: forged})
    returned = response.headers[REQUEST_ID_HEADER]
    assert returned != forged
    assert "\n" not in returned and "\r" not in returned
    assert len(returned) <= 64

    too_long = "a" * 200
    response = await client.get("/health", headers={REQUEST_ID_HEADER: too_long})
    assert response.headers[REQUEST_ID_HEADER] != too_long


# -------------------------------------------------------------------
# Exception handling
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_expected_error_keeps_its_status_and_message(client: AsyncClient):
    """Deliberate HTTPExceptions must not be flattened into generic 500s."""
    response = await client.get("/counselors/schedules")
    assert response.status_code in (401, 403)
    assert "detail" in response.json()
    assert response.json()["request_id"]


@pytest.mark.asyncio
async def test_a_validation_error_reports_fields_without_echoing_values(
    client: AsyncClient,
):
    """
    Pydantic includes the rejected input by default. For this app that can be
    a password, so the handler strips it and keeps the field path and reason.
    """
    secret = "hunter2-this-should-not-come-back"
    response = await client.post(
        "/auth/login", json={"email": "not-an-email", "password": secret}
    )
    assert response.status_code == 422
    body = response.text
    assert secret not in body
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_an_unhandled_exception_returns_a_safe_body(client: AsyncClient):
    """
    The client gets a generic message plus a request id -- never a traceback,
    file path, or exception text.
    """
    from main import app

    @app.get("/__boom__")
    async def _boom():
        raise RuntimeError("secret internal detail: postgres://user:pw@host/db")

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/__boom__")

        assert response.status_code == 500
        body = response.text
        assert "secret internal detail" not in body
        assert "postgres://" not in body
        assert "Traceback" not in body
        assert "RuntimeError" not in body
        payload = response.json()
        assert payload["detail"] == "Something went wrong. Please try again."
        assert payload["request_id"]
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__boom__"
        ]


# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_is_cheap_and_says_nothing_sensitive(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_db_health_reports_healthy_when_the_database_is_up(client: AsyncClient):
    response = await client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


@pytest.mark.asyncio
async def test_db_health_returns_503_and_hides_the_dsn_when_the_database_is_down(
    client: AsyncClient, monkeypatch
):
    """
    The regression that matters. This used to return 200 with an "unhealthy"
    body, so Docker, Render and any load balancer read it as passing and kept
    sending traffic to an instance that could not answer. It also returned
    str(exception), which for a connection failure contains the DSN.
    """
    import database.session as session_module

    class ExplodingSession:
        async def __aenter__(self):
            raise OSError(
                "could not connect to server: postgresql://kio:sup3rsecret@db:5432/kio"
            )

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(session_module, "async_session_factory", lambda: ExplodingSession())

    response = await client.get("/health/db")
    assert response.status_code == 503
    body = response.text
    assert "sup3rsecret" not in body
    assert "postgresql://" not in body
    assert response.json() == {"status": "unhealthy", "database": "disconnected"}


# -------------------------------------------------------------------
# Docs exposure
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docs_are_available_outside_production(client: AsyncClient):
    for path in ("/docs", "/openapi.json"):
        assert (await client.get(path)).status_code == 200, path


def test_production_configuration_serves_no_docs(monkeypatch):
    """
    Rebuilds the app with ENVIRONMENT=production and asserts the routes are
    absent -- not merely unlinked. The schema enumerates every endpoint and
    field in the product; that is a map worth withholding.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-production-secret-value")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.kio.example"]')

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.settings.is_production is True

    import main as main_module

    try:
        importlib.reload(main_module)
        paths = {getattr(route, "path", None) for route in main_module.app.router.routes}
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths
        assert "/health" in paths, "health must survive; orchestrators need it"
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)
        importlib.reload(main_module)


# -------------------------------------------------------------------
# Security headers
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_are_present(client: AsyncClient):
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]


@pytest.mark.asyncio
async def test_hsts_is_not_sent_over_plain_http(client: AsyncClient):
    """
    Pinning a browser to https for localhost would break every other project
    on a developer's machine, and the header is meaningless over http anyway.
    """
    response = await client.get("/health")
    assert "Strict-Transport-Security" not in response.headers


# -------------------------------------------------------------------
# CORS configuration
# -------------------------------------------------------------------


def test_a_wildcard_origin_is_refused():
    """Credentials are sent, so browsers reject '*' -- fail loudly at boot."""
    with pytest.raises(Exception) as excinfo:
        Settings(CORS_ORIGINS=["*"], JWT_SECRET_KEY="x" * 32)
    assert "*" in str(excinfo.value)


def test_production_refuses_a_loopback_origin():
    with pytest.raises(Exception) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-real-production-secret",
            CORS_ORIGINS=["https://app.kio.example", "http://localhost:5173"],
        )
    assert "loopback" in str(excinfo.value).lower()


def test_production_accepts_real_origins():
    settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-production-secret",
        CORS_ORIGINS=["https://app.kio.example"],
    )
    assert settings.is_production is True


# -------------------------------------------------------------------
# Sentry scrubbing
# -------------------------------------------------------------------


def test_scrubbing_strips_bodies_tokens_and_identifiers():
    """
    An error report must say what broke, never what a student wrote or who
    they are. Bodies are dropped wholesale rather than filtered field by
    field, because a deny-list drifts out of step with the schemas.
    """
    event = {
        "request": {
            "url": "https://api.kio.example/auth/reset?token=super-secret-token",
            "query_string": "token=super-secret-token",
            "data": {"message": "I have been feeling hopeless lately"},
            "cookies": {"session": "abc"},
            "headers": {
                "Authorization": "Bearer eyJhbGciOi.reallylong.token",
                "Cookie": "session=abc",
                "User-Agent": "Mozilla/5.0",
            },
        },
        "user": {
            "id": "user-123",
            "email": "student@school.edu",
            "username": "sarah.johnson",
            "ip_address": "203.0.113.5",
        },
    }

    scrubbed = scrub_event(event, {})
    serialised = str(scrubbed)

    assert "hopeless" not in serialised
    assert "super-secret-token" not in serialised
    assert "eyJhbGciOi" not in serialised
    assert "student@school.edu" not in serialised
    assert "sarah.johnson" not in serialised
    assert "203.0.113.5" not in serialised

    # Still useful: the route and the user id survive.
    assert scrubbed["request"]["url"].endswith("/auth/reset")
    assert scrubbed["user"]["id"] == "user-123"
    assert scrubbed["request"]["headers"]["User-Agent"] == "Mozilla/5.0"


# -------------------------------------------------------------------
# Production seeding
# -------------------------------------------------------------------


def test_seeding_is_allowed_outside_production(monkeypatch):
    from database.seed import assert_seeding_allowed

    for environment in ("development", "test", "staging"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        assert_seeding_allowed()  # must not raise


def test_seeding_production_is_refused(monkeypatch):
    """
    The seed creates one account per role -- platform admin included --
    sharing a password printed in this repository. Running it against a live
    system hands an admin login to anyone who has read the source.
    """
    from database.seed import SeedRefused, assert_seeding_allowed

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("KIO_ALLOW_PRODUCTION_SEED", raising=False)

    with pytest.raises(SeedRefused) as excinfo:
        assert_seeding_allowed()
    assert "REFUSING" in str(excinfo.value)


def test_the_production_override_must_be_exact(monkeypatch):
    """A truthy value is not enough; the guard should be hard to trip by accident."""
    from database.seed import SeedRefused, assert_seeding_allowed

    monkeypatch.setenv("ENVIRONMENT", "production")
    for value in ("1", "true", "yes", "YES", ""):
        monkeypatch.setenv("KIO_ALLOW_PRODUCTION_SEED", value)
        with pytest.raises(SeedRefused):
            assert_seeding_allowed()

    monkeypatch.setenv("KIO_ALLOW_PRODUCTION_SEED", "i-understand")
    assert_seeding_allowed()  # must not raise
