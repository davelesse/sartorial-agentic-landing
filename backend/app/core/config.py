"""
Sartorial Agentic — Application Configuration
Loaded from environment variables via Pydantic Settings.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = ...
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # JWT
    JWT_SECRET: str = ...
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sartorial:password@localhost:5432/sartorial_agentic"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLIC_KEY: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Resend
    RESEND_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Celery
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_TASK_TIME_LIMIT: int = 3600
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300

    # Next.js
    NEXT_TELEMETRY_DISABLED: str = "1"

    # Backups
    BACKUP_RETENTION_DAYS: int = 30
    S3_BACKUP_BUCKET: str = ""

    # Sentry (optionnel)
    SENTRY_DSN: str = ""

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production":
            missing = []
            if not self.STRIPE_SECRET_KEY:
                missing.append("STRIPE_SECRET_KEY")
            if not self.STRIPE_WEBHOOK_SECRET:
                missing.append("STRIPE_WEBHOOK_SECRET")
            if not self.ANTHROPIC_API_KEY:
                missing.append("ANTHROPIC_API_KEY")
            if not self.RESEND_API_KEY:
                missing.append("RESEND_API_KEY")
            if missing:
                raise ValueError(
                    f"Variables d'environnement manquantes en production: {', '.join(missing)}"
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
