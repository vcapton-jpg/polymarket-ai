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


# ═══════════════════ hybrid_search_markets_v2 ═══════════════════

from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def _fake_vector_rows():
    """Two candidate markets: m1 scores higher cosine, m2 ends sooner."""
    return [
        {
            "market_id": "m1",
            "question": "Will Macron survive 2026?",
            "category": "politics",
            "end_date": _utc(2026, 12, 31),
            "liquidity": 1000, "volume_24h": 100,
            "best_bid": 0.5, "best_ask": 0.52, "spread": 0.02, "last_trade_price": 0.51,
            "market_retrieval_text": "macron survive 2026",
            "cosine_score": 0.80,
            "bucket": "politics",
        },
        {
            "market_id": "m2",
            "question": "Will France pass law X?",
            "category": "politics",
            "end_date": _utc(2026, 5, 1),  # ends soon
            "liquidity": 500, "volume_24h": 50,
            "best_bid": 0.3, "best_ask": 0.33, "spread": 0.03, "last_trade_price": 0.31,
            "market_retrieval_text": "france law x",
            "cosine_score": 0.70,
            "bucket": "politics",
        },
    ]


@pytest.mark.asyncio
async def test_v2_equivalence_when_w_date_and_w_bucket_zero(monkeypatch, _fake_vector_rows):
    """When w_date = w_bucket = 0, v2 must rank identically to v1 on a shared pool."""
    # Both variants see the same vector pool.
    _mock = AsyncMock(return_value=_fake_vector_rows)
    monkeypatch.setattr(
        "app.retrieval.vector_retriever.search_markets_by_embedding",
        _mock,
    )
    # v1 uses a direct `from ... import` binding; patch its local name too so the
    # test is order-independent when hybrid_search is already cached in sys.modules.
    monkeypatch.setattr(
        "app.retrieval.hybrid_search.search_markets_by_embedding",
        _mock,
    )
    get_settings_cache_clear = _clear_settings()

    from app.retrieval.hybrid_search import hybrid_search_markets as v1
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2 as v2
    session = MagicMock()
    v1_out = await v1(session, [0.0] * 1536, "macron france 2026",
                     event_bucket="politics", event_entities=["Macron"])
    v2_out = await v2(session, [0.0] * 1536, "macron france 2026",
                     event_bucket="politics", event_entities=["Macron"],
                     event_last_seen=_utc(2026, 4, 25))

    assert [r["market_id"] for r in v1_out] == [r["market_id"] for r in v2_out], (
        f"v1 order {[r['market_id'] for r in v1_out]} != v2 order {[r['market_id'] for r in v2_out]}"
    )


@pytest.mark.asyncio
async def test_v2_date_proximity_flips_tie(monkeypatch, _fake_vector_rows):
    """With equal vector ranks and w_date=1.0, the nearer-end-date market wins."""
    # Force equal cosine so RRF is a pure tiebreak by date.
    rows = [dict(r, cosine_score=0.75) for r in _fake_vector_rows]
    monkeypatch.setattr(
        "app.retrieval.vector_retriever.search_markets_by_embedding",
        AsyncMock(return_value=rows),
    )
    _clear_settings()
    monkeypatch_setenv_w_date_1 = patch.dict(
        "os.environ", {"RANKING_V2_W_DATE": "1.0", "RANKING_V2_W_BUCKET": "0.0"}
    )
    with monkeypatch_setenv_w_date_1:
        from app.core.config import get_settings as gs
        gs.cache_clear()
        from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
        out = await hybrid_search_markets_v2(
            MagicMock(), [0.0] * 1536, "france politics",
            event_bucket="politics", event_entities=["France"],
            event_last_seen=_utc(2026, 4, 25),
        )
    assert out[0]["market_id"] == "m2", "expected the nearer-end-date market (m2) to rank first"


def _clear_settings():
    from app.core.config import get_settings
    get_settings.cache_clear()
