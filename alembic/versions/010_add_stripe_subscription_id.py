"""Add stripe_subscription_id to user_profiles.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "stripe_subscription_id")
