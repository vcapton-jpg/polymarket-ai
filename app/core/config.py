"""Core configuration — all settings from Blueprint V4."""

from functools import lru_cache

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
    openai_api_key: str | None = Field(default=None)
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_llm_model: str = Field(default="gpt-4o-mini")
    openai_impact_model: str = Field(default="gpt-4o")

    # ── World News API ────────────────────────────────────────────────────
    worldnews_api_key: str | None = Field(default=None)
    worldnews_poll_interval_seconds: int = Field(default=120)

    # ── Telegram (kept for optional alerts) ───────────────────────────────
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)

    # ── Auth / Security ──────────────────────────────────────────────────
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_days: int = Field(default=7)
    # Google Sign-In (OAuth 2.0 Web client ID — same value as VITE_GOOGLE_CLIENT_ID on frontend)
    google_client_id: str | None = Field(default=None)
    signal_api_key: str | None = Field(default=None)
    # Comma-separated list of emails allowed to hit /api/admin/* endpoints.
    # Not a role column — temporary until we need >1 permission tier.
    admin_emails: str = Field(default="")

    # ── Push Notifications (VAPID) ────────────────────────────────────
    vapid_private_key: str | None = Field(default=None)
    vapid_public_key: str | None = Field(default=None)
    vapid_email: str = Field(default="hello@getforesight.io")

    # ── Polymarket Builder ─────────────────────────────────────────────
    builder_api_key: str | None = Field(default=None)
    builder_api_secret: str | None = Field(default=None)
    builder_api_passphrase: str | None = Field(default=None)
    builder_private_key: str | None = Field(default=None)
    polygon_chain_id: int = Field(default=137)

    # Polymarket Builder attribution code (bytes32 hex from polymarket.com/settings?tab=builder)
    polymarket_builder_code: str = Field(
        default="0x0000000000000000000000000000000000000000000000000000000000000000",
        description="Builder attribution code — 66-char hex bytes32",
    )

    # Polygon RPC for Safe deployment
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon mainnet JSON-RPC endpoint",
    )

    # Gnosis Safe contract addresses on Polygon mainnet
    gnosis_safe_proxy_factory: str = Field(
        default="0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2",
        description="GnosisSafeProxyFactory address on Polygon",
    )
    gnosis_safe_singleton: str = Field(
        default="0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552",
        description="GnosisSafe singleton (master copy) on Polygon",
    )

    # ── Stripe ─────────────────────────────────────────────────────────
    stripe_secret_key: str | None = Field(default=None)
    stripe_webhook_secret: str | None = Field(default=None)
    stripe_price_pro: str | None = Field(default=None)
    stripe_price_trader: str | None = Field(default=None)

    # ── Environment ───────────────────────────────────────────────────────
    env: str = Field(default="development")
    app_base_url: str = Field(default="https://getforesight.io")
    # Comma-separated list of additional CORS origins, e.g. for staging or
    # an apex/www split. Production is always [app_base_url] + this list.
    # Audit follow-up: replaces the prior `allow_origins=["*"]` in main.py.
    cors_extra_origins: str = Field(default="")

    # ── Ingestion intervals (seconds) ─────────────────────────────────────
    rss_poll_interval_seconds: int = Field(default=90)
    x_poll_interval_seconds: int = Field(default=60)
    market_refresh_interval_seconds: int = Field(default=900)
    market_percentile_interval_seconds: int = Field(default=86400)

    # ── Signal thresholds ─────────────────────────────────────────────────
    # Raised from 55 → 65 (winrate optimization Phase A, 2026-04-27).
    # Performance audit on 130 signals over 3 days showed the 75+ band
    # had +19.5 % mean signed move at T+1h while the 60-74 band had
    # -14.5 %. Initial pin at 75 was too restrictive in practice — kills
    # too much volume and the 65-74 sub-band still has option value once
    # the upcoming freshness gate filters out stale-news signals (which
    # are likely the bulk of 65-74 misfires). Promote to 75 only after
    # the freshness fix has shipped and the 65-74 winrate is re-measured.
    # Below-threshold signals are still PERSISTED (logged with
    # `_below_threshold=True`) so the measurement layer keeps collecting
    # data — only user-facing emission and "best signal of event" selection
    # are gated by this value.
    signal_score_threshold: int = Field(default=65)
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

    # ── Sourcing (chantier #2) ────────────────────────────────────────
    sourcing_alpha: float = Field(
        default=0.7,
        description="Weight of cosine similarity in the composite article score.",
    )
    sourcing_beta: float = Field(
        default=0.3,
        description="Weight of recency decay in the composite article score.",
    )
    sourcing_recency_tau_hours: float = Field(
        default=24.0,
        description="Exponential-decay time constant (hours) for article recency.",
    )
    sourcing_pool_window_hours: int = Field(
        default=72,
        description="Hard cutoff for the candidate article pool, in hours.",
    )
    sourcing_top_k: int = Field(
        default=5,
        description="Number of articles re-ranked and fed to the shadow reasoning call.",
    )
    sourcing_shadow_enabled: bool = Field(
        default=True,
        description="Kill switch for the signal_v2_reranked Celery task.",
    )

    # ── Eval harness (chantier #3) ────────────────────────────────────
    llm_judge_max_usd: float = Field(
        default=10.0,
        description="Hard cap on spend per LLM-judge eval run (GPT-4o-mini).",
    )
    embeddings_variant_news: str = Field(
        default="v1",
        description="Active embedding variant for news_clean. 'v1' or 'v2'.",
    )
    embeddings_variant_market: str = Field(
        default="v1",
        description="Active embedding variant for markets. 'v1' or 'v2'.",
    )
    embeddings_variant_event: str = Field(
        default="v1",
        description="Active embedding variant for events. 'v1' or 'v2'.",
    )

    # ── Ranking v2 (chantier #4) ──────────────────────────────────────
    ranking_variant_event_to_market: str = Field(
        default="v1",
        description="Active ranking variant for event→market retrieval. 'v1' (current) or 'v2' (tuned).",
    )
    ranking_shadow_enabled: bool = Field(
        default=True,
        description="Kill switch for the event_market_ranking_shadow Celery task.",
    )
    ranking_v2_rrf_k: int = Field(
        default=60,
        description="RRF k-constant for hybrid_search_v2.",
    )
    ranking_v2_w_entity: float = Field(
        default=0.5,
        description="Weight of the entity-match bonus in hybrid_search_v2.",
    )
    ranking_v2_w_date: float = Field(
        default=0.0,
        description="Weight of the date-proximity bonus in hybrid_search_v2. Defaults to 0 → v2 ≡ v1.",
    )
    ranking_v2_w_bucket: float = Field(
        default=0.0,
        description="Weight of the bucket-match bonus in hybrid_search_v2. Defaults to 0 → v2 ≡ v1.",
    )
    ranking_v2_tau_days: float = Field(
        default=14.0,
        description="Exponential-decay time constant (days) for date-proximity boost.",
    )
    ranking_v2_min_sim: float = Field(
        default=0.45,
        description="Minimum cosine similarity threshold for v2 vector retrieval.",
    )

    # ── chantier #5: heuristic score — validation & calibration ──────────
    heuristic_shadow_enabled: bool = False
    heuristic_w_freshness: float = 0.15
    heuristic_w_source: float = 0.10
    heuristic_w_confirmation: float = 0.15
    heuristic_w_llm: float = 0.60
    heuristic_w_liquidity: float = 0.40
    heuristic_w_spread: float = 0.35
    heuristic_w_time_to_resolution: float = 0.25
    heuristic_strength_weight: float = 0.75
    heuristic_trade_weight: float = 0.25

    # ── Application ───────────────────────────────────────────────────────
    app_name: str = "Foresight"
    app_version: str = "1.0.0"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
