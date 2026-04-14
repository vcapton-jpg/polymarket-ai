"""Core configuration — all settings from Blueprint V4."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@db:5432/signal",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/signal",
    )

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://redis:6379/0")

    # ── OpenAI ────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(default=None)
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_llm_model: str = Field(default="gpt-4o-mini")
    openai_impact_model: str = Field(default="gpt-4o")

    # ── World News API ────────────────────────────────────────────────────
    worldnews_api_key: Optional[str] = Field(default=None)
    worldnews_poll_interval_seconds: int = Field(default=120)

    # ── Telegram (kept for optional alerts) ───────────────────────────────
    telegram_bot_token: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)

    # ── Auth / Security ──────────────────────────────────────────────────
    signal_api_key: Optional[str] = Field(default=None)

    # ── Push Notifications (VAPID) ────────────────────────────────────
    vapid_private_key: Optional[str] = Field(default=None)
    vapid_public_key: Optional[str] = Field(default=None)
    vapid_email: str = Field(default="admin@signal.app")

    # ── Polymarket Builder ─────────────────────────────────────────────
    builder_api_key: Optional[str] = Field(default=None)
    builder_api_secret: Optional[str] = Field(default=None)
    builder_api_passphrase: Optional[str] = Field(default=None)
    builder_private_key: Optional[str] = Field(default=None)
    polygon_chain_id: int = Field(default=137)

    # ── Stripe ─────────────────────────────────────────────────────────
    stripe_secret_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)
    stripe_price_pro: Optional[str] = Field(default=None)
    stripe_price_enterprise: Optional[str] = Field(default=None)

    # ── Environment ───────────────────────────────────────────────────────
    env: str = Field(default="development")

    # ── Ingestion intervals (seconds) ─────────────────────────────────────
    rss_poll_interval_seconds: int = Field(default=90)
    x_poll_interval_seconds: int = Field(default=60)
    market_refresh_interval_seconds: int = Field(default=900)
    market_percentile_interval_seconds: int = Field(default=86400)

    # ── Signal thresholds ─────────────────────────────────────────────────
    signal_score_threshold: int = Field(default=55)
    hard_exclusion_spread: float = Field(default=0.15)
    hard_exclusion_ambiguity: float = Field(default=0.80)
    hard_exclusion_min_specificity: float = Field(default=0.4)
    # BUY_YES / BUY_NO only if YES implied prob is in this band.
    # Outside: the market is essentially resolved — no edge, confusing UX.
    signal_tradeable_yes_min: float = Field(default=0.05)
    signal_tradeable_yes_max: float = Field(default=0.95)
    # Minimum cosine similarity between event embedding and market embedding.
    # Below this, the semantic link is too weak — the match is generic/tangential.
    signal_min_cosine_score: float = Field(default=0.52)

    # ── LLM cost guardrails ───────────────────────────────────────────────
    llm_cost_alert_usd: float = Field(default=30.0)

    # ── Ingestion health ──────────────────────────────────────────────────
    tier1_lag_alert_seconds: int = Field(default=180)

    # ── Retrieval ─────────────────────────────────────────────────────────
    top_k_markets: int = Field(default=10)
    rrf_k: int = Field(default=60)
    llm_impact_max_candidates: int = Field(default=3)

    # ── Clustering ────────────────────────────────────────────────────────
    clustering_cosine_threshold: float = Field(default=0.75)
    clustering_time_window_minutes: int = Field(default=120)
    clustering_simhash_threshold: float = Field(default=0.15)
    min_articles_per_event: int = Field(default=1)

    # ── Processing / latency ────────────────────────────────────────────────
    min_word_count: int = Field(default=50)
    min_title_words: int = Field(default=5)
    article_freshness_hours: int = Field(default=12)
    embedding_batch_size: int = Field(default=100)
    rss_max_article_age_hours: float = Field(default=24.0)
    # Beat intervals — backfill only; fast-path handles real-time flow
    embedding_batch_interval_seconds: int = Field(default=120)
    build_events_interval_seconds: int = Field(default=300)
    signal_event_max_age_hours: float = Field(default=6.0)
    signal_dedupe_window_hours: float = Field(default=72.0)

    # ── Event LLM (cluster ≥ min_articles) ───────────────────────────────
    event_llm_summarize: bool = Field(default=True)

    # ── 𝕏-scraper inbox (https://fmoncomble.github.io/X-scraper/) ───────
    x_scraper_inbox_dir: str = Field(default="data/x_scraper_inbox")
    x_scraper_processed_dir: str = Field(default="data/x_scraper_processed")
    x_scraper_inbox_interval_seconds: int = Field(default=120)

    # ── Application ───────────────────────────────────────────────────────
    app_name: str = "Signal"
    app_version: str = "0.1.0"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
