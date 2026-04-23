"""Learn & Trade tables: user_limits, paper_positions, onboarding_progress, quiz_attempts, outcome_views.

Revision ID: 019_user_limits_onboarding
Revises: 018_rsshub_self_hosted_urls
Create Date: 2026-04-23
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_limits",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("budget_weekly_eur", sa.Numeric(10, 2), nullable=False, server_default="20.00"),
        sa.Column("max_stake_eur", sa.Numeric(10, 2), nullable=False, server_default="10.00"),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("real_trades_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_losses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cooloff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("age_confirmed_18", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cgu_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("week_spent_eur", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("week_reset_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("market_id", sa.Text, sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("stake_eur", sa.Numeric(10, 2), nullable=False),
        sa.Column("entry_price", sa.Numeric(6, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(6, 4), nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("correct", sa.Boolean, nullable=True),
        sa.Column("pnl_eur", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_tutorial", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_paper_positions_user", "paper_positions", ["user_id"])

    op.create_table(
        "onboarding_progress",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("profile_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tutorial_trades_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tutorial_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("quiz_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("budget_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("unlocked_real_trading_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", postgresql.JSONB, nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quiz_attempts_user", "quiz_attempts", ["user_id"])

    op.create_table(
        "outcome_views",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_outcome_views_user_signal"),
    )


def downgrade() -> None:
    op.drop_table("outcome_views")
    op.drop_table("quiz_attempts")
    op.drop_table("onboarding_progress")
    op.drop_index("ix_paper_positions_user", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_table("user_limits")
