"""SQLAlchemy database models for Signal platform."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class SourceRegistry(Base):
    """Source registry for news sources."""

    __tablename__ = "sources_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, or 3
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class News(Base):
    """News articles ingested from various sources."""

    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    source_weight: Mapped[float] = mapped_column(Float, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingestion_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    ingestion_lag_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_computed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        VECTOR(1536), nullable=True
    )

    # Relationships
    entities: Mapped[list["ArticleEntity"]] = relationship(
        "ArticleEntity", back_populates="news", cascade="all, delete-orphan"
    )
    event_links: Mapped[list["EventNewsLink"]] = relationship(
        "EventNewsLink", back_populates="news", cascade="all, delete-orphan"
    )


class ArticleEntity(Base):
    """Extracted entities from news articles."""

    __tablename__ = "article_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    news: Mapped["News"] = relationship("News", back_populates="entities")


class Market(Base):
    """Prediction markets from Polymarket."""

    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    best_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ingestion_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    market_retrieval_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_computed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        VECTOR(1536), nullable=True
    )

    # Relationships
    candidates: Mapped[list["EventMarketCandidate"]] = relationship(
        "EventMarketCandidate", back_populates="market", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="market", cascade="all, delete-orphan"
    )


class Event(Base):
    """Events detected from clustered news articles."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_entities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    bucket: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    event_retrieval_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_computed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        VECTOR(1536), nullable=True
    )

    # Relationships
    news_links: Mapped[list["EventNewsLink"]] = relationship(
        "EventNewsLink", back_populates="event", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["EventMarketCandidate"]] = relationship(
        "EventMarketCandidate", back_populates="event", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["EventMarketAnalysis"]] = relationship(
        "EventMarketAnalysis", back_populates="event", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="event", cascade="all, delete-orphan"
    )


class EventNewsLink(Base):
    """Links between events and news articles."""

    __tablename__ = "event_news_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="news_links")
    news: Mapped["News"] = relationship("News", back_populates="event_links")


class EventMarketCandidate(Base):
    """Candidate markets for events from hybrid search."""

    __tablename__ = "event_market_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    bm25_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cosine_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rrf_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="candidates")
    market: Mapped["Market"] = relationship("Market", back_populates="candidates")

    __table_args__ = (
        UniqueConstraint("event_id", "market_id", name="uq_event_market_candidate"),
    )


class EventMarketFeatures(Base):
    """Computed features for event-market pairs."""

    __tablename__ = "event_market_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    freshness_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confirmation_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_penalty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_resolution_factor: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("event_id", "market_id", name="uq_event_market_features"),
    )


class EventMarketAnalysis(Base):
    """LLM analysis for event-market pairs."""

    __tablename__ = "event_market_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    llm_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_impact_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    llm_catalysts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    llm_risks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    llm_confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_time_sensitivity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="analyses")


class LLMCostLog(Base):
    """Log of LLM API costs."""

    __tablename__ = "llm_cost_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_eur: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class Signal(Base):
    """Generated trading signals."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    market_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # YES or NO
    confidence_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    urgency_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tradability_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    market_price_at_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    signal_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    outcome_label: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    direction_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="signals")
    market: Mapped["Market"] = relationship("Market", back_populates="signals")
    outcomes: Mapped[list["SignalOutcome"]] = relationship(
        "SignalOutcome", back_populates="signal", cascade="all, delete-orphan"
    )


class SignalOutcome(Base):
    """Outcome tracking for signals."""

    __tablename__ = "signal_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False
    )
    price_t5min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t15min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_resolved: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    direction_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    outcome_label: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    signal: Mapped["Signal"] = relationship("Signal", back_populates="outcomes")


# Create indexes

Index("ix_news_embedding", "news", postgresql_using="ivfflat", ndb_tablespace="")