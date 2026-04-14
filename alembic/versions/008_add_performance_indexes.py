"""Add performance indexes for common query patterns.

Revision ID: 008
Revises: 007
"""
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_signals_event_market", "signals", ["event_id", "market_id"])
    op.create_index("ix_signals_market_created", "signals", ["market_id", "created_at"])
    op.create_index("ix_event_market_analysis_event_market", "event_market_analysis", ["event_id", "market_id"])
    op.create_index("ix_event_market_candidates_event", "event_market_candidates", ["event_id"])
    op.create_index("ix_event_news_links_clean_id", "event_news_links", ["clean_id"])
    op.create_index("ix_news_clean_embedding_null", "news_clean", ["id"], postgresql_where="embedding IS NULL")
    op.create_index("ix_signal_outcomes_direction_correct", "signal_outcomes", ["direction_correct"])
    op.create_index("ix_agent_activities_created", "agent_activities", ["created_at"])
    op.create_index("ix_markets_active_closed", "markets", ["active", "closed"])


def downgrade() -> None:
    op.drop_index("ix_markets_active_closed")
    op.drop_index("ix_agent_activities_created")
    op.drop_index("ix_signal_outcomes_direction_correct")
    op.drop_index("ix_news_clean_embedding_null")
    op.drop_index("ix_event_news_links_clean_id")
    op.drop_index("ix_event_market_candidates_event")
    op.drop_index("ix_event_market_analysis_event_market")
    op.drop_index("ix_signals_market_created")
    op.drop_index("ix_signals_event_market")
