"""P1.2 (audit 2026-04-25): `heuristic_v1` baseline must use the composed
top-level `signal_score` (= 0.75*strength + 0.25*trade_quality), NOT the
raw `signal_strength` sub-component.

Background: the heuristic scorer composes a final `signal_score` from
strength + trade_quality. The measurement layer's `heuristic_v1` variant
historically read `sig.signal_strength` — only one of the two components.
For sync-built signals this throws away the trade-quality contribution;
for async-built signals (post P0-1) strength == score == trade so it's
moot, but the spec must lock in the composed-score reading regardless.

This test seeds a Signal with strength != trade != score and asserts the
heuristic_v1 prediction tracks `signal_score / 100`, not `signal_strength`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select


@pytest.mark.asyncio
async def test_heuristic_v1_reads_composed_signal_score(async_db_factory):
    from datetime import datetime, timezone

    from app.db.models import Event, Market, Signal, SignalPrediction
    from app.measurement.pipeline import record_baselines
    from app.measurement.scoring_context import ArticleImpact, ScoringContext
    from app.measurement.variant_registry import VariantRegistry

    MARKET_ID = "0xheuristic-v1-composed-1"
    EVENT_ID = 991210

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.flush()
        # signal_score = 70 ≠ signal_strength = 90 so we can tell which
        # column heuristic_v1 reads.
        sig = Signal(
            event_id=EVENT_ID, market_id=MARKET_ID,
            signal_score=70, signal_strength=90, trade_quality=10,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.flush()
        sid = sig.id

        ctx = ScoringContext(
            signal_id=sid, market_id=MARKET_ID, event_id=EVENT_ID,
            market_price=0.6, market_price_24h_ago=0.5,
            article_impacts=(ArticleImpact(direction="YES", source_weight=0.8),),
            t0=datetime(2026, 4, 25, tzinfo=timezone.utc),
        )
        await record_baselines(s, signal_id=sid, ctx=ctx, registry=VariantRegistry())
        await s.commit()

    try:
        async with async_db_factory() as s:
            row = (await s.execute(
                select(SignalPrediction).where(
                    SignalPrediction.signal_id == sid,
                    SignalPrediction.variant == "heuristic_v1",
                )
            )).scalar_one()
            # PIN (P1.2): probability must equal signal_score / 100, NOT
            # signal_strength / 100. With score=70 / strength=90 the two
            # readings give very different answers (0.7 vs 0.9).
            assert float(row.predicted_probability) == pytest.approx(0.70, abs=1e-6), (
                f"heuristic_v1 read the wrong column: got "
                f"{float(row.predicted_probability)}, expected 0.70 "
                "(= signal_score / 100). Audit 2026-04-25 P1.2."
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
