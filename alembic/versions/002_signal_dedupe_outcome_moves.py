"""Signal dedupe key + outcome move columns for ML dataset.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("dedupe_key", sa.String(64), nullable=True),
    )
    op.create_index("ix_signals_dedupe_key_created", "signals", ["dedupe_key", "created_at"])

    op.add_column(
        "signal_outcomes",
        sa.Column("move_t15min_pct", sa.Numeric(7, 4), nullable=True),
    )
    op.add_column(
        "signal_outcomes",
        sa.Column("move_t1h_pct", sa.Numeric(7, 4), nullable=True),
    )
    op.add_column(
        "signal_outcomes",
        sa.Column("move_t24h_pct", sa.Numeric(7, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_signals_dedupe_key_created", table_name="signals")
    op.drop_column("signals", "dedupe_key")
    op.drop_column("signal_outcomes", "move_t24h_pct")
    op.drop_column("signal_outcomes", "move_t1h_pct")
    op.drop_column("signal_outcomes", "move_t15min_pct")
