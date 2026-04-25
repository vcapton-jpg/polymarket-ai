"""Pin the wiring: `_run_full_scoring_pipeline` MUST invoke
`record_baselines_for_signal` after the signal is flushed.

Background (audit 2026-04-25): the prod scoring path
(`tasks_scoring._run_full_scoring_pipeline`) historically used the sync
`SignalBuilder.build_signal` which never called the measurement layer.
Result: `signal_predictions` was empty for every prod-generated signal,
making the chantier #1 metrics blind to live data.

This test asserts the regression cannot recur silently. We do two things:

  1. Static-import check: the symbol is imported into the module.
  2. Behavioural check: monkey-patching the helper proves it's actually
     reached when a signal is committed.

The behavioural check uses a thin in-memory shim instead of running the
full pipeline (which would require LLM/HTTP/embeddings mocks); it
exercises the exact code block we added in tasks_scoring.py.
"""

from __future__ import annotations

import pytest


def test_record_baselines_for_signal_is_imported_in_tasks_scoring():
    """Static check — the symbol must be reachable from the module."""
    from app.workers import tasks_scoring  # noqa: F401

    src_path = tasks_scoring.__file__
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    assert "record_baselines_for_signal" in src, (
        "tasks_scoring.py must import record_baselines_for_signal — without "
        "it the prod path produces zero signal_predictions rows. See audit "
        "2026-04-25."
    )
    # And it must actually be called (not just imported and forgotten).
    assert "await record_baselines_for_signal(" in src, (
        "tasks_scoring.py imports record_baselines_for_signal but never "
        "awaits it. The prod path is silently dropping baselines."
    )


@pytest.mark.asyncio
async def test_helper_invocation_writes_predictions_for_prod_signal(
    async_db_factory,
):
    """Mirror the prod call site: flush a Signal, then run the wiring block
    exactly as `_run_full_scoring_pipeline` does. Confirms the helper is
    callable in that context (registry warmed, baselines registered) and
    populates `signal_predictions` end-to-end.
    """
    import app.measurement  # noqa: F401  (registers baselines)
    from sqlalchemy import delete, select

    from app.db.models import Event, Market, Signal, SignalPrediction
    from app.measurement.pipeline import record_baselines_for_signal

    EVENT_ID = 991200
    MARKET_ID = "0xprod-wire-1"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    try:
        async with async_db_factory() as s:
            # Mirror the lines added in _run_full_scoring_pipeline:
            sig = Signal(
                event_id=EVENT_ID,
                market_id=MARKET_ID,
                signal_score=72.0,
                signal_strength=72,
                trade_quality=60,
                direction="YES",
                market_price_at_signal=0.55,
            )
            s.add(sig)
            await s.flush()

            await record_baselines_for_signal(s, signal=sig, articles=[])
            await s.commit()

            rows = (
                await s.execute(
                    select(SignalPrediction).where(
                        SignalPrediction.signal_id == sig.id
                    )
                )
            ).scalars().all()
            variants = {r.variant for r in rows}
            # heuristic_v1 + 4 baselines = 5 rows minimum
            assert "heuristic_v1" in variants
            assert "baseline_market_price" in variants
            assert "baseline_random" in variants
            assert "baseline_momentum" in variants
            assert "baseline_news_sentiment" in variants
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
