"""
Kio Application Configuration
Centralized settings via pydantic-settings with .env support.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "mindbridge-dev-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------
    APP_NAME: str = "Kio API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Kio — AI Companion for Growth. Student wellness & parenting guidance platform."
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # -------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mindbridge"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # -------------------------------------------------------------------
    # JWT Authentication
    # -------------------------------------------------------------------
    JWT_SECRET_KEY: str = _DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # -------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 60

    # -------------------------------------------------------------------
    # AI / Gemini
    # -------------------------------------------------------------------
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AI_MAX_CONTEXT_MESSAGES: int = 20
    AI_SUMMARY_THRESHOLD: int = 20  # Hook trigger threshold
    AI_DEFAULT_MAX_RETRIES: int = 2  # Used when a feature has no DB route configured yet
    AI_DAILY_MESSAGE_LIMIT: int = 100  # Max chat AI calls per student per day (spend cap)

    # -------------------------------------------------------------------
    # Google OAuth (Sign in with Google) -- ID-token flow
    # -------------------------------------------------------------------
    GOOGLE_CLIENT_ID: str = ""       # Set to enable Google sign-in; blank = feature disabled
    GOOGLE_CLIENT_SECRET: str = ""   # Reserved for future server-side auth-code flows

    # -------------------------------------------------------------------
    # Email delivery (interface only for now -- see app/email/)
    # -------------------------------------------------------------------
    EMAIL_PROVIDER: str = "noop"  # noop | resend | sendgrid | ses | smtp (future)

    # -------------------------------------------------------------------
    # Pagination
    # -------------------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @model_validator(mode="after")
    def _forbid_dev_secret_in_production(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production" and self.JWT_SECRET_KEY == _DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong secret in production. "
                "Refusing to start with the development default."
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
