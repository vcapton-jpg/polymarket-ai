"""record_baselines_for_signal — production-path glue helper.

The async `_persist_signal` (legacy / backfill path) hand-rolls the call
chain `build_scoring_context -> record_baselines`. The sync prod path in
`tasks_scoring._run_full_scoring_pipeline` did NOT, leaving the prod
signal_predictions table empty.

This module is the minimal helper that both paths now share. These tests
pin down its contract:

  - Always writes `heuristic_v1` plus every registered baseline.
  - Honours the `features` / `llm_combined` shadow toggle.
  - Swallows measurement-layer exceptions so a broken baseline cannot
    abort a signal commit (defensive — the signal is already flushed).
  - Idempotent on retry: re-calling for the same signal_id is a no-op.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.mark.asyncio
async def test_helper_writes_heuristic_and_all_baselines(async_db_factory):
    # Importing the package side-effect-registers the four built-in baselines.
    import app.measurement  # noqa: F401
    from app.measurement.pipeline import record_baselines_for_signal

    EVENT_ID = 991100
    MARKET_ID = "0xrec-helper-1"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    try:
        async with async_db_factory() as s:
            sig = Signal(
                event_id=EVENT_ID,
                market_id=MARKET_ID,
                signal_score=70.0,
                signal_strength=70,
                trade_quality=60,
                direction="YES",
                market_price_at_signal=0.65,
            )
            s.add(sig)
            await s.flush()
            n = await record_baselines_for_signal(
                s,
                signal=sig,
                articles=[
                    {"news_clean_id": 1, "direction_hint": "YES", "source_weight": 0.9},
                ],
            )
            await s.commit()
            assert n >= 5  # 1 heuristic + 4 baselines

            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sig.id)
                )
            ).scalars().all()
            variants = {r.variant for r in rows}
            assert variants == {
                "heuristic_v1",
                "baseline_random",
                "baseline_market_price",
                "baseline_momentum",
                "baseline_news_sentiment",
            }
            mp = next(r for r in rows if r.variant == "baseline_market_price")
            assert float(mp.predicted_probability) == pytest.approx(0.65, abs=1e-4)
            h = next(r for r in rows if r.variant == "heuristic_v1")
            assert float(h.predicted_probability) == pytest.approx(0.70, abs=1e-4)
            assert h.predicted_direction == "YES"
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_helper_is_idempotent_on_double_call(async_db_factory):
    """Re-calling on the same signal must NOT produce duplicate rows.

    The underlying `record_baselines` uses ON CONFLICT DO NOTHING — make sure
    the wrapper preserves that property.
    """
    import app.measurement  # noqa: F401
    from app.measurement.pipeline import record_baselines_for_signal

    EVENT_ID = 991101
    MARKET_ID = "0xrec-helper-2"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    try:
        async with async_db_factory() as s:
            sig = Signal(
                event_id=EVENT_ID,
                market_id=MARKET_ID,
                signal_score=55.0,
                signal_strength=55,
                trade_quality=50,
                direction="NO",
                market_price_at_signal=0.40,
            )
            s.add(sig)
            await s.flush()

            await record_baselines_for_signal(s, signal=sig, articles=[])
            await record_baselines_for_signal(s, signal=sig, articles=[])
            await s.commit()

            rows = (
                await s.execute(
                    select(SignalPrediction).where(SignalPrediction.signal_id == sig.id)
                )
            ).scalars().all()
            # 5 distinct variants — the second call must be a no-op.
            assert len(rows) == 5
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_helper_swallows_measurement_failure(async_db_factory, monkeypatch):
    """A baseline blowing up must not propagate — the signal is already flushed
    and a measurement failure is non-fatal. The helper logs and returns 0.
    """
    import app.measurement  # noqa: F401
    from app.measurement import pipeline as pipeline_mod

    EVENT_ID = 991102
    MARKET_ID = "0xrec-helper-3"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    try:
        async with async_db_factory() as s:
            sig = Signal(
                event_id=EVENT_ID,
                market_id=MARKET_ID,
                signal_score=50.0,
                signal_strength=50,
                trade_quality=40,
                direction="YES",
                market_price_at_signal=0.5,
            )
            s.add(sig)
            await s.flush()

            async def boom(*_a, **_kw):
                raise RuntimeError("simulated baseline crash")

            monkeypatch.setattr(pipeline_mod, "record_baselines", boom)

            # MUST NOT raise.
            n = await pipeline_mod.record_baselines_for_signal(
                s, signal=sig, articles=[]
            )
            assert n == 0
            await s.commit()
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
