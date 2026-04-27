"""upsert_event_market_features: persist features for every analyzed pair.

Pre-fix bug (data audit 2026-04-25): the `event_market_features` table was
defined but never written by the prod path, leaving 0 rows in production
despite 5 425 `event_market_analysis` rows. The 6 backend features
(freshness, source_weight, confirmation, liquidity, spread,
time_to_resolution) and the 3 LLM features (impact_strength,
llm_confidence, ambiguity_score) were ephemeral — only kept on
`Signal._features` for signals that passed the gates.

Post-fix contract: every (event_id, market_id) pair that produced an
`EventMarketAnalysis` row also has a corresponding `EventMarketFeatures`
row, populated at-time and idempotent on re-runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, EventMarketFeatures, Market

EVENT_ID = 992200
MARKET_ID = "0xfeatures-persist-1"


@pytest.fixture
async def seeded_event_and_market(async_db_factory):
    async with async_db_factory() as s:
        s.add(Event(id=EVENT_ID, event_title="e"))
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        await s.commit()
    try:
        yield
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID
            ))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_upsert_writes_full_row(async_db_factory, seeded_event_and_market):
    from app.scoring.event_market_features_writer import upsert_event_market_features

    features = {
        "freshness": 1.0,
        "source_weight": 0.85,
        "confirmation": 0.7,
        "liquidity": 1.0,
        "spread": 0.8,
        "time_to_resolution": 0.4,
    }
    async with async_db_factory() as s:
        await upsert_event_market_features(
            s,
            event_id=EVENT_ID,
            market_id=MARKET_ID,
            features=features,
            impact_strength=0.75,
            llm_confidence=0.90,
            ambiguity_score=0.20,
        )
        await s.commit()

    async with async_db_factory() as s:
        row = (await s.execute(
            select(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID,
                EventMarketFeatures.market_id == MARKET_ID,
            )
        )).scalar_one()

        assert row.freshness_factor == pytest.approx(1.0)
        assert row.source_weight == pytest.approx(0.85)
        assert row.confirmation_factor == pytest.approx(0.7)
        assert row.liquidity_factor == pytest.approx(1.0)
        assert row.spread_penalty == pytest.approx(0.8)
        assert row.time_to_resolution_factor == pytest.approx(0.4)
        assert row.impact_strength == pytest.approx(0.75)
        assert row.llm_confidence == pytest.approx(0.90)
        assert row.ambiguity_score == pytest.approx(0.20)
        # outcome_label is filled later by tasks_outcomes — must remain NULL on first write.
        assert row.outcome_label is None


@pytest.mark.asyncio
async def test_upsert_is_idempotent_with_updates(async_db_factory, seeded_event_and_market):
    """Second call with new values updates the same row in place — no duplicate insert."""
    from app.scoring.event_market_features_writer import upsert_event_market_features

    initial = {
        "freshness": 0.4,
        "source_weight": 0.5,
        "confirmation": 0.5,
        "liquidity": 0.6,
        "spread": 1.0,
        "time_to_resolution": 0.6,
    }
    async with async_db_factory() as s:
        await upsert_event_market_features(
            s,
            event_id=EVENT_ID,
            market_id=MARKET_ID,
            features=initial,
            impact_strength=0.50,
            llm_confidence=0.50,
            ambiguity_score=0.50,
        )
        await s.commit()

    updated = {
        "freshness": 1.0,
        "source_weight": 1.0,
        "confirmation": 1.0,
        "liquidity": 1.0,
        "spread": 1.0,
        "time_to_resolution": 1.0,
    }
    async with async_db_factory() as s:
        await upsert_event_market_features(
            s,
            event_id=EVENT_ID,
            market_id=MARKET_ID,
            features=updated,
            impact_strength=0.95,
            llm_confidence=0.95,
            ambiguity_score=0.05,
        )
        await s.commit()

    async with async_db_factory() as s:
        rows = (await s.execute(
            select(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID,
                EventMarketFeatures.market_id == MARKET_ID,
            )
        )).scalars().all()

        # Idempotency: still exactly one row.
        assert len(rows) == 1
        # Update applied: latest values win.
        assert rows[0].freshness_factor == pytest.approx(1.0)
        assert rows[0].impact_strength == pytest.approx(0.95)
        assert rows[0].ambiguity_score == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_upsert_accepts_none_llm_features(async_db_factory, seeded_event_and_market):
    """LLM features may be NULL when the LLM call failed — feature persistence
    must still write the backend features for the gate-replay backtest."""
    from app.scoring.event_market_features_writer import upsert_event_market_features

    features = {
        "freshness": 0.7,
        "source_weight": 0.5,
        "confirmation": 0.5,
        "liquidity": 0.6,
        "spread": 0.8,
        "time_to_resolution": 0.6,
    }
    async with async_db_factory() as s:
        await upsert_event_market_features(
            s,
            event_id=EVENT_ID,
            market_id=MARKET_ID,
            features=features,
            impact_strength=None,
            llm_confidence=None,
            ambiguity_score=None,
        )
        await s.commit()

    async with async_db_factory() as s:
        row = (await s.execute(
            select(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID,
                EventMarketFeatures.market_id == MARKET_ID,
            )
        )).scalar_one()
        assert row.freshness_factor == pytest.approx(0.7)
        assert row.impact_strength is None
        assert row.llm_confidence is None
        assert row.ambiguity_score is None
