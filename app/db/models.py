"""SQLAlchemy models — aligned with Blueprint V4 schema."""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# sources_registry
# ---------------------------------------------------------------------------
class SourceRegistry(Base):
    __tablename__ = "sources_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rss")
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    news_items: Mapped[list["News"]] = relationship(
        "News", back_populates="source"
    )


# ---------------------------------------------------------------------------
# news  (raw articles — one row per URL)
# ---------------------------------------------------------------------------
class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    publish_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingestion_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ingestion_lag_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("sources_registry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[Optional["SourceRegistry"]] = relationship(
        "SourceRegistry", back_populates="news_items", lazy="selectin"
    )

    clean: Mapped[Optional["NewsClean"]] = relationship(
        back_populates="news", uselist=False, cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# news_clean  (processed articles)
# ---------------------------------------------------------------------------
class NewsClean(Base):
    __tablename__ = "news_clean"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    simhash: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bucket: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    embedding_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    news: Mapped["News"] = relationship(back_populates="clean")
    entities: Mapped[list["ArticleEntity"]] = relationship(
        back_populates="news_clean", cascade="all, delete-orphan"
    )
    event_links: Mapped[list["EventNewsLink"]] = relationship(
        back_populates="news_clean", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# article_entities
# ---------------------------------------------------------------------------
class ArticleEntity(Base):
    __tablename__ = "article_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clean_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_clean.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_value: Mapped[str] = mapped_column(Text, nullable=False)

    news_clean: Mapped["NewsClean"] = relationship(back_populates="entities")


# ---------------------------------------------------------------------------
# markets  (Polymarket — PK is condition_id text)
# ---------------------------------------------------------------------------
class Market(Base):
    __tablename__ = "markets"

    market_id: Mapped[str] = mapped_column(Text, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bucket: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepting_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    volume: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    best_bid: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    best_ask: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    spread: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    last_trade_price: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clob_token_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    liquidity_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    volume_24h_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    market_retrieval_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    candidates: Mapped[list["EventMarketCandidate"]] = relationship(
        back_populates="market", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="market", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# events_from_news
# ---------------------------------------------------------------------------
class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_title: Mapped[str] = mapped_column(Text, nullable=False)
    event_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_retrieval_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_entities: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bucket: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    articles_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    unique_sources_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    news_links: Mapped[list["EventNewsLink"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["EventMarketCandidate"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["EventMarketAnalysis"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    features: Mapped[list["EventMarketFeatures"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# event_news_links  (N-N: events <-> news_clean)
# ---------------------------------------------------------------------------
class EventNewsLink(Base):
    __tablename__ = "event_news_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    clean_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_clean.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(30), nullable=False, default="supporting"
    )
    key_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="news_links")
    news_clean: Mapped["NewsClean"] = relationship(back_populates="event_links")

    __table_args__ = (
        UniqueConstraint("event_id", "clean_id", name="uq_event_news_link"),
    )


# ---------------------------------------------------------------------------
# event_market_candidates  (top-K from hybrid search)
# ---------------------------------------------------------------------------
class EventMarketCandidate(Base):
    __tablename__ = "event_market_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    bm25_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cosine_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rrf_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="candidates")
    market: Mapped["Market"] = relationship(back_populates="candidates")

    __table_args__ = (
        UniqueConstraint("event_id", "market_id", name="uq_event_market_candidate"),
    )


# ---------------------------------------------------------------------------
# event_market_analysis  (LLM #2 output)
# ---------------------------------------------------------------------------
class EventMarketAnalysis(Base):
    __tablename__ = "event_market_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    impact_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    impact_strength: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    llm_confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    ambiguity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    specificity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    catalysts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    risks: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped["Event"] = relationship(back_populates="analyses")

    __table_args__ = (
        UniqueConstraint("event_id", "market_id", name="uq_event_market_analysis"),
    )


# ---------------------------------------------------------------------------
# event_market_features  (scoring input — heuristic + future LightGBM)
# ---------------------------------------------------------------------------
class EventMarketFeatures(Base):
    __tablename__ = "event_market_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    # LLM variables
    impact_strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambiguity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Backend variables
    freshness_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confirmation_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_penalty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_resolution_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # ML label (filled post-resolution)
    outcome_label: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="features")

    __table_args__ = (
        UniqueConstraint("event_id", "market_id", name="uq_event_market_features"),
    )


# ---------------------------------------------------------------------------
# llm_cost_log
# ---------------------------------------------------------------------------
class LLMCostLog(Base):
    __tablename__ = "llm_cost_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# signals  (final output)
# ---------------------------------------------------------------------------
class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    signal_score: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    signal_strength: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), nullable=True)
    trade_quality: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    urgency_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tradability_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    market_price_at_signal: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    cosine_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    score_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    score_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    window_estimate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    yes_probability_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_tier_mix: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped["Event"] = relationship(back_populates="signals")
    market: Mapped["Market"] = relationship(back_populates="signals")
    outcome: Mapped[Optional["SignalOutcome"]] = relationship(
        back_populates="signal", uselist=False, cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# signal_outcomes  (ML labels — one per signal)
# ---------------------------------------------------------------------------
class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"

    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    price_t5min: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    price_t15min: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    price_t1h: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    price_t24h: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    price_resolved: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    direction_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    outcome_label: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    move_t5min_pct: Mapped[Optional[float]] = mapped_column(Numeric(7, 4), nullable=True)
    move_t15min_pct: Mapped[Optional[float]] = mapped_column(Numeric(7, 4), nullable=True)
    move_t1h_pct: Mapped[Optional[float]] = mapped_column(Numeric(7, 4), nullable=True)
    move_t24h_pct: Mapped[Optional[float]] = mapped_column(Numeric(7, 4), nullable=True)

    signal: Mapped["Signal"] = relationship(back_populates="outcome")


# ---------------------------------------------------------------------------
# user_profiles
# ---------------------------------------------------------------------------
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True, unique=True)
    polymarket_safe_address: Mapped[Optional[str]] = mapped_column(
        String(42), nullable=True, unique=True
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    card_attached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    profile: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    portfolios: Mapped[list["Portfolio"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKeyB2B"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# portfolios
# ---------------------------------------------------------------------------
class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Main")
    total_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    cash_balance: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["UserProfile"] = relationship(back_populates="portfolios")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------
class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    token_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    entry_price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    portfolio: Mapped["Portfolio"] = relationship(back_populates="positions")
    market: Mapped["Market"] = relationship()


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    token_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False, default="GTC")
    polymarket_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    filled_price: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    filled_size: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    portfolio: Mapped["Portfolio"] = relationship(back_populates="orders")
    market: Mapped["Market"] = relationship()
    signal: Mapped[Optional["Signal"]] = relationship()


# ---------------------------------------------------------------------------
# agent_activities
# ---------------------------------------------------------------------------
class AgentActivity(Base):
    __tablename__ = "agent_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# daily_briefs
# ---------------------------------------------------------------------------
class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=True
    )
    brief_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    brief_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sent_via: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# api_keys_b2b
# ---------------------------------------------------------------------------
class ApiKeyB2B(Base):
    __tablename__ = "api_keys_b2b"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="basic")
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["UserProfile"] = relationship(back_populates="api_keys")


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------
Index("ix_news_ingestion_date", News.ingestion_date)
Index("ix_news_clean_bucket", NewsClean.bucket)
Index("ix_events_processing_status", Event.processing_status)
Index("ix_events_bucket", Event.bucket)
Index("ix_signals_created_at", Signal.created_at.desc())
Index("ix_signals_score", Signal.signal_score.desc())


# ---------------------------------------------------------------------------
# gdelt_events_raw  (GDELT 2.0 DOC API staging)
# ---------------------------------------------------------------------------
class GdeltEventRaw(Base):
    __tablename__ = "gdelt_events_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gdelt_event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actor1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tone: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# signals_pending_reasoning  (LLM 429 circuit-breaker staging)
# ---------------------------------------------------------------------------
class SignalPendingReasoning(Base):
    __tablename__ = "signals_pending_reasoning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    market_id: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


Index("ix_gdelt_events_raw_published_at", GdeltEventRaw.published_at.desc())


# ---------------------------------------------------------------------------
# Learn & Trade (2026-04-23 pivot)
# ---------------------------------------------------------------------------
class UserLimits(Base):
    __tablename__ = "user_limits"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    budget_weekly_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=20.00)
    max_stake_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=10.00)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    real_trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooloff_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quiz_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    age_confirmed_18: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cgu_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    week_spent_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    week_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        onupdate=func.now(),
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "YES" | "NO"
    stake_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    pnl_eur: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    is_tutorial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    profile_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tutorial_trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tutorial_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiz_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    budget_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlocked_real_trading_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        onupdate=func.now(),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutcomeView(Base):
    __tablename__ = "outcome_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
