"""Persist EventMarketFeatures rows for every analyzed (event, market) pair.

Pre-fix bug (data audit 2026-04-25): the prod scoring path computed the
6 backend features (freshness, source_weight, confirmation, liquidity,
spread, time_to_resolution) and 3 LLM features (impact_strength,
llm_confidence, ambiguity_score) inline inside `SignalBuilder.build_signal`
but never persisted them. The `event_market_features` table existed but
held 0 rows in production (vs. 5 425 `event_market_analysis` rows). That
broke the offline gate-effectiveness backtest, which needs at-time
features for every analyzed pair — passed AND rejected.

Post-fix contract: `tasks_scoring` calls `upsert_event_market_features`
once per `(event_id, market_id)` whose LLM analysis ran. Idempotent
under retries via PostgreSQL `INSERT ... ON CONFLICT (event_id,
market_id) DO UPDATE`.

The `outcome_label` column is intentionally NOT written here — that's
filled later by `tasks_outcomes.check_resolved_markets` when the market
resolves in the binary band.
"""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventMarketFeatures


async def upsert_event_market_features(
    session: AsyncSession,
    *,
    event_id: int,
    market_id: str,
    features: dict[str, float],
    impact_strength: float | None,
    llm_confidence: float | None,
    ambiguity_score: float | None,
) -> None:
    """Insert or update the features row for one (event_id, market_id).

    `features` is the 6-key dict produced by `build_feature_dict` in
    `app.scoring.feature_dict`. The 3 LLM features come from the
    `EventMarketAnalysis` row associated with the same pair.

    The caller controls the transaction boundary — this function does
    NOT call `session.commit()` so it composes inside the existing
    Celery task transaction.
    """
    payload = {
        "event_id": event_id,
        "market_id": market_id,
        "freshness_factor": features["freshness"],
        "source_weight": features["source_weight"],
        "confirmation_factor": features["confirmation"],
        "liquidity_factor": features["liquidity"],
        "spread_penalty": features["spread"],
        "time_to_resolution_factor": features["time_to_resolution"],
        "impact_strength": impact_strength,
        "llm_confidence": llm_confidence,
        "ambiguity_score": ambiguity_score,
    }

    stmt = insert(EventMarketFeatures).values(**payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_event_market_features",
        set_={
            "freshness_factor": stmt.excluded.freshness_factor,
            "source_weight": stmt.excluded.source_weight,
            "confirmation_factor": stmt.excluded.confirmation_factor,
            "liquidity_factor": stmt.excluded.liquidity_factor,
            "spread_penalty": stmt.excluded.spread_penalty,
            "time_to_resolution_factor": stmt.excluded.time_to_resolution_factor,
            "impact_strength": stmt.excluded.impact_strength,
            "llm_confidence": stmt.excluded.llm_confidence,
            "ambiguity_score": stmt.excluded.ambiguity_score,
            # outcome_label deliberately omitted — set by tasks_outcomes only.
        },
    )
    await session.execute(stmt)
