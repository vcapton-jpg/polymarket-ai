"""T-001 candidate rule — drop BUY_NO when market_price_at_signal < 0.30.

Audit 2026-05-11 RTP cross-tab :
    BUY_NO × YES<0.20 → n=143, RTP −6.72%
    BUY_NO × YES 0.20-0.30 → n=68, RTP **−39.04%** (catastrophe)
    BUY_NO × YES 0.30-0.40 → n=48, RTP −3.60% (kept, marginal)
Cumulated: BUY_NO × YES<0.30 ≈ 211 signals/30d at avg move +17%
(against us). Pure-defense filter.
"""

from __future__ import annotations


def keep(signal: dict) -> bool:
    """Reject BUY_NO when the YES price is already <0.30 (no edge to capture)."""
    direction = (signal.get("direction") or "").upper()
    price = signal.get("market_price_at_signal")
    if price is None:
        return False  # cannot evaluate without a price → conservative reject
    if direction in ("BUY_NO", "NO", "DOWN") and float(price) < 0.30:
        return False
    return True
