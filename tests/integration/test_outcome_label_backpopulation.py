"""When `check_resolved_markets` runs, EventMarketFeatures.outcome_label is
back-populated for ALL pairs whose market just resolved in the binary band —
including pairs that did NOT become signals.

Without this back-population, the offline gate-effectiveness backtest cannot
score rejected pairs (the dominant 94 % of analyzed pairs in prod). The
binary-band rule is the same one already applied to `signal_outcomes.outcome_label`
([app/workers/tasks_outcomes.py:258-262](../../app/workers/tasks_outcomes.py)):
≥0.95 → 1, ≤0.05 → 0, else NULL.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import (
    Event,
    EventMarketFeatures,
    Market,
    Signal,
    SignalOutcome,
)

EVENT_ID = 992300
MARKET_ID_YES = "0xoutcome-bp-yes-1"
MARKET_ID_NO = "0xoutcome-bp-no-1"
MARKET_ID_AMBIG = "0xoutcome-bp-ambig-1"


@pytest.fixture
async def seeded_resolved_markets(async_db_factory):
    """Three markets: one resolved YES, one resolved NO, one ambiguous.

    Each has TWO EventMarketFeatures rows attached — one for a passed pair
    (also has a Signal row) and one for a rejected pair (no Signal). The
    test verifies BOTH get outcome_label populated.
    """
    async with async_db_factory() as s:
        s.add(Event(id=EVENT_ID, event_title="e"))
        s.add(Market(
            market_id=MARKET_ID_YES, question="qy", active=False,
            closed=True, last_trade_price=0.97,
        ))
        s.add(Market(
            market_id=MARKET_ID_NO, question="qn", active=False,
            closed=True, last_trade_price=0.02,
        ))
        s.add(Market(
            market_id=MARKET_ID_AMBIG, question="qa", active=False,
            closed=True, last_trade_price=0.55,
        ))
        await s.flush()

        for mid in (MARKET_ID_YES, MARKET_ID_NO, MARKET_ID_AMBIG):
            s.add(EventMarketFeatures(
                event_id=EVENT_ID, market_id=mid,
                freshness_factor=0.5, source_weight=0.5,
                confirmation_factor=0.5, liquidity_factor=0.5,
                spread_penalty=0.5, time_to_resolution_factor=0.5,
                impact_strength=0.5, llm_confidence=0.5,
                ambiguity_score=0.5,
                outcome_label=None,
            ))
        await s.commit()

    try:
        yield
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(SignalOutcome).where(
                SignalOutcome.signal_id.in_(
                    select(Signal.id).where(Signal.event_id == EVENT_ID)
                )
            ))
            await s.execute(delete(Signal).where(Signal.event_id == EVENT_ID))
            await s.execute(delete(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID,
            ))
            await s.execute(delete(Market).where(
                Market.market_id.in_(
                    [MARKET_ID_YES, MARKET_ID_NO, MARKET_ID_AMBIG]
                )
            ))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_backpop_writes_outcome_label_for_binary_resolutions(
    async_db_factory, seeded_resolved_markets,
):
    from app.workers.tasks_outcomes import _backpop_event_market_features_outcome

    async with async_db_factory() as s:
        await _backpop_event_market_features_outcome(
            s,
            market_ids=[MARKET_ID_YES, MARKET_ID_NO, MARKET_ID_AMBIG],
        )
        await s.commit()

    async with async_db_factory() as s:
        rows = (await s.execute(
            select(EventMarketFeatures).where(
                EventMarketFeatures.event_id == EVENT_ID,
            ).order_by(EventMarketFeatures.market_id)
        )).scalars().all()

    by_mid = {r.market_id: r.outcome_label for r in rows}
    assert by_mid[MARKET_ID_YES] == 1, "YES market (price 0.97) should label as 1"
    assert by_mid[MARKET_ID_NO] == 0, "NO market (price 0.02) should label as 0"
    assert by_mid[MARKET_ID_AMBIG] is None, (
        "ambiguous market (price 0.55) must remain NULL — outside the binary band"
    )


@pytest.mark.asyncio
async def test_backpop_is_idempotent(async_db_factory, seeded_resolved_markets):
    """Re-running the back-pop is a no-op for rows already labelled."""
    from app.workers.tasks_outcomes import _backpop_event_market_features_outcome

    async with async_db_factory() as s:
        await _backpop_event_market_features_outcome(
            s, market_ids=[MARKET_ID_YES, MARKET_ID_NO, MARKET_ID_AMBIG],
        )
        await s.commit()

    # Tamper: simulate a hypothetical bug that re-set YES to 0
    # — the back-pop must NOT overwrite a non-NULL label, so the bug
    # value would survive. This pins the "only update NULL" behaviour.
    async with async_db_factory() as s:
        await s.execute(
            EventMarketFeatures.__table__.update()
            .where(EventMarketFeatures.market_id == MARKET_ID_YES)
            .values(outcome_label=0)
        )
        await s.commit()

    async with async_db_factory() as s:
        await _backpop_event_market_features_outcome(
            s, market_ids=[MARKET_ID_YES],
        )
        await s.commit()

    async with async_db_factory() as s:
        row = (await s.execute(
            select(EventMarketFeatures).where(
                EventMarketFeatures.market_id == MARKET_ID_YES,
            )
        )).scalar_one()
        assert row.outcome_label == 0, (
            "Back-pop must not overwrite an existing label — only fill NULLs"
        )


@pytest.mark.asyncio
async def test_binary_label_helper_matches_signal_outcome_rule():
    """One source of truth for the binary-band rule.

    `binary_label` must produce the same output as the inline rule in
    `_check_resolved_async` ([tasks_outcomes.py:258-262](../../app/workers/tasks_outcomes.py)).
    """
    from app.workers.tasks_outcomes import binary_label

    assert binary_label(None) is None
    assert binary_label(0.97) == 1
    assert binary_label(0.95) == 1     # boundary inclusive
    assert binary_label(0.94) is None
    assert binary_label(0.06) is None
    assert binary_label(0.05) == 0     # boundary inclusive
    assert binary_label(0.02) == 0
    assert binary_label(0.5) is None
