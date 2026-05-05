"""Tests for `_check_signal_duplicate` (audit follow-up 2026-05-05).

Pre-PR the dedupe story was: `dedupe_key` was computed and stored on
every Signal but never queried for filtering — pure placebo. The
audit caught a live duplicate emission (Hormuz blockade May 31 vs
June 30 markets, both BUY_NO, same Hegseth catalyst, 33 min apart).
This module pins both layers of the new helper.

Approach: we don't spin a real DB. We give `session` a tiny stub
whose `execute(query)` returns a controllable result. The helper's
contract is "given the query result, what reason string does it
return?", which is fully testable without Postgres in the loop. The
SQL is written using SQLAlchemy expressions; whether it actually
queries Postgres correctly is an integration concern (caught at
deploy via the live ingestion stream).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.workers.tasks_scoring import _check_signal_duplicate


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────


def _settings(
    *,
    dedupe_window_hours: float = 72.0,
    thematic_window_hours: float = 12.0,
    thematic_threshold: float = 0.85,
):
    return SimpleNamespace(
        signal_dedupe_window_hours=dedupe_window_hours,
        thematic_dedup_window_hours=thematic_window_hours,
        thematic_dedup_cosine_threshold=thematic_threshold,
    )


def _market(market_id: str = "0xabc", embedding=(0.1,) * 1536):
    return SimpleNamespace(
        market_id=market_id,
        embedding=list(embedding) if embedding is not None else None,
    )


class _FakeSession:
    """Stub `session.execute` to return a sequence of pre-canned results."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _query):
        if not self._results:
            raise AssertionError("FakeSession.execute called more times than results were provided")
        next_result = self._results.pop(0)
        return next_result


def _scalar_result(value):
    """Mimics `result = await session.execute(...); result.scalar_one_or_none()`."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _row_result(row):
    """Mimics `result.first()` returning a Row or None."""
    r = MagicMock()
    r.first.return_value = row
    return r


# ───────────────────────────────────────────────────────────────────
# Layer 1: exact dedupe
# ───────────────────────────────────────────────────────────────────


def test_exact_match_returns_exact_duplicate():
    """If `dedupe_key` matches an existing signal, layer 1 fires and
    layer 2 never runs."""
    session = _FakeSession([_scalar_result(value=42)])  # found a hit

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(),
        event_title="Will X happen by June 30?",
        bucket="geopolitics",
        direction="BUY_NO",
        settings=_settings(),
    ))

    assert reason == "exact_duplicate"


def test_no_exact_no_thematic_returns_none():
    """No layer-1 hit, no layer-2 hit → emit the signal."""
    session = _FakeSession([
        _scalar_result(value=None),   # layer 1 misses
        _row_result(row=None),        # layer 2 nearest = no row
    ])

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(),
        event_title="Will X happen by June 30?",
        bucket="geopolitics",
        direction="BUY_NO",
        settings=_settings(),
    ))

    assert reason is None


# ───────────────────────────────────────────────────────────────────
# Layer 2: thematic dedupe
# ───────────────────────────────────────────────────────────────────


def test_thematic_match_above_threshold_returns_thematic_duplicate():
    """The keystone case — twin-market signal within window, cosine ≥ 0.85.
    Pre-PR this slipped through every filter."""
    # cosine 0.93 ↔ distance 0.07
    near_row = MagicMock()
    near_row.id = 1781
    near_row.market_id = "0x8b369e10..."
    near_row.dist = 0.07
    session = _FakeSession([
        _scalar_result(value=None),   # layer 1 misses
        _row_result(row=near_row),    # layer 2 finds a sibling
    ])

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(market_id="0x4d0c4865..."),
        event_title="Will X happen by June 30?",
        bucket="geopolitics",
        direction="BUY_NO",
        settings=_settings(),
    ))

    assert reason is not None
    assert reason.startswith("thematic_duplicate")
    assert "0.93" in reason  # 1.0 - 0.07
    assert "1781" in reason  # sibling_signal_id surfaces in the log line


def test_thematic_match_below_threshold_returns_none():
    """Cosine 0.80 (distance 0.20) is below the 0.85 threshold → emit."""
    far_row = MagicMock()
    far_row.id = 1781
    far_row.market_id = "0x..."
    far_row.dist = 0.20
    session = _FakeSession([
        _scalar_result(value=None),
        _row_result(row=far_row),
    ])

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(),
        event_title="Will X happen by June 30?",
        bucket="geopolitics",
        direction="BUY_NO",
        settings=_settings(),
    ))

    assert reason is None


def test_no_market_embedding_skips_layer_2():
    """A market with no `embedding` can't be cosine-compared. Skip
    layer 2 silently — don't pretend it's safe, but don't fail-close
    either. Layer 1's exact-key check still ran."""
    session = _FakeSession([_scalar_result(value=None)])  # only layer 1

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(embedding=None),
        event_title="Some new event",
        bucket="economics",
        direction="BUY_YES",
        settings=_settings(),
    ))

    assert reason is None


def test_thematic_threshold_is_configurable():
    """Operators can tune the cosine bar without a code change. Setting
    threshold=0.95 means only very-similar markets trigger."""
    # Sibling at sim 0.88 (distance 0.12) — over default 0.85 but
    # under 0.95.
    near_row = MagicMock()
    near_row.id = 1781
    near_row.market_id = "0x..."
    near_row.dist = 0.12
    session = _FakeSession([
        _scalar_result(value=None),
        _row_result(row=near_row),
    ])

    reason = asyncio.run(_check_signal_duplicate(
        session,
        market=_market(),
        event_title="t",
        bucket="x",
        direction="BUY_NO",
        settings=_settings(thematic_threshold=0.95),
    ))

    assert reason is None  # 0.88 < 0.95
