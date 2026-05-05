"""Tests for `TradeRequest` Pydantic bounds (PR #45 / audit H1).

Pre-PR #45, `amount: float` accepted any value Python could parse —
`-100`, `0`, `1e9`, NaN — and depended on `can_trade_real` and the
CLOB client to bounce it. Defense-in-depth is fine but should never
be the *first* validator a hostile request meets.

These tests pin the schema layer. A future contributor who relaxes
`Field(gt=0, le=10_000)` to plain `float` will trip every test below.
We do not exercise the live `/api/trading/trade` endpoint because the
schema is the contract — once it accepts a value, every layer above
gets the same value, no matter the route wiring.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.api.routes.trading import TRADE_AMOUNT_MAX_USDC, TradeRequest


def _valid_payload(**overrides) -> dict:
    base = {
        "market_id": "0xabc123",
        "direction": "BUY_YES",
        "amount": 100.0,
        "price": 0.50,
        "signal_id": 1,
    }
    base.update(overrides)
    return base


# ───────────────────────────────────────────────────────────────────
# Happy path — sanity check that valid input still parses
# ───────────────────────────────────────────────────────────────────


def test_valid_request_parses():
    req = TradeRequest(**_valid_payload())
    assert req.amount == 100.0
    assert req.price == 0.50


def test_market_order_omits_price():
    """`price=None` is the documented "market order" — must remain accepted."""
    req = TradeRequest(**_valid_payload(price=None))
    assert req.price is None


# ───────────────────────────────────────────────────────────────────
# Amount bounds (HIGH from audit — most consequential)
# ───────────────────────────────────────────────────────────────────


def test_amount_negative_rejected():
    with pytest.raises(ValidationError) as exc:
        TradeRequest(**_valid_payload(amount=-100.0))
    assert "amount" in str(exc.value)


def test_amount_zero_rejected():
    """Zero-stake orders are operationally meaningless and would still
    cost gas to attempt the Safe transaction."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(amount=0.0))


def test_amount_above_cap_rejected():
    """Over the configured cap (default 10_000 USDC). The hard cap is
    `TRADE_AMOUNT_MAX_USDC` — any change to the constant should be a
    deliberate decision visible in code review, not silent."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(amount=TRADE_AMOUNT_MAX_USDC + 0.01))


def test_amount_at_cap_accepted():
    """Boundary check: exactly at the cap is still allowed (le=, not lt=)."""
    req = TradeRequest(**_valid_payload(amount=TRADE_AMOUNT_MAX_USDC))
    assert req.amount == TRADE_AMOUNT_MAX_USDC


def test_amount_nan_rejected():
    """NaN passes a lot of float comparisons silently — Pydantic should
    block it before any business logic gets a chance to misbehave."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(amount=float("nan")))


def test_amount_inf_rejected():
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(amount=math.inf))


# ───────────────────────────────────────────────────────────────────
# Price bounds — Polymarket-native (probabilities ∈ [0.01, 0.99])
# ───────────────────────────────────────────────────────────────────


def test_price_below_polymarket_minimum_rejected():
    """Polymarket itself rejects prices below 1¢ — no point in letting
    the order propagate to the CLOB layer just to bounce there."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(price=0.005))


def test_price_above_polymarket_maximum_rejected():
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(price=0.995))


def test_price_at_boundaries_accepted():
    TradeRequest(**_valid_payload(price=0.01))
    TradeRequest(**_valid_payload(price=0.99))


# ───────────────────────────────────────────────────────────────────
# market_id and signal_id — defensive bounds
# ───────────────────────────────────────────────────────────────────


def test_market_id_empty_rejected():
    """An empty market_id would lookup MISSING in the DB and 404 anyway,
    but rejecting at the schema layer is one less query worth of waste."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(market_id=""))


def test_signal_id_zero_rejected():
    """`signal_id` is a positive integer in the DB. 0 / negative would
    silently match no signal and allow an unattributed trade."""
    with pytest.raises(ValidationError):
        TradeRequest(**_valid_payload(signal_id=0))


def test_signal_id_none_accepted():
    """A trade can be placed without a backing signal — `None` is the
    documented "manual trade" path."""
    req = TradeRequest(**_valid_payload(signal_id=None))
    assert req.signal_id is None
