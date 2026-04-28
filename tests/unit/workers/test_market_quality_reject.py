"""Filter A — `_market_quality_reject` regression tests.

Audit 2026-04-28 follow-up: the 27-04 retro showed 7 catastrophic
geopolitics×BUY_NO losses on news-binary markets within 0–3 days of
resolution. Two new branches in `_market_quality_reject` close that
trap:

  * end_date already past (e.g. signal at 2026-04-27 on a market whose
    end_date was 2026-04-17) → reject.
  * end_date within `settings.market_min_remaining_hours` (default 48 h)
    → reject. Within the resolution window, breaking news can flip the
    price to 0/1 inside our 1h decision horizon.

These tests pin both branches without spinning a DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import patch

import pytest

from app.workers.tasks_scoring import _market_quality_reject


@dataclass
class _Market:
    """Lightweight stand-in for the SQLAlchemy `Market` model — only the
    attributes `_market_quality_reject` reads."""

    volume_24h: float = 10_000.0
    liquidity: float = 10_000.0
    last_trade_price: Optional[float] = 0.50
    end_date: Optional[datetime] = None


def _future(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _past(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Pre-existing checks still pass through.
# ---------------------------------------------------------------------------


def test_healthy_market_returns_none():
    """A liquid, far-from-resolution, well-priced market → no rejection."""
    m = _Market(end_date=_future(30 * 24))
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        assert _market_quality_reject(m) is None


def test_low_volume_still_rejected():
    m = _Market(volume_24h=10.0, end_date=_future(30 * 24))
    assert "volume_24h" in (_market_quality_reject(m) or "")


def test_low_liquidity_still_rejected():
    m = _Market(liquidity=100.0, end_date=_future(30 * 24))
    assert "liquidity" in (_market_quality_reject(m) or "")


def test_price_pinned_at_one_still_rejected():
    m = _Market(last_trade_price=0.99, end_date=_future(30 * 24))
    assert "outside" in (_market_quality_reject(m) or "")


# ---------------------------------------------------------------------------
# A — end_date in the past.
# ---------------------------------------------------------------------------


def test_end_date_already_past_rejected():
    """Signals like 2026-04-27 #1664 on a market whose end_date was
    2026-04-17 must not generate a trade. The market is in resolution
    pending state — entering is pure noise."""
    m = _Market(end_date=_past(10 * 24))
    reason = _market_quality_reject(m)
    assert reason is not None
    assert "already past" in reason


def test_end_date_naive_datetime_treated_as_utc():
    """`Market.end_date` may arrive without tzinfo if Polymarket's
    payload mis-formats it. We normalise to UTC instead of crashing."""
    naive_past = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None)
    m = _Market(end_date=naive_past)
    reason = _market_quality_reject(m)
    assert reason is not None
    assert "already past" in reason


# ---------------------------------------------------------------------------
# B — end_date within `market_min_remaining_hours`.
# ---------------------------------------------------------------------------


def test_end_date_within_window_rejected():
    """Markets resolving in <48 h are the news-binary trap: a single
    breaking story moves the price to 0/1 inside our 1h decision
    horizon. Reject by default."""
    m = _Market(end_date=_future(12))  # 12 h until resolution
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        reason = _market_quality_reject(m)
    assert reason is not None
    assert "too soon" in reason


def test_end_date_just_outside_window_passes():
    """49 h to resolution is on the safe side of the default 48 h gate."""
    m = _Market(end_date=_future(49))
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        assert _market_quality_reject(m) is None


def test_window_disabled_when_setting_zero():
    """Operators can disable the window gate by setting the threshold
    to 0 (e.g. for a backtest where past-noise is desired)."""
    m = _Market(end_date=_future(2))
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 0})(),
    ):
        assert _market_quality_reject(m) is None


def test_no_end_date_at_all_passes():
    """Some markets ship without `end_date` populated — we cannot gate
    on what we don't know. Pass through to the existing checks."""
    m = _Market(end_date=None)
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        assert _market_quality_reject(m) is None


# ---------------------------------------------------------------------------
# Pre-fix scenario — must be rejected post-fix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_name,end_date_offset_h,expected_marker",
    [
        # 27-04 catastrophes whose end_date was already in the past at
        # signal time — the past-deadline branch must catch them.
        ("1664-Lebanon-suspension-Apr17", -10 * 24, "already past"),
        ("1709-1664-resignaled-6h-later", -10 * 24, "already past"),
        # Synthetic close-deadline case — within the 48 h window.
        ("synthetic-deadline-12h-out", 12, "too soon"),
    ],
)
def test_2026_04_27_catastrophes_now_blocked(case_name, end_date_offset_h, expected_marker):
    """Replays the 27-04 retro cases that A+B *can* prevent.

    Specifically these branches catch end_date in the past (#1664/#1709)
    and end_date within 48 h. The remaining 27-04 catastrophes (Apr 30 →
    72 h out, May/June deadlines) are intentionally outside this filter's
    scope — they need the catalyst-cluster work scheduled for later
    (Filter D + thematic dedup).
    """
    m = _Market(
        last_trade_price=0.50,
        end_date=_future(end_date_offset_h)
        if end_date_offset_h >= 0
        else _past(-end_date_offset_h),
    )
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        reason = _market_quality_reject(m)
    assert reason is not None, f"{case_name} must be rejected"
    assert expected_marker in reason


def test_apr30_deadline_at_apr27_signal_time_not_caught_by_48h_window():
    """Documenting the gap: signals fired on Apr 27 against a market
    closing Apr 30 are 72 h out — outside the 48 h window. Those need
    Filter D + cluster-thematic dedup (Phase 2). This test pins the
    current scope so a later refactor doesn't accidentally claim
    coverage we don't have.
    """
    m = _Market(end_date=_future(72))
    with patch(
        "app.core.config.get_settings",
        return_value=type("S", (), {"market_min_remaining_hours": 48})(),
    ):
        assert _market_quality_reject(m) is None
