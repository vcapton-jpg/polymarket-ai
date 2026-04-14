"""Add trading, agents, and business tables.

Tables: user_profiles, portfolios, positions, orders,
agent_activities, daily_briefs, api_keys_b2b

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "user_profiles"):
        return

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wallet_address", sa.String(42), nullable=True, unique=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("telegram_chat_id", sa.String(50), nullable=True),
        sa.Column("preferences", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default="Main"),
        sa.Column("total_value", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("cash_balance", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text, sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", sa.Text, nullable=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("size", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("entry_price", sa.Numeric(6, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(6, 4), nullable=True),
        sa.Column("pnl_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.Text, sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_id", sa.Text, nullable=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("price", sa.Numeric(6, 4), nullable=False),
        sa.Column("size", sa.Numeric(20, 6), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=False, server_default="GTC"),
        sa.Column("polymarket_order_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filled_price", sa.Numeric(6, 4), nullable=True),
        sa.Column("filled_size", sa.Numeric(20, 6), nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "agent_activities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_name", sa.String(50), nullable=False, index=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "daily_briefs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("brief_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("brief_type", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("sent_via", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "api_keys_b2b",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False, server_default="basic"),
        sa.Column("rate_limit", sa.Integer, nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("api_keys_b2b")
    op.drop_table("daily_briefs")
    op.drop_table("agent_activities")
    op.drop_table("orders")
    op.drop_table("positions")
    op.drop_table("portfolios")
    op.drop_table("user_profiles")
