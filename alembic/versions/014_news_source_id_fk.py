"""normalize news.source_name to sources_registry via source_id FK

Revision ID: 014
Revises: 013
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources_registry.id"), nullable=True),
    )
    op.create_index("ix_news_source_id", "news", ["source_id"])
    op.execute(
        """
        UPDATE news
        SET source_id = sr.id
        FROM sources_registry sr
        WHERE news.source_name = sr.source_name AND news.source_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_news_source_id", table_name="news")
    op.drop_column("news", "source_id")
