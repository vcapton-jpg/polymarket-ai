"""P0-2 + P1.3 (audit 2026-04-25): derive event-level source_weight and
source_tier from the actual cluster, not hardcoded constants.

Background:
- P0-2: `tasks_scoring._run_full_scoring_pipeline` passed
  `source_weight=0.8` hardcoded to the SignalBuilder, ignoring the real
  source weights of the news in the cluster.
- P1.3: the same call site never passed `source_tier`, so
  `feature_builder.build_confirmation_factor` always defaulted to
  `source_tier=2` for the single-source branch — meaning a single Reuters
  (tier 1) story scored the same as a single tier-2 blog.

Both bugs share the same prefetched data (the `src_rows` from the events
articles JOIN), so a single helper handles them.

Selection rules (best-of-cluster):
- source_weight: MAX across the cluster — the strongest source defines
  the cluster's authority. A confirming Reuters wire shouldn't be diluted
  by a low-weight aggregator that happened to repost it.
- source_tier: MIN across the cluster — lower tier number = better
  source, same logic as above.
"""

from __future__ import annotations

import pytest


def test_helper_picks_max_weight_and_min_tier():
    from app.workers.tasks_scoring import _derive_event_source_signals

    rows = [
        ("reuters", 1, 0.95),
        ("blog-x", 3, 0.30),
        ("politico", 2, 0.85),
    ]
    out = _derive_event_source_signals(rows)
    assert out == {"source_weight": 0.95, "source_tier": 1}


def test_helper_handles_empty_cluster():
    """Empty input must yield safe defaults — never raise."""
    from app.workers.tasks_scoring import _derive_event_source_signals

    out = _derive_event_source_signals([])
    # Defaults must match what the SignalBuilder used pre-fix:
    # build_source_weight returns 0.5 for a falsy input, and
    # build_confirmation_factor defaults source_tier=2.
    assert out == {"source_weight": 0.5, "source_tier": 2}


def test_helper_skips_none_tiers_and_weights():
    """A row with NULL tier/weight is ignored, not treated as 0."""
    from app.workers.tasks_scoring import _derive_event_source_signals

    rows = [
        ("a", None, None),
        ("b", 1, 0.95),
    ]
    out = _derive_event_source_signals(rows)
    assert out == {"source_weight": 0.95, "source_tier": 1}


def test_helper_handles_all_none_rows():
    """All NULLs → fall back to safe defaults."""
    from app.workers.tasks_scoring import _derive_event_source_signals

    rows = [("a", None, None), ("b", None, None)]
    out = _derive_event_source_signals(rows)
    assert out == {"source_weight": 0.5, "source_tier": 2}
