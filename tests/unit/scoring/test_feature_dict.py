"""Shared feature-dict builder — pinned regression test.

The 6-feature dict produced here is the load-bearing input to
`HeuristicScorer.compute_score`. Before extraction, this dict was built
inline inside `SignalBuilder.build_signal`. After extraction it MUST
produce byte-identical values for the same inputs — that is the
correctness contract this file enforces.

If a feature formula changes deliberately, update both the prod helper
in `feature_builder.py` AND the expected values here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.scoring.feature_builder import FeatureBuilder
from app.scoring.feature_dict import build_feature_dict


@pytest.fixture
def fresh_ref_dt() -> datetime:
    """30 minutes old → falls in the freshness ≤ 1h band → 1.0."""
    return datetime.now(timezone.utc) - timedelta(minutes=30)


@pytest.fixture
def stale_ref_dt() -> datetime:
    """48 hours old → falls in the 24-72h band → 0.4."""
    return datetime.now(timezone.utc) - timedelta(hours=48)


@pytest.fixture
def end_date_30d() -> datetime:
    """30 days out → falls in the 720h-MAX band → 0.4."""
    return datetime.now(timezone.utc) + timedelta(days=30)


def test_returns_six_keys_only(fresh_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    assert set(out.keys()) == {
        "freshness", "source_weight", "confirmation",
        "liquidity", "spread", "time_to_resolution",
    }


def test_freshness_band_one_hour(fresh_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # 30min → ≤ 1h band → 1.0
    assert out["freshness"] == pytest.approx(1.0)


def test_freshness_band_48h(stale_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=stale_ref_dt,
        source_count=2,
    )
    # 48h → 24-72h band → 0.4
    assert out["freshness"] == pytest.approx(0.4)


def test_source_weight_defaults_to_half_when_missing(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={},  # no source_weight key
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # build_source_weight(0.5) → 0.5 (since 0.5 truthy and ≤ 1.0)
    assert out["source_weight"] == pytest.approx(0.5)


def test_source_weight_clamps_above_one(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 1.5, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    assert out["source_weight"] == pytest.approx(1.0)


def test_confirmation_three_or_more_sources_is_one(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 2},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=3,
    )
    assert out["confirmation"] == pytest.approx(1.0)


def test_confirmation_one_source_tier_one(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=1,
    )
    # source_count<2 + tier 1 → 0.7 per build_confirmation_factor
    assert out["confirmation"] == pytest.approx(0.7)


def test_confirmation_one_source_tier_two_default(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85},  # tier defaults to 2
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=1,
    )
    assert out["confirmation"] == pytest.approx(0.5)


def test_liquidity_band_50k(fresh_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # 10k ≤ liquidity ≤ 100k → 1.0
    assert out["liquidity"] == pytest.approx(1.0)


def test_liquidity_none_floors_to_low(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": None, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    assert out["liquidity"] == pytest.approx(0.1)


def test_spread_tight(fresh_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.015, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # spread ≤ 0.02 → 1.0
    assert out["spread"] == pytest.approx(1.0)


def test_spread_none(fresh_ref_dt: datetime, end_date_30d: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": None, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # build_spread_penalty(None) → 0.8
    assert out["spread"] == pytest.approx(0.8)


def test_time_to_resolution_30d(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    # 30 days = 720h → falls in the 720-365d band, but exactly 720h → still 0.6 (≤ 720h)
    # Actually 30 days = 720h exactly; build_time_to_resolution_factor returns 0.6 if hours_left ≤ 720.
    # We use a small tolerance because clock drift between fixture creation and assertion can
    # push hours_left just under 720.
    assert out["time_to_resolution"] == pytest.approx(0.6)


def test_time_to_resolution_none(fresh_ref_dt: datetime) -> None:
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": None},
        ref_dt=fresh_ref_dt,
        source_count=2,
    )
    assert out["time_to_resolution"] == pytest.approx(0.5)


def test_accepts_injected_feature_builder(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    """The helper must accept a custom FeatureBuilder instance for testability."""
    fb = FeatureBuilder()
    out = build_feature_dict(
        event_data={"source_weight": 0.85, "source_tier": 1},
        market_data={"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d},
        ref_dt=fresh_ref_dt,
        source_count=2,
        feature_builder=fb,
    )
    assert "freshness" in out


def test_matches_signal_builder_inline_construction(
    fresh_ref_dt: datetime, end_date_30d: datetime,
) -> None:
    """Pin the exact contract: helper output == prior inline construction.

    This is the regression test that catches drift between the extracted
    helper and the in-prod code. If signal_builder.py:178-196 changes
    behavior, this test must be updated in the same PR.
    """
    event_data = {"source_weight": 0.85, "source_tier": 1}
    market_data = {"liquidity": 50_000, "spread": 0.03, "end_date": end_date_30d}
    source_count = 2

    out = build_feature_dict(
        event_data=event_data,
        market_data=market_data,
        ref_dt=fresh_ref_dt,
        source_count=source_count,
    )

    fb = FeatureBuilder()
    expected = {
        "freshness": fb.build_freshness_factor(fresh_ref_dt),
        "source_weight": fb.build_source_weight(event_data.get("source_weight", 0.5)),
        "confirmation": fb.build_confirmation_factor(
            source_count, source_tier=event_data.get("source_tier", 2),
        ),
        "liquidity": fb.build_liquidity_factor(market_data.get("liquidity")),
        "spread": fb.build_spread_penalty(market_data.get("spread")),
        "time_to_resolution": fb.build_time_to_resolution_factor(
            market_data.get("end_date"),
        ),
    }
    assert out == expected
