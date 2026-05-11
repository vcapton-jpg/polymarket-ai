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


from typing import Protocol


class BaselineFn(Protocol):
    def __call__(self, ctx) -> VariantPrediction: ...  # noqa: D401


class VariantRegistry:
    """Registers baseline and shadow variants by name.

    Baselines are in-band, deterministic, fast — run inside the signal
    transaction. Shadows are async, possibly expensive, run via Celery. The
    registry stores them separately so pipeline.py can dispatch correctly.
    """

    def __init__(self) -> None:
        self._baselines: dict[str, BaselineFn] = {}
        self._shadows: dict[str, BaselineFn] = {}

    def register_baseline(self, name: str, fn: BaselineFn) -> None:
        if name in self._baselines:
            raise ValueError(f"Baseline {name!r} already registered")
        self._baselines[name] = fn

    def register_shadow(self, name: str, fn: BaselineFn) -> None:
        if name in self._shadows:
            raise ValueError(f"Shadow {name!r} already registered")
        self._shadows[name] = fn

    def baselines(self) -> dict[str, BaselineFn]:
        return dict(self._baselines)

    def shadows(self) -> dict[str, BaselineFn]:
        return dict(self._shadows)


_registry = VariantRegistry()


def get_registry() -> VariantRegistry:
    """Module-level singleton used by the signal builder + Celery workers."""
    return _registry
