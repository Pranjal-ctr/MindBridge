"""
MindBridge Application Configuration
Centralized settings via pydantic-settings with .env support.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    APP_NAME: str = "MindBridge API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "AI-Powered Student Wellness & Parenting Platform"
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
    JWT_SECRET_KEY: str = "mindbridge-dev-secret-key-change-in-production"
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

    # -------------------------------------------------------------------
    # Pagination
    # -------------------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
