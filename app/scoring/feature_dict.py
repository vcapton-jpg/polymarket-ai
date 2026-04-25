"""Shared feature-dict builder.

Single source of truth for the 6-key heuristic feature dict consumed by
`HeuristicScorer.compute_score`. Extracted from
`SignalBuilder.build_signal` so the same shape can also be persisted to
`event_market_features` from `tasks_scoring.py` for both passed and
rejected (event, market) pairs — the input the offline gate-effectiveness
backtest needs.

The contract is pinned by `tests/unit/scoring/test_feature_dict.py`: any
change here must move that test in the same PR.
"""
from __future__ import annotations

from datetime import datetime

from app.scoring.feature_builder import FeatureBuilder, create_feature_builder


def build_feature_dict(
    *,
    event_data: dict,
    market_data: dict,
    ref_dt: datetime,
    source_count: int,
    feature_builder: FeatureBuilder | None = None,
) -> dict[str, float]:
    fb = feature_builder or create_feature_builder()
    return {
        "freshness": fb.build_freshness_factor(ref_dt),
        "source_weight": fb.build_source_weight(
            event_data.get("source_weight", 0.5)
        ),
        "confirmation": fb.build_confirmation_factor(
            source_count,
            source_tier=event_data.get("source_tier", 2),
        ),
        "liquidity": fb.build_liquidity_factor(market_data.get("liquidity")),
        "spread": fb.build_spread_penalty(market_data.get("spread")),
        "time_to_resolution": fb.build_time_to_resolution_factor(
            market_data.get("end_date"),
        ),
    }
