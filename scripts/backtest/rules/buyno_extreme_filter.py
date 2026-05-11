"""T-013 candidate — drop BUY_NO outside the [0.30, 0.70] price band.

Audit 2026-05-12 (data 30j) :

  BUY_NO × YES<0.30 → n=201, RTP −17.10 %   (already caught by T-001)
  BUY_NO × YES 0.30-0.40 → n=46,  RTP  −3.60 %  (marginal)
  BUY_NO × YES 0.40-0.50 → n=23,  RTP  +5.86 %  (KEEP)
  BUY_NO × YES 0.50-0.60 → n=13,  RTP  −1.77 %  (small n, marginal)
  BUY_NO × YES 0.60-0.70 → n=27,  RTP  −1.71 %  (marginal)
  BUY_NO × YES≥0.70      → n=70,  RTP  −4.57 %  (toxic mirror of T-001)

The mirror of T-001: when the market already prices YES highly, betting
NO is a contrarian bet against the market consensus, and it loses in
expectation. Filter logic: keep BUY_NO only when YES ∈ [0.30, 0.70].

This rule is layered ON TOP of T-001 (which is already in
`signal_builder.py`), so backtest replay simulates both filters
together.
"""

from __future__ import annotations

_T001_LOWER = 0.30
_T013_UPPER = 0.70


def keep(signal: dict) -> bool:
    """Reject BUY_NO outside the [0.30, 0.70] price band."""
    direction = (signal.get("direction") or "").upper()
    price = signal.get("market_price_at_signal")
    if price is None:
        return False
    p = float(price)
    if direction in ("BUY_NO", "NO", "DOWN"):
        if p < _T001_LOWER:
            return False  # T-001 zone (lower)
        if p >= _T013_UPPER:
            return False  # T-013 mirror zone (upper)
    return True
