"""End-to-end: record_baselines must write the correct variants based on the
heuristic_shadow_enabled flag.

Uses a real async DB (Postgres via docker-compose), a registered Signal row,
and a ScoringContext built from the existing builder. No LLM calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, text

from app.core.config import get_settings
from app.db.models import Event, Market, Signal, SignalPrediction
from app.measurement.pipeline import record_baselines
from app.measurement.scoring_context import build_scoring_context
from app.measurement.variant_registry import get_registry


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_signal(session, event_id: int, market_id: str) -> int:
    session.add(Market(market_id=market_id, question="q", active=True))
    session.add(Event(id=event_id, event_title="e"))
    await session.flush()
    sig = Signal(
        event_id=event_id, market_id=market_id, signal_score=80,
        direction="BUY_YES", market_price_at_signal=0.5,
    )
    session.add(sig)
    await session.commit()
    return sig.id


async def _cleanup(session, event_id: int, market_id: str, sig_id: int) -> None:
    await session.execute(delete(SignalPrediction).where(SignalPrediction.signal_id == sig_id))
    await session.execute(delete(Signal).where(Signal.id == sig_id))
    await session.execute(delete(Event).where(Event.id == event_id))
    await session.execute(delete(Market).where(Market.market_id == market_id))
    await session.commit()


@pytest.mark.asyncio
async def test_heuristic_v1_always_written(async_db_factory, monkeypatch):
    """Flag off → heuristic_v1 + 4 baselines, no heuristic_shadow."""
    monkeypatch.setenv("HEURISTIC_SHADOW_ENABLED", "false")
    get_settings.cache_clear()
    import app.measurement  # noqa: F401 — register baselines

    async with async_db_factory() as session:
        sig_id = await _seed_signal(session, event_id=9901, market_id="mkt-shadow-9901")
        try:
            ctx = await build_scoring_context(
                signal_id=sig_id, market_id="mkt-shadow-9901", event_id=9901,
                market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
            )
            await record_baselines(
                session=session,
                signal_id=sig_id,
                ctx=ctx,
                registry=get_registry(),
                features={"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
                          "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
                llm_combined=0.5,
            )
            await session.commit()

            variants = [r[0] for r in (await session.execute(
                text("SELECT variant FROM signal_predictions WHERE signal_id=:sid"),
                {"sid": sig_id},
            )).all()]
            assert "heuristic_v1" in variants
            assert "heuristic_shadow" not in variants
            assert len([v for v in variants if v.startswith("baseline_")]) == 4
        finally:
            await _cleanup(session, event_id=9901, market_id="mkt-shadow-9901", sig_id=sig_id)


@pytest.mark.asyncio
async def test_heuristic_shadow_written_when_flag_on(async_db_factory, monkeypatch):
    """Flag on → heuristic_v1 + heuristic_shadow + 4 baselines."""
    monkeypatch.setenv("HEURISTIC_SHADOW_ENABLED", "true")
    get_settings.cache_clear()
    import app.measurement  # noqa: F401

    async with async_db_factory() as session:
        sig_id = await _seed_signal(session, event_id=9902, market_id="mkt-shadow-9902")
        try:
            ctx = await build_scoring_context(
                signal_id=sig_id, market_id="mkt-shadow-9902", event_id=9902,
                market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
            )
            await record_baselines(
                session=session,
                signal_id=sig_id,
                ctx=ctx,
                registry=get_registry(),
                features={"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
                          "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
                llm_combined=0.5,
            )
            await session.commit()

            variants = [r[0] for r in (await session.execute(
                text("SELECT variant FROM signal_predictions WHERE signal_id=:sid"),
                {"sid": sig_id},
            )).all()]
            assert "heuristic_v1" in variants
            assert "heuristic_shadow" in variants
            assert len([v for v in variants if v.startswith("baseline_")]) == 4
        finally:
            await _cleanup(session, event_id=9902, market_id="mkt-shadow-9902", sig_id=sig_id)


@pytest.mark.asyncio
async def test_shadow_probability_differs_when_settings_override_weights(
    async_db_factory, monkeypatch,
):
    """Shadow weights diverge from v1 → probabilities differ."""
    monkeypatch.setenv("HEURISTIC_SHADOW_ENABLED", "true")
    monkeypatch.setenv("HEURISTIC_W_FRESHNESS", "0.50")
    monkeypatch.setenv("HEURISTIC_W_SOURCE", "0.10")
    monkeypatch.setenv("HEURISTIC_W_CONFIRMATION", "0.15")
    monkeypatch.setenv("HEURISTIC_W_LLM", "0.25")
    get_settings.cache_clear()
    import app.measurement  # noqa: F401

    async with async_db_factory() as session:
        sig_id = await _seed_signal(session, event_id=9903, market_id="mkt-shadow-9903")
        try:
            ctx = await build_scoring_context(
                signal_id=sig_id, market_id="mkt-shadow-9903", event_id=9903,
                market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
            )
            # freshness=1.0 dominates shadow (w=0.50); v1 weights freshness=0.15
            # and llm=0.60 with llm_combined=0.0 → v1 gets less strength → probs differ
            await record_baselines(
                session=session, signal_id=sig_id, ctx=ctx,
                registry=get_registry(),
                features={"freshness": 1.0, "source_weight": 0.1, "confirmation": 0.1,
                          "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
                llm_combined=0.0,
            )
            await session.commit()

            rows = {r[0]: float(r[1]) for r in (await session.execute(
                text("SELECT variant, predicted_probability FROM signal_predictions "
                     "WHERE signal_id=:sid AND variant LIKE 'heuristic_%'"),
                {"sid": sig_id},
            )).all()}
            assert rows["heuristic_v1"] != pytest.approx(rows["heuristic_shadow"], abs=1e-4)
        finally:
            await _cleanup(session, event_id=9903, market_id="mkt-shadow-9903", sig_id=sig_id)
