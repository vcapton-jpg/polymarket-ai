"""Add email and password_hash to user_profiles for auth.

Revision ID: 009
Revises: 008
"""
import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("password_hash", sa.Text(), nullable=True))
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_profiles_email", table_name="user_profiles")
    op.drop_column("user_profiles", "password_hash")
    op.drop_column("user_profiles", "email")
