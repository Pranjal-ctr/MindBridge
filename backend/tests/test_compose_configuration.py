"""
docker-compose must actually deliver what .env.docker.example documents.

Compose injects only the keys named in a service's `environment` block, and a
Dockerfile only receives a build arg it declares with ARG. Both are silent when
they do not match: a value set in `.env` simply never arrives, and nothing logs
that it was dropped.

That is not hypothetical. `ALLOWED_HOSTS`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`
and `VITE_SENTRY_DSN` were added to the template while the compose file went on
listing the keys it already had. The consequences would have been found only in
a deployment: with `ENVIRONMENT=production` the API refuses to start without
`ALLOWED_HOSTS`, so the operator would have seen their own `.env` setting
apparently ignored; and Sentry would have stayed dark with a DSN configured.

These are static checks against the YAML rather than a container run, because
the failure is a wiring mismatch between three files and does not need Docker
to demonstrate.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_TEMPLATE = REPO_ROOT / ".env.docker.example"
WEB_DOCKERFILE = REPO_ROOT / "Dockerfile"

#: Backend settings that must reach the API container.
REQUIRED_API_ENV = ("ALLOWED_HOSTS", "SENTRY_DSN", "SENTRY_ENVIRONMENT")

#: Build-time values, which reach the bundle only as build args.
REQUIRED_WEB_BUILD_ARGS = ("VITE_SENTRY_DSN",)

#: Supplied to the container by other means, so their absence from the api
#: service's environment is correct rather than a gap:
#:   DATABASE_URL  assembled from POSTGRES_* by the compose file itself
#:   GEMINI_MODEL  deprecated alias, read nowhere on the request path
SUPPLIED_BY_OTHER_MEANS = {"DATABASE_URL", "GEMINI_MODEL"}

#: Documented in .env.docker.example, read by app/config.py, and NOT passed
#: through by compose today.
#:
#: This is the same defect as the one above, found by the general check while
#: fixing it, and left alone deliberately: the change that added these was
#: scoped to the four values the release review named, and widening it here
#: would have meant editing the AI configuration block without review.
#:
#: The practical effect is that a compose operator cannot change the provider,
#: model or guardrail ceilings from .env -- they silently get the code
#: defaults, which are the same values the template shows. Render is
#: unaffected; it sets what it needs explicitly.
#:
#: Wire them and delete them from here; the test below fails if this list ever
#: names something that is actually wired.
KNOWN_UNWIRED = {
    "OPENAI_API_KEY",
    "AI_PRIMARY_PROVIDER",
    "AI_PRIMARY_MODEL",
    "AI_FALLBACK_PROVIDER",
    "AI_FALLBACK_MODEL",
    "AI_FALLBACK_ENABLED",
    "AI_REQUEST_TIMEOUT_SECONDS",
    "AI_MAX_OUTPUT_TOKENS_CEILING",
    "AI_MAX_INPUT_CHARS",
    "AI_USER_REQUESTS_PER_MINUTE",
    "AI_FEATURE_REQUESTS_PER_MINUTE",
    "AI_GLOBAL_REQUESTS_PER_MINUTE",
    "AI_MAX_CONCURRENT_PER_USER",
    "AI_DAILY_TOKEN_CEILING",
    "AI_MONTHLY_TOKEN_CEILING",
    "AI_CIRCUIT_FAILURE_THRESHOLD",
    "AI_CIRCUIT_COOLDOWN_SECONDS",
}


@pytest.fixture(scope="module")
def compose() -> dict:
    if not COMPOSE_FILE.exists():  # pragma: no cover - repo layout guard
        pytest.skip(f"{COMPOSE_FILE} not found")
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def env_template_keys() -> set[str]:
    keys = set()
    for line in ENV_TEMPLATE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def _api_environment(compose: dict) -> dict:
    return compose["services"]["api"]["environment"]


def _web_build_args(compose: dict) -> dict:
    return compose["services"]["web"]["build"]["args"]


class TestComposeDeliversDocumentedValues:
    @pytest.mark.parametrize("key", REQUIRED_API_ENV)
    def test_api_container_receives(self, compose, key):
        assert key in _api_environment(compose), (
            f"{key} is documented in .env.docker.example but not listed in the "
            "api service's environment, so compose would never pass it."
        )

    @pytest.mark.parametrize("key", REQUIRED_API_ENV)
    def test_the_value_is_taken_from_the_environment(self, compose, key):
        """A hardcoded value would ignore .env just as thoroughly as omission."""
        assert f"${{{key}" in str(_api_environment(compose)[key])

    @pytest.mark.parametrize("key", REQUIRED_WEB_BUILD_ARGS)
    def test_web_image_receives_build_arg(self, compose, key):
        args = _web_build_args(compose)
        assert key in args, (
            f"{key} is a VITE_* value: it is compiled into the bundle, so it "
            "must be a build arg, not a runtime environment variable."
        )
        assert f"${{{key}" in str(args[key])

    @pytest.mark.parametrize("key", REQUIRED_WEB_BUILD_ARGS)
    def test_the_dockerfile_declares_the_build_arg(self, key):
        """
        Compose passing a build arg the Dockerfile does not declare is a warning
        and a dropped value, which looks identical to it working.
        """
        assert f"ARG {key}" in WEB_DOCKERFILE.read_text(encoding="utf-8")

    def test_optional_values_default_to_empty_rather_than_failing(self, compose):
        """
        An unset DSN disables reporting; it is a working configuration, so it
        must not use the `:?` form that makes compose refuse to start.
        """
        for key in ("SENTRY_DSN", "SENTRY_ENVIRONMENT"):
            assert ":?" not in str(_api_environment(compose)[key])

    def test_no_newly_documented_backend_value_is_silently_dropped(
        self, compose, env_template_keys
    ):
        """
        The general form of the defect, so the next variable added to the
        template cannot repeat it.

        Only keys the backend actually reads are considered; the template also
        carries compose-level and build-time values that legitimately do not
        belong in the api service's environment.
        """
        from app.config import Settings

        api_env = set(_api_environment(compose))
        documented_backend_keys = {
            key
            for key in env_template_keys & set(Settings.model_fields)
            # One-off input to `python -m database.bootstrap`, deliberately not
            # a standing service variable.
            if not key.startswith("BOOTSTRAP_")
        } - SUPPLIED_BY_OTHER_MEANS

        missing = sorted(documented_backend_keys - api_env - KNOWN_UNWIRED)
        assert not missing, (
            "documented in .env.docker.example and read by app/config.py, but "
            f"never passed to the api container: {missing}"
        )

    def test_the_known_gap_list_does_not_outlive_the_gap(self, compose):
        """
        Keeps KNOWN_UNWIRED honest: once a key is wired, it must leave the
        list, or the list would start hiding regressions instead of recording
        a decision.
        """
        api_env = set(_api_environment(compose))
        stale = sorted(KNOWN_UNWIRED & api_env)
        assert not stale, (
            f"these are wired now and should be removed from KNOWN_UNWIRED: {stale}"
        )
