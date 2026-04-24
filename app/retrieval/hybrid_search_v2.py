"""Hybrid search v2 — v1 + date-proximity + bucket-match.

The main entry point `hybrid_search_markets_v2` is defined in task 5.
This module lands in two steps so the pure helpers can be TDD'd first.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional


def date_proximity(
    market_end_date: Optional[datetime],
    event_last_seen: datetime,
    tau_days: float,
) -> float:
    """Exponential decay past a 7-day floor; 0 if the market is already past.

    Returns 1.0 when the market ends within 7 days of the event, then decays
    as exp(-(days_until - 7) / tau_days). Returns 0.0 when end_date is None
    or already past.
    """
    if market_end_date is None:
        return 0.0
    days_until = (market_end_date - event_last_seen).total_seconds() / 86400.0
    if days_until < 0:
        return 0.0
    if days_until <= 7.0:
        return 1.0
    if tau_days <= 0:
        return 0.0
    return math.exp(-(days_until - 7.0) / tau_days)


def bucket_match(market_bucket: Optional[str], event_bucket: Optional[str]) -> float:
    """1.0 iff both are the same real bucket; 0.0 for None/other/mismatch."""
    if event_bucket is None or event_bucket == "other":
        return 0.0
    if market_bucket is None:
        return 0.0
    return 1.0 if market_bucket == event_bucket else 0.0


async def hybrid_search_markets_v2(*args, **kwargs):  # pragma: no cover
    raise NotImplementedError("hybrid_search_markets_v2 is implemented in task 5")
