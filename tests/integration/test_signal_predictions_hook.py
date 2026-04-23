"""E2E: _persist_signal writes the 4 baseline + 1 signal rows inside the
same transaction."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.mark.asyncio
async def test_persist_signal_writes_all_variant_rows(async_db_factory):
    from app.signal.signal_builder import _persist_signal

    # Use high, unlikely-to-collide ids / market strings
    EVENT_ID = 991080
    MARKET_ID = "0xmeasure-hook-test-1"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    try:
        assembled = {
            "event_id": EVENT_ID,
            "market_id": MARKET_ID,
            "market_price": 0.65,
            "reasoning": "because reasons",
            "llm_model_version": "gpt-4o-test",
            "source_tier_mix": {"tier1": 2},
            "direction_recommendation": "YES",
            "impact_score": 0.8,
            "confidence": 0.7,
            "article_excerpts": [],
        }
        articles = [
            {"news_clean_id": 1, "direction_hint": "YES", "source_weight": 0.9},
        ]
        await _persist_signal(assembled, articles)

        async with async_db_factory() as s:
            sig = (
                await s.execute(
                    select(Signal).where(Signal.market_id == MARKET_ID)
                )
            ).scalar_one()
            rows = (
                await s.execute(
                    select(SignalPrediction).where(
                        SignalPrediction.signal_id == sig.id
                    )
                )
            ).scalars().all()
            variants = {r.variant for r in rows}
            assert variants == {
                "signal",
                "baseline_random",
                "baseline_market_price",
                "baseline_momentum",
                "baseline_news_sentiment",
            }
            mp = next(r for r in rows if r.variant == "baseline_market_price")
            assert float(mp.predicted_probability) == pytest.approx(0.65, abs=1e-4)
            mom = next(r for r in rows if r.variant == "baseline_momentum")
            assert mom.predicted_direction is None
            assert mom.predicted_probability is None
    finally:
        # teardown
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
