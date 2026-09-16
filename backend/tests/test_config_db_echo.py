"""
DB_ECHO must be impossible to enable in production.

Why this has its own file: SQLAlchemy's echo mode logs every statement *and its
bound parameters*. In most products that is a noisy convenience. In Kio the
bound parameters of a routine INSERT are a student's message to Comrade, a
counselor's session note, or a crisis assessment -- so `DB_ECHO=true` in
production would copy exactly the content the product exists to protect into
the host's log drain.

The guard is a startup refusal rather than a silent override, matching the
JWT-secret and CORS guards: an operator who set the flag wanted to see
something, and ignoring it quietly would leave them debugging why their change
had no effect.

The last test is the important one. It asserts that `echo` is the *only* route
to statement logging -- SQLAlchemy pins its own logger below the root, so
raising the application log level cannot produce it. If a future change to
logging setup ever breaks that assumption, this fails rather than shipping.
"""

import logging
import sys

import pytest
from sqlalchemy import create_engine, text

from app.config import Settings


def _settings(**overrides) -> Settings:
    """Build a Settings independent of the developer's real .env file.

    `_env_file=None` matters: without it pydantic-settings reads backend/.env,
    and this machine's .env sets DB_ECHO=true -- so the "valid" cases would
    pass or fail according to local configuration rather than the argument
    under test.
    """
    base = dict(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-production-secret-value",
        CORS_ORIGINS=["https://app.kio.example"],
        GEMINI_API_KEY="a-key",
        DB_ECHO=False,
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


class TestProductionRefusesEcho:
    def test_production_with_db_echo_true_is_rejected(self):
        with pytest.raises(ValueError) as exc:
            _settings(DB_ECHO=True)

        message = str(exc.value)
        # The message must name the variable and say why, so the operator who
        # hits this at deploy time does not have to go source-diving.
        assert "DB_ECHO" in message
        assert "production" in message

    def test_rejection_is_not_a_silent_override(self):
        """The value is refused, never quietly forced to false.

        A silent override would leave an operator believing echo was on and
        wondering why no SQL appeared -- and would mean production behaviour
        differed from the configuration on file.
        """
        with pytest.raises(ValueError):
            _settings(DB_ECHO=True)

    def test_production_with_db_echo_false_is_valid(self):
        settings = _settings(DB_ECHO=False)
        assert settings.is_production is True
        assert settings.DB_ECHO is False

    def test_production_default_is_false(self):
        """Nothing has to be set for production to be safe."""
        settings = _settings()
        assert settings.DB_ECHO is False


class TestNonProductionKeepsEcho:
    @pytest.mark.parametrize("environment", ["development", "test", "testing", "staging"])
    def test_db_echo_remains_supported_outside_production(self, environment):
        """Echo is a genuinely useful local tool and stays available.

        Note `staging` is included: `is_production` is an exact match on
        "production", so staging is treated as non-production here exactly as
        it is by every other guard in config.py. That is the pre-existing
        definition, not a new decision.
        """
        settings = Settings(
            _env_file=None,
            ENVIRONMENT=environment,
            DB_ECHO=True,
            GEMINI_API_KEY="a-key",
        )
        assert settings.DB_ECHO is True
        assert settings.is_production is False


class TestEchoIsTheOnlyRouteToParameterLogging:
    """Guards the assumption the production check relies on.

    The guard above only protects production if `echo` is the sole way to get
    statement logging. SQLAlchemy pins its own `sqlalchemy` logger to WARNING
    at import time, so it does not inherit the application's root level. These
    tests assert that directly, against SQLAlchemy rather than against Kio, so
    an upgrade that changed the behaviour would surface here.
    """

    def test_sqlalchemy_pins_its_own_logger_below_the_root(self):
        root_level_before = logging.getLogger().level
        try:
            logging.getLogger().setLevel(logging.DEBUG)
            effective = logging.getLogger("sqlalchemy.engine.Engine").getEffectiveLevel()
            # Not DEBUG/INFO: SQLAlchemy set an explicit level on `sqlalchemy`,
            # so the root logger's level does not reach it.
            assert effective >= logging.WARNING
        finally:
            logging.getLogger().setLevel(root_level_before)

    def test_raising_the_root_log_level_does_not_log_parameters(self, capsys):
        """DEBUG=true / a verbose LOG_LEVEL must not leak bound parameters."""
        secret = "PRIVATE-STUDENT-MESSAGE-TEXT"
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        try:
            root.handlers = [logging.StreamHandler(sys.stdout)]
            root.setLevel(logging.DEBUG)

            engine = create_engine("sqlite://", echo=False)
            with engine.connect() as conn:
                conn.execute(text("SELECT :v AS v"), {"v": secret})

            assert secret not in capsys.readouterr().out
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)

    def test_echo_true_really_does_log_the_parameter_value(self, capsys):
        """The premise of the guard, demonstrated rather than assumed.

        If this ever stops being true the guard is merely redundant, not
        wrong -- but it is worth knowing which.
        """
        secret = "PRIVATE-STUDENT-MESSAGE-TEXT"
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        try:
            root.handlers = [logging.StreamHandler(sys.stdout)]
            root.setLevel(logging.INFO)

            engine = create_engine("sqlite://", echo=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT :v AS v"), {"v": secret})

            assert secret in capsys.readouterr().out
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)
            # echo=True sets an explicit level on the engine logger; restore it
            # so this test cannot make a later one noisy.
            logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.NOTSET)

    def test_engine_is_configured_only_from_db_echo(self):
        """No second echo knob (echo_pool, an explicit logger level) is set."""
        import inspect

        import database.session as session_module

        source = inspect.getsource(session_module)
        assert "echo=app_config.settings.DB_ECHO" in source or "echo=settings.DB_ECHO" in source
        assert "echo_pool" not in source
        assert "sqlalchemy.engine" not in source
