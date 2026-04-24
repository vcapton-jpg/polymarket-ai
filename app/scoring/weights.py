# app/scoring/weights.py
"""Frozen dataclass holding the 9 knobs of the heuristic scorer.

Why frozen: the scorer is shared across threads (FastAPI + Celery workers).
Accidentally mutating `self.weights.w_llm` mid-request would be a nightmare
to debug. Freezing forbids that at the language level.

Sum invariants: each of the 3 blocs (strength / trade / top) must sum to
1.0 within 1e-6. Violations raise ValueError at construction — we'd rather
crash on startup than score with a malformed vector.

Chantier #5 entry point. Replaces the hand-picked dicts in
`HeuristicScorer.__init__`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeuristicWeights:
    # strength bloc: freshness + source + confirmation + llm must sum to 1.0
    w_freshness: float = 0.15
    w_source: float = 0.10
    w_confirmation: float = 0.15
    w_llm: float = 0.60

    # trade bloc: liquidity + spread + time_to_resolution must sum to 1.0
    w_liquidity: float = 0.40
    w_spread: float = 0.35
    w_time_to_resolution: float = 0.25

    # top-level combination: strength + trade must sum to 1.0
    strength_weight: float = 0.75
    trade_weight: float = 0.25

    def __post_init__(self) -> None:
        strength_sum = self.w_freshness + self.w_source + self.w_confirmation + self.w_llm
        trade_sum = self.w_liquidity + self.w_spread + self.w_time_to_resolution
        top_sum = self.strength_weight + self.trade_weight

        for name, total in (
            ("strength_weights", strength_sum),
            ("trade_weights", trade_sum),
            ("top_weights", top_sum),
        ):
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"{name} sum to {total:.6f}, expected 1.0 (±1e-6)"
                )

    @classmethod
    def frozen_v1(cls) -> "HeuristicWeights":
        """Snapshot of the chantier #5 launch weights.

        Anchor point for `heuristic_v1` measurement. Never edit — if the
        tuner produces a winner, introduce `HeuristicWeights.frozen_v2()`
        rather than mutating this.
        """
        return cls()

    @classmethod
    def load_from_settings(cls, settings) -> "HeuristicWeights":
        """Build from Settings overrides; fall back to defaults per field.

        Settings fields: heuristic_w_freshness, heuristic_w_source,
        heuristic_w_confirmation, heuristic_w_llm, heuristic_w_liquidity,
        heuristic_w_spread, heuristic_w_time_to_resolution,
        heuristic_strength_weight, heuristic_trade_weight.
        """
        return cls(
            w_freshness=getattr(settings, "heuristic_w_freshness", cls.w_freshness),
            w_source=getattr(settings, "heuristic_w_source", cls.w_source),
            w_confirmation=getattr(settings, "heuristic_w_confirmation", cls.w_confirmation),
            w_llm=getattr(settings, "heuristic_w_llm", cls.w_llm),
            w_liquidity=getattr(settings, "heuristic_w_liquidity", cls.w_liquidity),
            w_spread=getattr(settings, "heuristic_w_spread", cls.w_spread),
            w_time_to_resolution=getattr(
                settings, "heuristic_w_time_to_resolution", cls.w_time_to_resolution
            ),
            strength_weight=getattr(settings, "heuristic_strength_weight", cls.strength_weight),
            trade_weight=getattr(settings, "heuristic_trade_weight", cls.trade_weight),
        )
