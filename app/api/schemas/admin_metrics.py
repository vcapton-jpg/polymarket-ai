"""Pydantic response schemas for /api/admin/metrics/*."""

from __future__ import annotations

from pydantic import BaseModel


class VariantAggregate(BaseModel):
    variant: str
    n: int                        # resolved rows with non-null direction
    n_coverage: int               # all rows including NULL direction (coverage)
    winrate: float | None
    winrate_ci95_low: float | None
    winrate_ci95_high: float | None
    brier: float | None
    brier_n: int                  # count of rows where brier was defined (binary only)
    pnl_per_trade_eur: float | None
    pnl_total_eur: float | None


class VariantsResponse(BaseModel):
    window: str
    as_of: str
    variants: list[VariantAggregate]


class RollingPoint(BaseModel):
    date: str
    variant: str
    n_cumulative: int
    winrate_cumulative: float | None


class RollingResponse(BaseModel):
    window: str
    step: str
    series: list[RollingPoint]
