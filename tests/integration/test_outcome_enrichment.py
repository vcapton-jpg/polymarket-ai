"""Integration tests for outcome explainer enrichment + /outcome/viewed marker."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, select

from app.api.main import app
from app.db.models import (
    Event,
    Market,
    OutcomeView,
    Signal,
    SignalOutcome,
)


async def _seed_resolved_signal(
    async_db_factory,
    *,
    direction: str,
    base_price: float,
    final_price: float,
    direction_correct: bool = True,
) -> tuple[int, str, int]:
    """Seed a Market, Event, Signal, SignalOutcome. Returns (signal_id, market_id, event_id)."""
    market_id = f"0xoutcome-{uuid.uuid4().hex[:10]}"
    async with async_db_factory() as s:
        mkt = Market(
            market_id=market_id, question="outcome test", active=False, closed=True
        )
        s.add(mkt)
        ev = Event(
            event_title="outcome-ev",
            event_summary="summary",
            bucket="politics",
        )
        s.add(ev)
        await s.commit()
        await s.refresh(ev)
        sig = Signal(
            event_id=ev.id,
            market_id=market_id,
            signal_score=80.0,
            direction=direction,
            market_price_at_signal=base_price,
        )
        s.add(sig)
        await s.commit()
        await s.refresh(sig)
        s.add(
            SignalOutcome(
                signal_id=sig.id,
                price_resolved=final_price,
                direction_correct=direction_correct,
            )
        )
        await s.commit()
        return sig.id, market_id, ev.id


async def _cleanup(async_db_factory, signal_id: int, market_id: str, event_id: int):
    async with async_db_factory() as s:
        await s.execute(
            delete(OutcomeView).where(OutcomeView.signal_id == signal_id)
        )
        await s.execute(
            delete(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        )
        await s.execute(delete(Signal).where(Signal.id == signal_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.execute(delete(Market).where(Market.market_id == market_id))
        await s.commit()


@pytest.mark.asyncio
async def test_resolved_signal_returns_outcome_explainer(
    async_db_factory, auth_headers_for_user
):
    sig_id, mkt, ev_id = await _seed_resolved_signal(
        async_db_factory,
        direction="BUY_YES",
        base_price=0.30,
        final_price=0.75,
        direction_correct=True,
    )
    uid, headers = await auth_headers_for_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get(f"/api/signals/{sig_id}", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["outcome"] is not None
        assert data["outcome"]["directionCorrect"] is True
        assert abs(data["outcome"]["finalPrice"] - 0.75) < 1e-6
        assert abs(data["outcome"]["basePrice"] - 0.30) < 1e-6
        assert data["outcome"]["movePct"] is not None
        assert data["outcome"]["movePct"] > 0
        assert "learningPoint" in data["outcome"]
        assert len(data["outcome"]["learningPoint"]) > 10
    finally:
        await _cleanup(async_db_factory, sig_id, mkt, ev_id)


@pytest.mark.asyncio
async def test_unresolved_signal_has_null_outcome(
    async_db_factory, auth_headers_for_user
):
    """A signal without a SignalOutcome row should return outcome: null."""
    market_id = f"0xoutcome-{uuid.uuid4().hex[:10]}"
    async with async_db_factory() as s:
        mkt = Market(
            market_id=market_id, question="noout", active=True, closed=False
        )
        s.add(mkt)
        ev = Event(
            event_title="unresolved-ev", event_summary="s", bucket="politics"
        )
        s.add(ev)
        await s.commit()
        await s.refresh(ev)
        sig = Signal(
            event_id=ev.id,
            market_id=market_id,
            signal_score=70.0,
            direction="BUY_NO",
            market_price_at_signal=0.5,
        )
        s.add(sig)
        await s.commit()
        await s.refresh(sig)
        sig_id, ev_id = sig.id, ev.id

    uid, headers = await auth_headers_for_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get(f"/api/signals/{sig_id}", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["outcome"] is None
    finally:
        await _cleanup(async_db_factory, sig_id, market_id, ev_id)


@pytest.mark.asyncio
async def test_mark_outcome_viewed_idempotent(
    async_db_factory, auth_headers_for_user
):
    sig_id, mkt, ev_id = await _seed_resolved_signal(
        async_db_factory,
        direction="BUY_NO",
        base_price=0.60,
        final_price=0.20,
        direction_correct=True,
    )
    uid, headers = await auth_headers_for_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r1 = await c.post(
                f"/api/signals/{sig_id}/outcome/viewed", headers=headers
            )
            r2 = await c.post(
                f"/api/signals/{sig_id}/outcome/viewed", headers=headers
            )
        assert r1.status_code == 204
        assert r2.status_code == 204

        async with async_db_factory() as s:
            rows = (
                await s.execute(
                    select(OutcomeView).where(
                        OutcomeView.user_id == uid,
                        OutcomeView.signal_id == sig_id,
                    )
                )
            ).scalars().all()
        assert len(rows) == 1  # idempotent
    finally:
        await _cleanup(async_db_factory, sig_id, mkt, ev_id)
