"""Add signal_strength and trade_quality columns to signals table.

Two-dimensional scoring: signal_strength (intelligence quality) and
trade_quality (market tradability) stored separately.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("signal_strength", sa.Numeric(5, 1), nullable=True),
    )
    op.add_column(
        "signals",
        sa.Column("trade_quality", sa.Numeric(5, 1), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "trade_quality")
    op.drop_column("signals", "signal_strength")
