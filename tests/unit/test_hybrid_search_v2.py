"""Tests for hybrid_search_v2 — helper functions + v1-equivalence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


# ═══════════════════ date_proximity ═══════════════════

def test_date_proximity_none_end_date_returns_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    assert date_proximity(market_end_date=None, event_last_seen=_utc(2026, 4, 25), tau_days=14) == 0.0


def test_date_proximity_past_end_date_returns_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 4, 20),
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == 0.0


def test_date_proximity_within_7_days_returns_one():
    """Within the 7-day floor, decay = exp(0) = 1."""
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 5, 1),  # 6 days after event
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == pytest.approx(1.0)


def test_date_proximity_decays_exponentially():
    """21 days out, tau=14 → exp(-(21-7)/14) = exp(-1) ≈ 0.3679."""
    import math
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 5, 16),  # 21 days after event
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == pytest.approx(math.exp(-1.0), rel=1e-3)


def test_date_proximity_far_future_approaches_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2027, 4, 25),  # 365 days out
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got < 1e-10


# ═══════════════════ bucket_match ═══════════════════

def test_bucket_match_same_bucket_returns_one():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="politics", event_bucket="politics") == 1.0


def test_bucket_match_different_bucket_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="sports", event_bucket="politics") == 0.0


def test_bucket_match_event_bucket_none_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="politics", event_bucket=None) == 0.0


def test_bucket_match_event_bucket_other_returns_zero():
    """'other' is not a real bucket — refuse to match on it."""
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="other", event_bucket="other") == 0.0


def test_bucket_match_market_bucket_none_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket=None, event_bucket="politics") == 0.0
