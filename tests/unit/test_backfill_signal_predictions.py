from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, Market, Signal, SignalOutcome, SignalPrediction


async def _cleanup(async_db_factory, event_id, market_id):
    async with async_db_factory() as s:
        await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(
            select(Signal.id).where(Signal.event_id == event_id)
        )))
        await s.execute(delete(SignalOutcome).where(SignalOutcome.signal_id.in_(
            select(Signal.id).where(Signal.event_id == event_id)
        )))
        await s.execute(delete(Signal).where(Signal.event_id == event_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.execute(delete(Market).where(Market.market_id == market_id))
        await s.commit()


@pytest.mark.asyncio
async def test_backfill_creates_variant_rows_for_historical_signal(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    await _cleanup(async_db_factory, 501, "0xbk1")
    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xbk1", question="q", active=True))
            s.add(Event(id=501, event_title="e"))
            await s.flush()
            sig = Signal(
                event_id=501, market_id="0xbk1", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
                signal_strength=70.0,
            )
            s.add(sig)
            await s.commit()
            sid = sig.id

        # Limit backfill to just our signal via since=<signal created_at>
        stats = await backfill(dry_run=False, since=None, batch_size=100)
        assert stats["signals_processed"] >= 1

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
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
    finally:
        await _cleanup(async_db_factory, 501, "0xbk1")


@pytest.mark.asyncio
async def test_backfill_is_idempotent(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    await _cleanup(async_db_factory, 502, "0xbk2")
    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xbk2", question="q", active=True))
            s.add(Event(id=502, event_title="e"))
            await s.flush()
            sig = Signal(
                event_id=502, market_id="0xbk2", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
            )
            s.add(sig)
            await s.commit()
            sid = sig.id

        await backfill(dry_run=False, since=None, batch_size=100)
        await backfill(dry_run=False, since=None, batch_size=100)  # second run

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalars().all()
        assert len(rows) == 5
    finally:
        await _cleanup(async_db_factory, 502, "0xbk2")


@pytest.mark.asyncio
async def test_backfill_resolves_when_outcome_present(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    await _cleanup(async_db_factory, 503, "0xbk3")
    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xbk3", question="q", active=True))
            s.add(Event(id=503, event_title="e"))
            await s.flush()
            sig = Signal(
                event_id=503, market_id="0xbk3", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
            )
            s.add(sig)
            await s.flush()
            s.add(SignalOutcome(signal_id=sig.id, price_resolved=1.0))
            await s.commit()
            sid = sig.id

        await backfill(dry_run=False, since=None, batch_size=100)

        async with async_db_factory() as s:
            sig_row = (
                await s.execute(
                    select(SignalPrediction).where(
                        SignalPrediction.signal_id == sid,
                        SignalPrediction.variant == "signal",
                    )
                )
            ).scalar_one()
        assert sig_row.resolved_at is not None
        assert sig_row.direction_correct is True
    finally:
        await _cleanup(async_db_factory, 503, "0xbk3")


@pytest.mark.asyncio
async def test_backfill_dry_run_writes_nothing(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    await _cleanup(async_db_factory, 504, "0xbk4")
    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xbk4", question="q", active=True))
            s.add(Event(id=504, event_title="e"))
            await s.flush()
            sig = Signal(
                event_id=504, market_id="0xbk4", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
            )
            s.add(sig)
            await s.commit()
            sid = sig.id

        stats = await backfill(dry_run=True, since=None, batch_size=100)

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sid)
                )
            ).scalars().all()
        assert len(rows) == 0
        assert stats["dry_run"] is True
    finally:
        await _cleanup(async_db_factory, 504, "0xbk4")
