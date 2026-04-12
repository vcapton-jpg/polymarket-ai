"""Core configuration settings for Signal platform."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@db:5432/signal",
        description="Async PostgreSQL connection URL",
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@db:5432/signal",
        description="Sync PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL for Celery",
    )

    # OpenAI
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for LLM operations",
    )

    # Telegram
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token for notifications",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat ID for notifications",
    )

    # World News API
    worldnews_api_key: Optional[str] = Field(
        default=None,
        description="World News API key",
    )

    # Environment
    env: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )

    # Signal Configuration
    signal_score_threshold: int = Field(
        default=60,
        description="Minimum score to generate a signal",
    )
    llm_cost_alert_eur: float = Field(
        default=30.0,
        description="Alert threshold for daily LLM costs in EUR",
    )
    tier1_lag_alert_seconds: int = Field(
        default=180,
        description="Alert threshold for Tier 1 source lag",
    )

    # Retrieval Configuration
    top_k_markets: int = Field(
        default=10,
        description="Number of top markets to retrieve per event",
    )

    # Clustering Configuration
    clustering_cosine_threshold: float = Field(
        default=0.82,
        description="Cosine similarity threshold for clustering",
    )
    clustering_time_window_minutes: int = Field(
        default=60,
        description="Time window in minutes for clustering",
    )

    # Application
    app_name: str = "Signal"
    app_version: str = "0.1.0"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()