"""signal_predictions: per-signal per-variant predictions + resolved metrics.

Revision ID: 020
Revises: 019
Create Date: 2026-04-23
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_predictions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "signal_id",
            sa.BigInteger,
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.Text, nullable=False),
        sa.Column("predicted_direction", sa.Text, nullable=True),  # BUY_YES | BUY_NO | NULL
        sa.Column("predicted_probability", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("direction_correct", sa.Boolean, nullable=True),
        sa.Column("brier_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("simulated_pnl_eur", sa.Numeric(8, 2), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("signal_id", "variant", name="uq_signal_predictions_signal_variant"),
    )
    op.create_index(
        "idx_sp_variant_resolved",
        "signal_predictions",
        ["variant", "resolved_at"],
        postgresql_where=sa.text("resolved_at IS NOT NULL"),
    )
    op.create_index("idx_sp_signal", "signal_predictions", ["signal_id"])


def downgrade() -> None:
    op.drop_index("idx_sp_signal", table_name="signal_predictions")
    op.drop_index("idx_sp_variant_resolved", table_name="signal_predictions")
    op.drop_table("signal_predictions")
