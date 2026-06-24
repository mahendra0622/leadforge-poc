"""
FintelliPro — Application Configuration
All settings loaded from environment variables
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me-in-production-please-use-32-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql://fintellipro:fintellipro_dev@localhost:5432/fintellipro"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # External APIs
    APOLLO_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Gmail OAuth
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/auth/gmail/callback"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
