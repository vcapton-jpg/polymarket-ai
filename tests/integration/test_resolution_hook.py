"""E2E: when a market resolves, all non-null variant rows for its signals
get their direction_correct / brier / P&L / resolved_at filled in."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.mark.asyncio
async def test_record_resolution_fills_all_variants(async_db_factory):
    from app.measurement.pipeline import record_prediction_resolution

    EVENT_ID = 991090
    MARKET_ID = "0xmeasure-resolution-1"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.flush()
        sig = Signal(
            event_id=EVENT_ID, market_id=MARKET_ID, signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6, signal_strength=70.0,
        )
        s.add(sig)
        await s.flush()

        s.add(SignalPrediction(
            signal_id=sig.id, variant="heuristic_v1",
            predicted_direction="BUY_YES", predicted_probability=0.7,
        ))
        s.add(SignalPrediction(
            signal_id=sig.id, variant="baseline_random",
            predicted_direction="BUY_NO", predicted_probability=0.5,
        ))
        s.add(SignalPrediction(
            signal_id=sig.id, variant="baseline_momentum",
            predicted_direction=None, predicted_probability=None,
        ))
        await s.commit()
        sid = sig.id

    try:
        # Market resolved at 1.0 (YES won, clean binary)
        async with async_db_factory() as s:
            await record_prediction_resolution(s, signal_id=sid, price_resolved=1.0)
            await s.commit()

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalars().all()
            by = {r.variant: r for r in rows}

            # 'heuristic_v1' said BUY_YES at 0.7, resolved 1.0
            assert by["heuristic_v1"].direction_correct is True
            assert float(by["heuristic_v1"].brier_score) == pytest.approx((0.7 - 1.0) ** 2, abs=1e-4)
            assert float(by["heuristic_v1"].simulated_pnl_eur) == pytest.approx(3.0, abs=1e-2)
            assert by["heuristic_v1"].resolved_at is not None

            # baseline_random said BUY_NO at 0.5, resolved 1.0 -> wrong
            assert by["baseline_random"].direction_correct is False

            # baseline_momentum had NULL direction -> skipped
            assert by["baseline_momentum"].direction_correct is None
            assert by["baseline_momentum"].resolved_at is None
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.id == sid))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_record_resolution_brier_null_on_ambiguous(async_db_factory):
    from app.measurement.pipeline import record_prediction_resolution

    EVENT_ID = 991091
    MARKET_ID = "0xmeasure-resolution-2"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.flush()
        sig = Signal(
            event_id=EVENT_ID, market_id=MARKET_ID, signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.flush()
        s.add(SignalPrediction(
            signal_id=sig.id, variant="heuristic_v1",
            predicted_direction="BUY_YES", predicted_probability=0.7,
        ))
        await s.commit()
        sid = sig.id

    try:
        # Resolves at 0.7 — ambiguous (between 0.05 and 0.95)
        async with async_db_factory() as s:
            await record_prediction_resolution(s, signal_id=sid, price_resolved=0.7)
            await s.commit()

        async with async_db_factory() as s:
            row = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalar_one()
            assert row.brier_score is None
            # P&L still computed from raw price: 10 * (0.7 - 0.7) = 0
            assert float(row.simulated_pnl_eur) == pytest.approx(0.0, abs=1e-2)
            assert row.resolved_at is not None
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.id == sid))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
