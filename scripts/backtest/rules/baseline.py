"""Baseline rule — keep all signals.

Used to confirm the harness reproduces the live `/api/admin/stats/extended`
numbers. If `baseline` returns different RTP/winrate than the API, the
harness has a bug.
"""

from __future__ import annotations


def keep(signal: dict) -> bool:
    """Accept every signal that has an outcome and a market_price."""
    return True
