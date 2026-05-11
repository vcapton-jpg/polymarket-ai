"""Pin the T-013 BUY_NO × YES≥threshold filter contract.

Symmetric to T-001 (low-price filter): rejects BUY_NO when the market
YES price is already high, where betting NO is a contrarian bet
against consensus and loses in expectation (audit 2026-05-12 :
n=70, RTP −4.57 %).

Toggle is OFF by default so these tests force-enable it via the
`enable_buyno_highprice_filter` setting before each case.
"""

from __future__ import annotations

import pytest

from scripts.backtest.rules.buyno_extreme_filter import keep


def test_keep_rejects_buyno_at_or_above_high_threshold():
    """BUY_NO × YES=0.70 must be rejected — the mirror of the toxic
    low-side zone."""
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.70}) is False
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.85}) is False


def test_keep_accepts_buyno_in_mid_band():
    """The [0.30, 0.70) mid-band stays for BUY_NO — that's the zone
    where the residual edge lives."""
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.50}) is True
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.30}) is True
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.69}) is True


def test_keep_rejects_buyno_under_low_threshold_t001_overlap():
    """T-001 + T-013 stack: low-side rejection still applies."""
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.10}) is False
    assert keep({"direction": "BUY_NO", "market_price_at_signal": 0.29}) is False


def test_keep_passes_buy_yes_at_any_price():
    """T-013 is BUY_NO-specific. BUY_YES is untouched."""
    for price in (0.05, 0.30, 0.50, 0.70, 0.95):
        assert keep({"direction": "BUY_YES", "market_price_at_signal": price}) is True


def test_keep_rejects_when_price_unknown():
    """No price → conservative reject (matches T-001 baseline policy)."""
    assert keep({"direction": "BUY_NO", "market_price_at_signal": None}) is False


@pytest.mark.parametrize("alias", ["NO", "DOWN", "buy_no", "Buy_No"])
def test_keep_handles_direction_aliases(alias):
    """Direction normalization: BUY_NO / NO / DOWN must all behave the
    same — case-insensitive."""
    assert keep({"direction": alias, "market_price_at_signal": 0.85}) is False
    assert keep({"direction": alias, "market_price_at_signal": 0.50}) is True
