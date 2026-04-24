# tests/integration/test_hybrid_search_v2_db.py
"""End-to-end: dispatcher routes v1 and v2 against a real DB."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import Market


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dispatcher_routes_by_flag(async_db_factory, monkeypatch):
    """Same input, different variants → both return a list of dicts with rank."""
    # Seed 3 markets.
    async with async_db_factory() as s:
        for i, mid in enumerate(("m_alpha", "m_beta", "m_gamma")):
            s.add(Market(
                market_id=mid, question=f"Will {mid} win?",
                category="politics", bucket="politics",
                end_date=datetime(2026, 5, 15 + i, tzinfo=timezone.utc),
                active=True, closed=False, accepting_orders=True,
                embedding=[0.1] * 1536,
                market_retrieval_text=f"test text {mid}",
            ))
        await s.commit()

    try:
        from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
        async with async_db_factory() as s:
            # v1 path
            monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v1")
            get_settings.cache_clear()
            r1 = await hybrid_search_markets_dispatch(
                s, [0.1] * 1536, "will win", top_k=3,
                event_bucket="politics", event_entities=["alpha"],
                event_last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            )
            assert r1 and all("rank" in row for row in r1)

            # v2 path
            monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
            get_settings.cache_clear()
            r2 = await hybrid_search_markets_dispatch(
                s, [0.1] * 1536, "will win", top_k=3,
                event_bucket="politics", event_entities=["alpha"],
                event_last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            )
            assert r2 and all("rank" in row for row in r2)
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Market).where(Market.market_id.in_(
                ("m_alpha", "m_beta", "m_gamma")
            )))
            await s.commit()
