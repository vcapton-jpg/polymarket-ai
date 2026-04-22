"""Add trial tracking + profile JSONB to user_profiles.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "card_attached",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column("profile", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "profile")
    op.drop_column("user_profiles", "card_attached")
    op.drop_column("user_profiles", "trial_ends_at")
