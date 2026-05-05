"""Tests for `app.processing.embedding_service` OpenAI client construction.

Audit follow-up 2026-05-05 — pins behavior introduced in PR #38. The
SDK's default `timeout` is 600 s, which combined with `task_time_limit
= 600 s` and tenacity's 3-attempt retry created a 30-min worst-case
hang during the 6-day outage. The 30 s ceiling here is the safety
contract: a future contributor who removes `timeout=...` from the
`AsyncOpenAI(...)` constructor reintroduces the silent crash loop.

We don't test happy-path embeddings — those need a real OpenAI key and
network. We pin the *constructor argument*, which is sufficient
because the SDK itself enforces the timeout below it.
"""

from __future__ import annotations

from unittest.mock import patch


def test_embedding_service_constructs_async_openai_with_30s_timeout():
    """`EmbeddingService()` must wire `timeout=OPENAI_TIMEOUT_SECONDS`
    into the `AsyncOpenAI` constructor. If a refactor drops the kwarg
    or changes the constant, the network tail is uncapped again."""
    import app.processing.embedding_service as svc

    # Reset singleton so this test forces a fresh constructor call.
    svc._service = None

    with patch("app.processing.embedding_service.AsyncOpenAI") as mock_cls:
        instance = svc.EmbeddingService()
        # Single call, with the timeout constant explicitly passed.
        assert mock_cls.call_count == 1
        kwargs = mock_cls.call_args.kwargs
        assert "timeout" in kwargs, (
            "AsyncOpenAI must be constructed with an explicit `timeout=` "
            "kwarg — relying on the SDK default (600 s) re-creates the "
            "30-min hang we shipped PR #38 to fix."
        )
        assert kwargs["timeout"] == svc.OPENAI_TIMEOUT_SECONDS == 30.0


def test_embedding_service_singleton_creates_one_client():
    """`get_embedding_service` is a singleton — one `AsyncOpenAI` per
    process, not per call. Pre-PR #44, lots of these "create one per
    invocation" patterns added up to real memory pressure."""
    import app.processing.embedding_service as svc

    svc._service = None

    with patch("app.processing.embedding_service.AsyncOpenAI"):
        a = svc.get_embedding_service()
        b = svc.get_embedding_service()
        c = svc.get_embedding_service()
        assert a is b is c
