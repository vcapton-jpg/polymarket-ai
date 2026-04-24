"""Pipelines write both embedding and embedding_v2 on new rows.

This is a schema-acceptance shield: it verifies the v2 columns are
writable and the ORM round-trip preserves them. The full pipeline
trigger is exercised implicitly by the main backend suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models import News, NewsClean
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


pytestmark = pytest.mark.asyncio


async def test_news_creation_writes_embedding_v2(async_db_factory):
    """NewsClean accepts both embedding and embedding_v2 + companion metadata columns."""
    # Pick a news id unlikely to collide with the rest of the backend suite
    # (fixed IDs race across tests; full-suite runs populate low-numbered rows).
    news_id = 900_000_000 + (uuid.uuid4().int % 10_000_000)
    unique_url = f"https://example.invalid/v2-smoke-{news_id}"

    try:
        async with async_db_factory() as s:
            # Parent News row (NewsClean.news_id is FK, NOT NULL, UNIQUE).
            news = News(
                id=news_id,
                title="A title for the v2 smoke test",
                url=unique_url,
                source_name="test",
                source_tier=1,
                publish_date=NOW,
            )
            s.add(news)
            await s.flush()

            nc = NewsClean(
                news_id=news_id,
                clean_text="first paragraph is long enough to pass the filter in v2",
                embedding=make_toy_embedding(axis=3),
                embedding_v2=make_toy_embedding(axis=7),
                embedding_v2_composition="news_v2_lead_tail",
                embedding_v2_computed_at=NOW,
            )
            s.add(nc)
            await s.commit()

        async with async_db_factory() as s:
            stored = (await s.execute(
                select(NewsClean).where(NewsClean.news_id == news_id)
            )).scalar_one()
            assert stored.embedding is not None
            assert stored.embedding_v2 is not None
            assert stored.embedding_v2_composition == "news_v2_lead_tail"
            assert stored.embedding_v2_computed_at is not None
    finally:
        # Cleanup so re-runs (and the full suite) stay isolated.
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.news_id == news_id))
            await s.execute(delete(News).where(News.id == news_id))
            await s.commit()
