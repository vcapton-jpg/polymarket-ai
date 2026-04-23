"""Variant registry — enumeration only. Execution lives in pipeline.py.

A 'variant' is a named predictor: the production signal, the 4 baselines, and
(future chantiers) shadow LLM / retrieval variants. Each variant produces a
VariantPrediction from a ScoringContext.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariantPrediction:
    """A direction + probability emitted by a single variant.

    Both fields may be None when the variant lacks data (e.g. momentum with no
    24h price history). A None row is still inserted — presence is coverage
    proof; aggregation queries filter it out.
    """
    direction: str | None       # 'BUY_YES' | 'BUY_NO' | None
    probability: float | None   # P(YES) in [0, 1] or None
