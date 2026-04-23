"""Unit tests for ArticleRanker — pure scoring, no DB.

Tests cover every branch of §5 of the spec:
- α/β weighting, recency decay, tie-break, top_k, None-embedding fallback,
  articles with NULL embeddings excluded.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.sourcing.article_ranker import ArticleRanker, RankedArticle


T0 = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


def _vec(x: float) -> list[float]:
    """1536-dim embedding pointing along x axis, magnitude = x (simulates
    normalized vectors when we pass x=1; cosine then = dot(e_a, e_m))."""
    v = [0.0] * 1536
    v[0] = x
    return v


def _art(
    news_clean_id: int,
    *,
    age_hours: float,
    cos_x: float,
    source_weight: float = 0.5,
) -> dict:
    """Build a candidate article dict with an embedding along the x axis."""
    return {
        "news_clean_id": news_clean_id,
        "embedding": _vec(cos_x),
        "publish_date": T0 - timedelta(hours=age_hours),
        "clean_text": f"body-{news_clean_id}",
        "source_name": "src",
        "source_tier": 1,
        "source_weight": source_weight,
    }


# ── core ordering ────────────────────────────────────────────────────
def test_rank_deterministic_same_inputs_same_output():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    pool = [_art(1, age_hours=1, cos_x=0.6), _art(2, age_hours=1, cos_x=0.9)]
    a = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    b = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert [r.news_clean_id for r in a] == [r.news_clean_id for r in b]


def test_rank_alpha_one_beta_zero_orders_by_pure_cosine():
    ranker = ArticleRanker(alpha=1.0, beta=0.0, tau_hours=24.0)
    pool = [_art(1, age_hours=48, cos_x=0.9),  # old but highly relevant
            _art(2, age_hours=1,  cos_x=0.2)]  # fresh but irrelevant
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert ranked[0].news_clean_id == 1


def test_rank_alpha_zero_beta_one_orders_by_pure_recency():
    ranker = ArticleRanker(alpha=0.0, beta=1.0, tau_hours=24.0)
    pool = [_art(1, age_hours=48, cos_x=0.9),
            _art(2, age_hours=1,  cos_x=0.2)]
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert ranked[0].news_clean_id == 2


# ── tie-break ────────────────────────────────────────────────────────
def test_rank_tiebreak_newer_publish_date_wins():
    """Same cosine & same alpha-weight: the fresher article must come first."""
    ranker = ArticleRanker(alpha=0.5, beta=0.5, tau_hours=24.0)
    pool = [
        _art(1, age_hours=5, cos_x=0.5),
        _art(2, age_hours=5, cos_x=0.5),  # identical age + cosine
    ]
    # Manually shift art 2 to be older by 1h so the scores tie at ε precision
    # but the fresher one (art 1) must come first.
    pool[1]["publish_date"] = T0 - timedelta(hours=5, seconds=1)
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert ranked[0].news_clean_id == 1


# ── top-k & empty ────────────────────────────────────────────────────
def test_rank_respects_top_k():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    pool = [_art(i, age_hours=1, cos_x=0.5) for i in range(1, 11)]  # 10 items
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=3)
    assert len(ranked) == 3


def test_rank_empty_pool_returns_empty():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    assert ranker.rank([], _vec(1.0), T0, top_k=5) == []


# ── None-embedding fallbacks ─────────────────────────────────────────
def test_rank_none_market_embedding_degrades_to_recency_only():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    pool = [_art(1, age_hours=48, cos_x=0.9),
            _art(2, age_hours=1,  cos_x=0.1)]
    ranked = ranker.rank(pool, None, T0, top_k=5)   # market embedding = None
    # Recency-only means fresher wins regardless of cosine.
    assert ranked[0].news_clean_id == 2
    # cosine field is recorded as 0.0 under the fallback.
    assert ranked[0].cosine == pytest.approx(0.0, abs=1e-6)


def test_rank_article_without_embedding_is_dropped():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    good = _art(1, age_hours=1, cos_x=0.9)
    bad = _art(2, age_hours=1, cos_x=0.9)
    bad["embedding"] = None
    ranked = ranker.rank([good, bad], _vec(1.0), T0, top_k=5)
    assert [r.news_clean_id for r in ranked] == [1]


# ── rank values ──────────────────────────────────────────────────────
def test_rank_numbers_are_1_based_and_contiguous():
    ranker = ArticleRanker(alpha=0.7, beta=0.3, tau_hours=24.0)
    pool = [_art(i, age_hours=i, cos_x=0.5) for i in range(1, 6)]
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert [r.rank for r in ranked] == [1, 2, 3, 4, 5]


# ── decay formula sanity ─────────────────────────────────────────────
def test_recency_weight_matches_exp_decay_24h():
    ranker = ArticleRanker(alpha=0.0, beta=1.0, tau_hours=24.0)
    pool = [_art(1, age_hours=24, cos_x=0.0)]
    ranked = ranker.rank(pool, _vec(1.0), T0, top_k=5)
    assert ranked[0].recency_weight == pytest.approx(math.exp(-1.0), abs=1e-6)


# ── from_settings factory ────────────────────────────────────────────
def test_from_settings_reads_alpha_beta_tau():
    from app.core.config import get_settings
    get_settings.cache_clear()
    ranker = ArticleRanker.from_settings(get_settings())
    assert ranker.alpha == 0.7
    assert ranker.beta == 0.3
    assert ranker.tau_hours == 24.0
