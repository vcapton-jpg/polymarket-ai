"""backfill_reasoning drains signals_pending_reasoning once LLM works again."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event, Market, Signal, SignalPendingReasoning
from app.workers.tasks_scoring import _backfill_reasoning_async


@pytest.mark.asyncio
async def test_backfill_drains_pending_on_success():
    session_factory = get_session_factory()

    # Seed parents — Signal has FK on events.id and markets.market_id.
    async with session_factory() as s:
        s.add(Event(id=999001, event_title="backfill test event"))
        s.add(Market(market_id="m-backfill-test", question="q?"))
        s.add(SignalPendingReasoning(
            event_id=999001,
            market_id="m-backfill-test",
            inputs={
                "event": {"id": 999001, "title": "t", "summary": "s"},
                "market": {"id": "m-backfill-test", "question": "q?", "price": 0.5},
                "articles": [{
                    "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
                    "source_tier": 1, "clean_text": "summit confirmed today", "publish_date": None,
                }],
            },
        ))
        await s.commit()

    try:
        analyzer = AsyncMock()
        analyzer.model_version = "gpt-4o-mini-2024-07-18"
        analyzer.analyze = AsyncMock(return_value={
            "impact_score": 0.8, "confidence": 0.9, "catalyst": "Summit confirmed",
            "reasoning": (
                "Reuters Top News confirms the summit, addressing the market resolution criteria "
                "directly. Convergence raises conviction and direction is YES."
            ),
            "direction_recommendation": "YES",
            "article_excerpts": [
                {"news_clean_id": 1, "excerpt": "summit confirmed today", "relevance": 0.9}
            ],
            "source_tier_mix": {"tier_1": 1},
        })

        n = await _backfill_reasoning_async(limit=10, analyzer=analyzer)
        assert n >= 1

        async with session_factory() as s:
            leftover = (await s.execute(
                select(SignalPendingReasoning).where(SignalPendingReasoning.market_id == "m-backfill-test")
            )).scalar_one_or_none()
            assert leftover is None
            sig = (await s.execute(
                select(Signal).where(Signal.market_id == "m-backfill-test")
            )).scalar_one()
            assert sig.reasoning.startswith("Reuters")
    finally:
        # Cleanup — cascade-delete Signals via parent row deletes.
        async with session_factory() as s:
            from sqlalchemy import delete
            await s.execute(delete(SignalPendingReasoning).where(SignalPendingReasoning.market_id == "m-backfill-test"))
            await s.execute(delete(Market).where(Market.market_id == "m-backfill-test"))
            await s.execute(delete(Event).where(Event.id == 999001))
            await s.commit()
