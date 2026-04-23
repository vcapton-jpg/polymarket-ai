"""Migration 014 — news.source_id backfill coverage."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def _make_session():
    """Create a fresh async session (new engine) to avoid event-loop conflicts."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_news_source_id_column_exists_after_upgrade():
    async with _make_session()() as s:
        rows = (await s.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='news' AND column_name='source_id'"
        ))).all()
        assert rows, "news.source_id must exist after migration 014"


@pytest.mark.asyncio
async def test_news_source_id_index_exists():
    async with _make_session()() as s:
        rows = (await s.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename='news' AND indexname='ix_news_source_id'"
        ))).all()
        assert rows, "ix_news_source_id must exist"


@pytest.mark.asyncio
async def test_news_source_id_backfill_coverage():
    async with _make_session()() as s:
        total = (await s.execute(text(
            "SELECT COUNT(*) FROM news n "
            "JOIN sources_registry sr ON n.source_name = sr.source_name"
        ))).scalar_one()
        matched = (await s.execute(text(
            "SELECT COUNT(*) FROM news n "
            "JOIN sources_registry sr ON n.source_name = sr.source_name "
            "WHERE n.source_id IS NOT NULL"
        ))).scalar_one()
        if total > 0:
            assert matched / total >= 0.95, f"Backfill coverage too low: {matched}/{total}"
