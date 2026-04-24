"""Integration: record_shadow_ranking writes top-k rows idempotently."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import Event, Market, EventMarketRankingShadow


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _apply_task_in_thread(fn, **kwargs):
    """Run a celery task in a fresh thread to avoid event-loop collision
    with pytest-asyncio. Same pattern as tests/integration/test_sourcing_shadow.py."""
    import concurrent.futures

    def _run():
        return fn.apply(kwargs=kwargs).get(disable_sync_subtasks=False, timeout=30)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result(timeout=60)


@pytest.mark.asyncio
async def test_record_shadow_ranking_writes_rows(async_db_factory, monkeypatch):
    from app.workers.tasks_ranking_shadow import record_shadow_ranking

    eid = 900_123_001  # high-range to avoid collision on shared dev DB
    async with async_db_factory() as s:
        s.add(Event(
            id=eid,
            event_title="t-shadow-1",
            event_summary="summary",
            bucket="politics",
            last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            embedding=[0.1] * 1536,
            event_retrieval_text="t-shadow-1 summary",
        ))
        for mid in ("shadow_m1", "shadow_m2"):
            s.add(Market(
                market_id=mid, question=f"Q-{mid}",
                category="politics", bucket="politics",
                end_date=datetime(2026, 5, 15, tzinfo=timezone.utc),
                active=True, closed=False, accepting_orders=True,
                embedding=[0.1] * 1536,
                market_retrieval_text=f"retrieval {mid}",
            ))
        await s.commit()

    try:
        # First run: writes rows.
        result = _apply_task_in_thread(record_shadow_ranking, event_id=eid)
        assert result["status"] == "ok"
        assert result["rows_inserted"] >= 1

        # Second run: same call, no new rows (UNIQUE + ON CONFLICT DO NOTHING).
        result2 = _apply_task_in_thread(record_shadow_ranking, event_id=eid)
        assert result2["status"] == "ok"
        assert result2["rows_inserted"] == 0

        async with async_db_factory() as s:
            rows = (await s.execute(
                select(EventMarketRankingShadow).where(EventMarketRankingShadow.event_id == eid)
            )).scalars().all()
            assert rows and all(r.variant in ("v1", "v2") for r in rows)
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventMarketRankingShadow).where(EventMarketRankingShadow.event_id == eid))
            await s.execute(delete(Event).where(Event.id == eid))
            await s.execute(delete(Market).where(Market.market_id.in_(("shadow_m1", "shadow_m2"))))
            await s.commit()


@pytest.mark.asyncio
async def test_record_shadow_ranking_disabled_by_flag(async_db_factory, monkeypatch):
    from app.workers.tasks_ranking_shadow import record_shadow_ranking
    monkeypatch.setenv("RANKING_SHADOW_ENABLED", "false")
    get_settings.cache_clear()

    result = _apply_task_in_thread(record_shadow_ranking, event_id=12345)
    assert result == {"status": "disabled", "event_id": 12345}
