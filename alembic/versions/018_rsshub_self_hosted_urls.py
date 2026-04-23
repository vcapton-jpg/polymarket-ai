"""rewrite rsshub.app → rsshub:1200 in sources_registry

Revision ID: 018
Revises: 017
Create Date: 2026-04-23
"""
from alembic import op


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sources_registry
        SET url = REPLACE(url, 'https://rsshub.app', 'http://rsshub:1200')
        WHERE source_type = 'x_rss' AND url LIKE 'https://rsshub.app%'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE sources_registry
        SET url = REPLACE(url, 'http://rsshub:1200', 'https://rsshub.app')
        WHERE source_type = 'x_rss' AND url LIKE 'http://rsshub:1200%'
        """
    )
