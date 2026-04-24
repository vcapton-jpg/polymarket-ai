"""Integration tests for the embedding_v2 backfill Celery task."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial

import pytest
from sqlalchemy import delete, func, select

from app.db.models import News, NewsClean
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.asyncio


async def _apply_task_in_thread(task, **kwargs):
    """Run a Celery task .apply() in a thread executor.

    pytest-asyncio keeps a running event loop; `_run_async` (used by every
    Celery task body) calls `loop.run_until_complete()` on a *second* loop,
    which Python rejects with "Cannot run the event loop while another loop is
    running".  Offloading the `.apply()` call to a thread gives it a clean
    execution context with no running loop.
    """
    loop = asyncio.get_event_loop()
    async_result = await loop.run_in_executor(
        None, partial(task.apply, kwargs=kwargs)
    )
    return async_result.get()


@pytest.fixture
async def rows_missing_v2(async_db_factory, monkeypatch):
    """Insert 5 NewsClean rows with embedding but NULL embedding_v2, teardown on exit."""
    async def _fake_embed(text):
        return make_toy_embedding(axis=len(text) % 1536)

    # Backfill code imports get_embedding from app.processing.embedding_service.
    monkeypatch.setattr("app.processing.embedding_service.get_embedding", _fake_embed)
    # Backfill module imports it at module-load, so patch that too.
    monkeypatch.setattr(
        "app.workers.tasks_embeddings_backfill.get_embedding", _fake_embed, raising=False,
    )

    ids_news = list(range(900_000_100, 900_000_105))
    ids_clean = list(range(900_000_200, 900_000_205))

    async with async_db_factory() as s:
        for i in range(5):
            s.add(News(
                id=ids_news[i],
                title=f"Test title {i}",
                url=f"https://example.invalid/backfill-{i}",
                source_name="test",
                source_tier=1,
                publish_date=NOW,
            ))
        await s.flush()
        for i in range(5):
            s.add(NewsClean(
                id=ids_clean[i],
                news_id=ids_news[i],
                clean_text=f"article body {i} long enough to pass the filter for v2 composition.",
                embedding=make_toy_embedding(axis=i),
                embedding_v2=None,
            ))
        await s.commit()

    try:
        yield {"news_ids": ids_news, "clean_ids": ids_clean}
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.id.in_(ids_clean)))
            await s.execute(delete(News).where(News.id.in_(ids_news)))
            await s.commit()


async def test_backfill_news_embedding_v2_populates_inserted_rows(rows_missing_v2, async_db_factory):
    from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
    # Eager mode: invoke synchronously (via thread to avoid nested event loops).
    # Loop until no rows remain — on a shared dev DB there may be many
    # pre-existing NULL rows ahead of our fixture's ids in the scan order.
    total_processed = 0
    for _ in range(200):  # hard cap — prevents runaway loops
        result = await _apply_task_in_thread(
            recompute_embedding_v2, surface="news", batch_size=100,
        )
        total_processed += result["processed"]
        if result["remaining"] == 0:
            break
    assert total_processed >= 5

    async with async_db_factory() as s:
        rows = (await s.execute(
            select(NewsClean).where(NewsClean.id.in_(rows_missing_v2["clean_ids"]))
        )).scalars().all()
        for r in rows:
            assert r.embedding_v2 is not None, f"clean_id={r.id} still NULL"
            assert r.embedding_v2_composition == "news_v2_lead_tail"
            assert r.embedding_v2_computed_at is not None


async def test_backfill_is_idempotent(rows_missing_v2, async_db_factory):
    from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
    # Drain all NULL rows first.
    for _ in range(200):
        r = await _apply_task_in_thread(
            recompute_embedding_v2, surface="news", batch_size=100,
        )
        if r["remaining"] == 0:
            break

    # Capture timestamps for our fixture rows post-drain.
    async with async_db_factory() as s:
        rows = (await s.execute(
            select(NewsClean).where(NewsClean.id.in_(rows_missing_v2["clean_ids"]))
        )).scalars().all()
        first_pass_timestamps = {r.id: r.embedding_v2_computed_at for r in rows}
        assert all(v is not None for v in first_pass_timestamps.values())

    # Second run should be a no-op for our rows (nothing NULL left for them).
    r2 = await _apply_task_in_thread(
        recompute_embedding_v2, surface="news", batch_size=100,
    )
    assert r2["processed"] == 0

    async with async_db_factory() as s:
        rows = (await s.execute(
            select(NewsClean).where(NewsClean.id.in_(rows_missing_v2["clean_ids"]))
        )).scalars().all()
        for r in rows:
            assert r.embedding_v2_computed_at == first_pass_timestamps[r.id]
