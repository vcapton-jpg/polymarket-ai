from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, Market, Signal, SignalPrediction
from app.measurement.pipeline import record_baselines, schedule_shadow_variants
from app.measurement.scoring_context import ArticleImpact, ScoringContext
from app.measurement.variant_registry import VariantPrediction, VariantRegistry

# Use high, non-clashing IDs so repeated test runs don't conflict.
_MKT1 = "0xmeasure-pipeline-test-1"
_MKT2 = "0xmeasure-pipeline-test-2"
_MKT3 = "0xmeasure-pipeline-test-3"
_EVT1 = 991001
_EVT2 = 991002
_EVT3 = 991003


async def _seed_signal(session, market_id: str, event_id: int) -> int:
    session.add(Market(market_id=market_id, question="q", active=True))
    session.add(Event(id=event_id, event_title="e"))
    await session.flush()
    sig = Signal(event_id=event_id, market_id=market_id, signal_score=80,
                 direction="BUY_YES", market_price_at_signal=0.6)
    session.add(sig)
    await session.flush()
    return sig.id


def _ctx(signal_id: int, market_id: str, event_id: int) -> ScoringContext:
    return ScoringContext(
        signal_id=signal_id, market_id=market_id, event_id=event_id,
        market_price=0.6, market_price_24h_ago=0.5,
        article_impacts=(ArticleImpact(direction="YES", source_weight=0.8),),
        t0=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )


async def _cleanup(async_db_factory, market_id: str, event_id: int) -> None:
    async with async_db_factory() as s:
        # SignalPrediction and Signal cascade-delete via ON DELETE CASCADE from signals.
        # Signals cascade-delete when Event deleted. Markets cascade too.
        await s.execute(delete(Signal).where(Signal.market_id == market_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.execute(delete(Market).where(Market.market_id == market_id))
        await s.commit()


@pytest.mark.asyncio
async def test_record_baselines_inserts_signal_plus_all_baselines(async_db_factory):
    async with async_db_factory() as s:
        sid = await _seed_signal(s, market_id=_MKT1, event_id=_EVT1)
        reg = VariantRegistry()
        reg.register_baseline("b_fake", lambda c: VariantPrediction("BUY_YES", 0.7))

        n = await record_baselines(s, signal_id=sid, ctx=_ctx(sid, _MKT1, _EVT1), registry=reg)
        await s.commit()

    try:
        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalars().all()
            variants = {r.variant for r in rows}
            assert variants == {"signal", "b_fake"}
            assert n == 2
    finally:
        await _cleanup(async_db_factory, _MKT1, _EVT1)


@pytest.mark.asyncio
async def test_record_baselines_inserts_rows_even_when_baseline_returns_none(async_db_factory):
    async with async_db_factory() as s:
        sid = await _seed_signal(s, market_id=_MKT2, event_id=_EVT2)
        reg = VariantRegistry()
        reg.register_baseline("b_missing", lambda c: VariantPrediction(None, None))
        await record_baselines(s, signal_id=sid, ctx=_ctx(sid, _MKT2, _EVT2), registry=reg)
        await s.commit()

    try:
        async with async_db_factory() as s:
            row = (
                await s.execute(
                    select(SignalPrediction).where(
                        SignalPrediction.signal_id == sid,
                        SignalPrediction.variant == "b_missing",
                    )
                )
            ).scalar_one()
            assert row.predicted_direction is None
            assert row.predicted_probability is None
    finally:
        await _cleanup(async_db_factory, _MKT2, _EVT2)


@pytest.mark.asyncio
async def test_record_baselines_is_idempotent_per_signal_variant(async_db_factory):
    """Second call with same signal+variant is a no-op — unique constraint catches it."""
    async with async_db_factory() as s:
        sid = await _seed_signal(s, market_id=_MKT3, event_id=_EVT3)
        reg = VariantRegistry()
        reg.register_baseline("b_x", lambda c: VariantPrediction("BUY_YES", 0.7))
        await record_baselines(s, signal_id=sid, ctx=_ctx(sid, _MKT3, _EVT3), registry=reg)
        await s.commit()

    try:
        async with async_db_factory() as s:
            # second call: pipeline must detect conflict and not raise
            reg2 = VariantRegistry()
            reg2.register_baseline("b_x", lambda c: VariantPrediction("BUY_YES", 0.7))
            await record_baselines(s, signal_id=sid, ctx=_ctx(sid, _MKT3, _EVT3), registry=reg2)
            await s.commit()

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalars().all()
            # 1 'signal' + 1 'b_x', no duplicates
            assert len(rows) == 2
    finally:
        await _cleanup(async_db_factory, _MKT3, _EVT3)


def test_schedule_shadow_variants_is_a_noop_stub():
    """Task 6 ships the hook; chantier #3 fills the shadow registry."""
    # Must not raise, must not require a signal to exist.
    schedule_shadow_variants(999_999)
