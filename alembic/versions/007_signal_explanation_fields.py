"""Add score_label, score_explanation, window_estimate, yes_probability_explanation to signals.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("score_label", sa.String(20), nullable=True))
    op.add_column("signals", sa.Column("score_explanation", sa.Text(), nullable=True))
    op.add_column("signals", sa.Column("window_estimate", sa.String(50), nullable=True))
    op.add_column("signals", sa.Column("yes_probability_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "yes_probability_explanation")
    op.drop_column("signals", "window_estimate")
    op.drop_column("signals", "score_explanation")
    op.drop_column("signals", "score_label")
