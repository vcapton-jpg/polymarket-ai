"""add polymarket_safe_address to user_profiles

Revision ID: 013
Revises: 012
Create Date: 2026-04-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("polymarket_safe_address", sa.String(length=42), nullable=True),
    )
    op.create_unique_constraint(
        "uq_user_profiles_polymarket_safe_address",
        "user_profiles",
        ["polymarket_safe_address"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_profiles_polymarket_safe_address",
        "user_profiles",
        type_="unique",
    )
    op.drop_column("user_profiles", "polymarket_safe_address")
