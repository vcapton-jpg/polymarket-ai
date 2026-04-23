"""add key_excerpt and relevance_score to event_news_links

Revision ID: 016
Revises: 015
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_news_links", sa.Column("key_excerpt", sa.Text(), nullable=True))
    op.add_column("event_news_links", sa.Column("relevance_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("event_news_links", "relevance_score")
    op.drop_column("event_news_links", "key_excerpt")
