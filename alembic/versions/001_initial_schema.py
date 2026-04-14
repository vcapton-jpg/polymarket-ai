"""Initial schema — all tables from Blueprint V4.

Revision ID: 001
Revises:
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="rss"),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "news",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(1024), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_tier", sa.SmallInteger(), nullable=False),
        sa.Column("source_weight", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ingestion_lag_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_news_ingestion_date", "news", ["ingestion_date"])

    op.create_table(
        "news_clean",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("news_id", sa.Integer(), sa.ForeignKey("news.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("simhash", sa.Integer(), nullable=True),
        sa.Column("bucket", sa.String(50), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("embedding_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TABLE news_clean ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.create_index("ix_news_clean_bucket", "news_clean", ["bucket"])

    op.create_table(
        "article_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clean_id", sa.Integer(), sa.ForeignKey("news_clean.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_value", sa.Text(), nullable=False),
    )

    op.create_table(
        "markets",
        sa.Column("market_id", sa.Text(), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("tags", ARRAY(sa.Text()), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("accepting_orders", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("volume", sa.Numeric(20, 6), nullable=True),
        sa.Column("volume_24h", sa.Numeric(20, 6), nullable=True),
        sa.Column("liquidity", sa.Numeric(20, 6), nullable=True),
        sa.Column("best_bid", sa.Numeric(6, 4), nullable=True),
        sa.Column("best_ask", sa.Numeric(6, 4), nullable=True),
        sa.Column("spread", sa.Numeric(6, 4), nullable=True),
        sa.Column("last_trade_price", sa.Numeric(6, 4), nullable=True),
        sa.Column("clob_token_ids", JSONB(), nullable=True),
        sa.Column("liquidity_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("volume_24h_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("market_retrieval_text", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE markets ADD COLUMN IF NOT EXISTS embedding vector(1536)")

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_title", sa.Text(), nullable=False),
        sa.Column("event_summary", sa.Text(), nullable=True),
        sa.Column("event_retrieval_text", sa.Text(), nullable=True),
        sa.Column("key_entities", ARRAY(sa.Text()), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=True),
        sa.Column("bucket", sa.String(50), nullable=True),
        sa.Column("articles_count", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("unique_sources_count", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.create_index("ix_events_processing_status", "events", ["processing_status"])
    op.create_index("ix_events_bucket", "events", ["bucket"])

    op.create_table(
        "event_news_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clean_id", sa.Integer(), sa.ForeignKey("news_clean.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="supporting"),
        sa.UniqueConstraint("event_id", "clean_id", name="uq_event_news_link"),
    )

    op.create_table(
        "event_market_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text(), sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("bm25_score", sa.Float(), nullable=True),
        sa.Column("cosine_score", sa.Float(), nullable=True),
        sa.Column("rrf_score", sa.Float(), nullable=True),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("event_id", "market_id", name="uq_event_market_candidate"),
    )

    op.create_table(
        "event_market_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text(), sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("impact_direction", sa.String(20), nullable=True),
        sa.Column("impact_strength", sa.Numeric(3, 2), nullable=True),
        sa.Column("llm_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("ambiguity_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("catalysts", JSONB(), nullable=True),
        sa.Column("risks", JSONB(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("llm_cost_usd", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", "market_id", name="uq_event_market_analysis"),
    )

    op.create_table(
        "event_market_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text(), sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("impact_strength", sa.Float(), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("ambiguity_score", sa.Float(), nullable=True),
        sa.Column("freshness_factor", sa.Float(), nullable=True),
        sa.Column("source_weight", sa.Float(), nullable=True),
        sa.Column("confirmation_factor", sa.Float(), nullable=True),
        sa.Column("liquidity_factor", sa.Float(), nullable=True),
        sa.Column("spread_penalty", sa.Float(), nullable=True),
        sa.Column("time_to_resolution_factor", sa.Float(), nullable=True),
        sa.Column("outcome_label", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("event_id", "market_id", name="uq_event_market_features"),
    )

    op.create_table(
        "llm_cost_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("call_type", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False),
        sa.Column("tokens_output", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text(), sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_score", sa.Numeric(5, 1), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("confidence_label", sa.String(20), nullable=True),
        sa.Column("urgency_label", sa.String(20), nullable=True),
        sa.Column("tradability_label", sa.String(20), nullable=True),
        sa.Column("market_price_at_signal", sa.Numeric(6, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signals_created_at", "signals", [sa.text("created_at DESC")])
    op.create_index("ix_signals_score", "signals", [sa.text("signal_score DESC")])

    op.create_table(
        "signal_outcomes",
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_t5min", sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t15min", sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t1h", sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t24h", sa.Numeric(6, 4), nullable=True),
        sa.Column("price_resolved", sa.Numeric(6, 4), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("outcome_label", sa.SmallInteger(), nullable=True),
        sa.Column("move_t5min_pct", sa.Numeric(7, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("signal_outcomes")
    op.drop_table("signals")
    op.drop_table("llm_cost_log")
    op.drop_table("event_market_features")
    op.drop_table("event_market_analysis")
    op.drop_table("event_market_candidates")
    op.drop_table("event_news_links")
    op.drop_table("events")
    op.drop_table("markets")
    op.drop_table("article_entities")
    op.drop_table("news_clean")
    op.drop_table("news")
    op.drop_table("sources_registry")
