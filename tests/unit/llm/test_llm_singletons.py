"""Tests for the LLM-wrapper singletons (`get_event_summarizer`,
`get_impact_analyzer`, `get_reasoning_analyzer`).

Audit follow-up 2026-05-05 (H9). Pre-PR these wrappers were created
fresh on every Celery task. The underlying `OpenAIClient` was already
a singleton, so the AsyncOpenAI httpx pool was *not* re-created — but
the wrappers themselves did one disk read each (the system prompt
file) per allocation, plus the cumulative Python object churn at
~50 articles/min × 3 wrappers.

These tests pin two contracts:
  * Repeated calls return the same instance.
  * Backward-compat `create_*` aliases route through the singleton
    (so any ancient call site we missed migrating still benefits).
"""

from __future__ import annotations


def _reset_llm_singletons():
    """Drop all 3 cached wrappers — call this in setUp so test order
    cannot taint state."""
    import app.llm.event_summarizer as evt
    import app.llm.impact_analyzer as imp
    import app.llm.reasoning_analyzer as rsn

    evt._event_summarizer_singleton = None
    imp._impact_analyzer_singleton = None
    rsn._reasoning_analyzer_singleton = None


# ───────────────────────────────────────────────────────────────────
# event_summarizer
# ───────────────────────────────────────────────────────────────────


def test_get_event_summarizer_returns_same_instance():
    _reset_llm_singletons()
    from app.llm.event_summarizer import get_event_summarizer

    assert get_event_summarizer() is get_event_summarizer()


def test_create_event_summarizer_routes_through_singleton():
    """Backward-compat alias must NOT allocate a fresh wrapper —
    pre-PR this was the wasteful path."""
    _reset_llm_singletons()
    from app.llm.event_summarizer import (
        create_event_summarizer,
        get_event_summarizer,
    )

    a = create_event_summarizer()
    b = get_event_summarizer()
    c = create_event_summarizer()
    assert a is b is c


# ───────────────────────────────────────────────────────────────────
# impact_analyzer
# ───────────────────────────────────────────────────────────────────


def test_get_impact_analyzer_returns_same_instance():
    _reset_llm_singletons()
    from app.llm.impact_analyzer import get_impact_analyzer

    assert get_impact_analyzer() is get_impact_analyzer()


def test_create_impact_analyzer_routes_through_singleton():
    _reset_llm_singletons()
    from app.llm.impact_analyzer import (
        create_impact_analyzer,
        get_impact_analyzer,
    )

    assert create_impact_analyzer() is get_impact_analyzer() is create_impact_analyzer()


# ───────────────────────────────────────────────────────────────────
# reasoning_analyzer
# ───────────────────────────────────────────────────────────────────


def test_get_reasoning_analyzer_returns_same_instance():
    _reset_llm_singletons()
    from app.llm.reasoning_analyzer import get_reasoning_analyzer

    assert get_reasoning_analyzer() is get_reasoning_analyzer()


def test_create_reasoning_analyzer_routes_through_singleton():
    _reset_llm_singletons()
    from app.llm.reasoning_analyzer import (
        create_reasoning_analyzer,
        get_reasoning_analyzer,
    )

    assert (
        create_reasoning_analyzer()
        is get_reasoning_analyzer()
        is create_reasoning_analyzer()
    )


# ───────────────────────────────────────────────────────────────────
# All three share the underlying OpenAIClient singleton
# ───────────────────────────────────────────────────────────────────


def test_all_wrappers_share_underlying_openai_client():
    """The whole point — only one AsyncOpenAI httpx pool per process."""
    _reset_llm_singletons()
    from app.llm.event_summarizer import get_event_summarizer
    from app.llm.impact_analyzer import get_impact_analyzer
    from app.llm.openai_client import get_openai_client
    from app.llm.reasoning_analyzer import get_reasoning_analyzer

    shared = get_openai_client()
    assert get_event_summarizer().client is shared
    assert get_impact_analyzer().client is shared
    assert get_reasoning_analyzer().client is shared
