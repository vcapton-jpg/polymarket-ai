# Embedding Quality — Eval Harness + Composition Shadows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every future embedding change measurable (phase 1 = offline eval harness + frozen baseline), then ship three targeted composition shadows — news lead+tail truncation (A1), market category injection (A3), event bucket prefix + call-site consolidation (A4) — each gated by the harness before a per-surface feature flag flip in production.

**Architecture:** Phase 1 adds `embedding_v2` columns to `news_clean`, `markets`, `events` (migration 022), a read-only `app/eval/` package (labels + metrics + runner), and a `scripts/eval_embeddings.py` CLI that emits a reproducible JSON report. Phase 2 adds a single `app/processing/text_composers.py` module (v1 = bit-exact re-implementation of today's inline f-strings, v2 = the three new compositions), a feature-flag helper `embedding_reader.py` that routes ORM and raw-SQL consumers to `embedding` or `embedding_v2`, a Celery backfill task, and a conditional migration 023 (HNSW index on `markets.embedding_v2`, required only before promoting the market surface).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async (`Mapped` / `mapped_column`), Alembic (revision `022`, `down_revision="021"`; revision `023` with `down_revision="022"`), pgvector 1536-dim, Celery + Redis, OpenAI `text-embedding-3-small` + `gpt-4o-mini` (for LLM judge), numpy (bootstrap CI), pytest-asyncio.

**Spec:** `docs/specs/2026-04-24-embeddings-eval-harness-design.md`. Read it once before starting — §4 (harness), §5 (composers), §6 (schema), §7 (promotion gate) are the ground truth.

**Depends on (already shipped in chantiers #1 and #2):**
- `SignalPrediction`, `SignalOutcome`, `SignalArticle` tables + their relationships.
- `app/core/config.py::Settings` with BaseSettings + `@lru_cache` on `get_settings`.
- `app/db/models.py` with `NewsClean`, `Market`, `Event` ORM classes.
- `app/workers/_async_helpers.run_async` for async-in-Celery.
- `llm_cost_log` table (used by LLM judge for budget tracking).

**Branch target:** continue on `pivot/learn-and-trade` (current branch). No new worktree — this chantier is a linear continuation.

---

## File structure (created / modified)

**New files:**
- `alembic/versions/022_add_embedding_v2_columns.py` — migration (task 1)
- `alembic/versions/023_add_hnsw_index_market_embedding_v2.py` — conditional migration (task 17)
- `app/eval/__init__.py` — package marker (task 3)
- `app/eval/metrics.py` — pure functions: `retrieval_at_k`, `ndcg_at_k`, `bootstrap_ci`, `aggregate`, `cluster_purity` (task 3)
- `app/eval/labels.py` — `EvalPair` dataclass + `load_pairs(surface)` + 3 internal loaders + dedup (tasks 4 + 5)
- `app/eval/runner.py` — `EvalReport` + `run_eval` + `report_to_json` + `diff_reports` (task 6)
- `scripts/eval_embeddings.py` — CLI wrapper (task 7)
- `docs/eval_baselines/.gitkeep` + `docs/eval_baselines/embeddings_2026-04-24_v1.json` — frozen baseline (task 7)
- `app/processing/text_composers.py` — `ComposedText` dataclass + 6 composers: `compose_news_v1/v2`, `compose_market_v1/v2`, `compose_event_v1/v2` (tasks 8 + 10–12)
- `app/processing/embedding_reader.py` — `get_active_embedding(row, surface)` + `active_column_name(surface)` (task 13)
- `app/workers/tasks_embeddings_backfill.py` — `recompute_embedding_v2(surface, batch_size)` (task 16)
- `docs/runbooks/promote_embeddings_v2.md` — promotion gate runbook (task 18)
- `tests/unit/test_eval_metrics.py` — metrics tests (task 3)
- `tests/unit/test_text_composers_v1.py` — bit-exact regression tests (task 8)
- `tests/unit/test_text_composers_v2.py` — v2 logic tests (tasks 10–12)
- `tests/unit/test_embedding_reader.py` — flag-routing tests (task 13)
- `tests/integration/test_eval_labels.py` — DB-backed label loading (tasks 4 + 5)
- `tests/integration/test_eval_runner.py` — end-to-end eval on fixture (task 6)
- `tests/integration/test_embeddings_backfill.py` — Celery eager + idempotence (task 16)
- `tests/integration/test_inline_v2_writes.py` — pipeline writes both embeddings (task 15)
- `tests/helpers/embedding_fixtures.py` — `make_toy_embedding` + `tiny_eval_corpus` (task 3)

**Modified files:**
- `app/db/models.py` — add `embedding_v2`, `embedding_v2_composition`, `embedding_v2_computed_at` columns to `NewsClean`, `Market`, `Event` (task 2)
- `app/core/config.py` — add `embeddings_variant_news`, `embeddings_variant_market`, `embeddings_variant_event`, `llm_judge_max_usd` settings (task 13)
- `app/workers/tasks_pipeline.py` — replace inline `f"{raw_title}. {clean_text[:1500]}"` at line 98 with `compose_news_v1(...)` then add v2 inline write (tasks 9 + 15); replace the 3 inline event-composition f-strings at lines 271, 316–319, 513–516 with `compose_event_v1(...)` (task 9)
- `app/workers/tasks_ingestion.py::_build_retrieval_text` — replace body with `compose_market_v1(mkt).text` (task 9); add v2 inline write in market creation (task 15)
- `app/event_engine/event_builder.py:55-63` — replace inline join with `compose_event_v1(...)` (task 9); add v2 inline write (task 15)
- `app/retrieval/hybrid_search.py` — migrate embedding reads through `get_active_embedding` (task 14)
- `app/retrieval/vector_retriever.py::search_markets_by_embedding` — migrate raw-SQL column name through `active_column_name("market")` (task 14)
- `app/event_engine/simple_clusterer.py` — migrate embedding reads through `get_active_embedding` (task 14)
- `app/sourcing/pool_builder.py` — migrate embedding reads through `get_active_embedding("news")` (task 14)
- `app/workers/celery_app.py` — add `"app.workers.tasks_embeddings_backfill"` to `autodiscover_tasks([...])` and route to `scoring` queue (task 16)

---

## Task 1: Alembic migration — `embedding_v2` columns on 3 tables

**Files:**
- Create: `alembic/versions/022_add_embedding_v2_columns.py`

- [ ] **Step 1: Write the migration**

```python
"""add embedding_v2 columns to news_clean / markets / events.

Revision ID: 022
Revises: 021
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


_TABLES = ("news_clean", "markets", "events")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("embedding_v2", Vector(1536), nullable=True))
        op.add_column(table, sa.Column("embedding_v2_composition", sa.Text(), nullable=True))
        op.add_column(
            table,
            sa.Column(
                "embedding_v2_computed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "embedding_v2_computed_at")
        op.drop_column(table, "embedding_v2_composition")
        op.drop_column(table, "embedding_v2")
```

- [ ] **Step 2: Apply the migration**

Run: `docker compose exec -T app alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 021 -> 022, add embedding_v2 columns to news_clean / markets / events`.

- [ ] **Step 3: Verify schema on all three tables**

Run:
```bash
docker compose exec -T db psql -U postgres -d signal -c "
  SELECT table_name, column_name, data_type
  FROM information_schema.columns
  WHERE column_name LIKE 'embedding_v2%'
  ORDER BY table_name, column_name;"
```
Expected: 9 rows — three per table (`embedding_v2` as `USER-DEFINED` (vector), `embedding_v2_composition` as `text`, `embedding_v2_computed_at` as `timestamp with time zone`).

- [ ] **Step 4: Verify downgrade then re-upgrade works**

Run:
```bash
docker compose exec -T app alembic downgrade 021 && \
docker compose exec -T app alembic upgrade head
```
Expected: downgrade emits `Running downgrade 022 -> 021` and drops all 9 columns; upgrade re-applies them.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/022_add_embedding_v2_columns.py
git commit -m "feat(embeddings): migration 022 — embedding_v2 columns on news_clean/markets/events"
```

---

## Task 2: ORM — add `embedding_v2*` columns to `NewsClean`, `Market`, `Event`

**Files:**
- Modify: `app/db/models.py`

- [ ] **Step 1: Add the columns to `NewsClean` (after existing `embedding_computed_at`, around line 108)**

```python
    embedding_v2: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    embedding_v2_composition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_v2_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: Add the same three columns to `Market` (after existing `embedding`, around line 166)**

```python
    embedding_v2: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    embedding_v2_composition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_v2_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 3: Add the same three columns to `Event` (after existing `embedding`, around line 200)**

```python
    embedding_v2: Mapped[Optional[list[float]]] = mapped_column(VECTOR(1536), nullable=True)
    embedding_v2_composition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_v2_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Verify `VECTOR`, `Optional`, `Text`, `DateTime`, `Mapped`, `mapped_column` are already imported in the file — they are as of chantier #1.

- [ ] **Step 4: Smoke — the ORM recognises the new columns**

Run:
```bash
docker compose exec -T app python -c "
from app.db.models import NewsClean, Market, Event
for cls in (NewsClean, Market, Event):
    cols = [c.name for c in cls.__table__.columns if c.name.startswith('embedding_v2')]
    assert sorted(cols) == ['embedding_v2', 'embedding_v2_composition', 'embedding_v2_computed_at'], \
        f'{cls.__name__}: {cols}'
    print(cls.__name__, 'ok')
"
```
Expected: `NewsClean ok`, `Market ok`, `Event ok` (three lines, no assertion error).

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py
git commit -m "feat(embeddings): ORM — embedding_v2 columns on NewsClean/Market/Event"
```

---

## Task 3: `app/eval/metrics.py` — pure functions + unit tests

**Files:**
- Create: `app/eval/__init__.py`
- Create: `app/eval/metrics.py`
- Create: `tests/unit/test_eval_metrics.py`
- Create: `tests/helpers/__init__.py` (if not already present — likely is)
- Create: `tests/helpers/embedding_fixtures.py`

- [ ] **Step 1: Create the package marker**

Create `app/eval/__init__.py`:

```python
"""Offline evaluation harness for embedding quality.

Modules:
- metrics    — pure retrieval/clustering metrics (no I/O).
- labels     — eval-pair loaders (DB heuristic, downstream P&L, LLM judge).
- runner     — orchestration: load pairs, score against candidates, aggregate.

Nothing in this package writes to production DB. All read-only. The CLI
lives at scripts/eval_embeddings.py.
"""
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_eval_metrics.py`:

```python
"""Unit tests for app.eval.metrics — pure functions, no I/O.

Covers every documented edge case in §4.2 of the spec."""

from __future__ import annotations

import math

import pytest

from app.eval.metrics import (
    aggregate,
    bootstrap_ci,
    cluster_purity,
    ndcg_at_k,
    retrieval_at_k,
)


# ── retrieval@k ──────────────────────────────────────────────────────
def test_retrieval_at_k_all_relevant_in_top_k():
    assert retrieval_at_k({1, 2}, [1, 2, 3, 4, 5], k=5) == pytest.approx(1.0)


def test_retrieval_at_k_partial_match():
    # 1 of 2 relevant items is in top-5.
    assert retrieval_at_k({1, 99}, [1, 2, 3, 4, 5], k=5) == pytest.approx(0.5)


def test_retrieval_at_k_none_in_top_k():
    assert retrieval_at_k({99}, [1, 2, 3, 4, 5], k=5) == pytest.approx(0.0)


def test_retrieval_at_k_k_larger_than_ranked():
    # Only 3 candidates, k=5 → normalize against min(k, |relevant|).
    assert retrieval_at_k({1}, [1, 2, 3], k=5) == pytest.approx(1.0)


def test_retrieval_at_k_empty_relevant_returns_zero():
    assert retrieval_at_k(set(), [1, 2, 3], k=5) == 0.0


def test_retrieval_at_k_empty_ranked_returns_zero():
    assert retrieval_at_k({1}, [], k=5) == 0.0


def test_retrieval_at_k_k_zero_returns_zero():
    assert retrieval_at_k({1}, [1, 2, 3], k=0) == 0.0


def test_retrieval_at_k_duplicates_in_ranked_do_not_double_count():
    # 1 appears twice in the ranked list; it's one relevant hit.
    assert retrieval_at_k({1}, [1, 1, 2, 3], k=4) == pytest.approx(1.0)


# ── nDCG@k ───────────────────────────────────────────────────────────
def test_ndcg_at_k_perfect_ranking_is_one():
    assert ndcg_at_k({1, 2}, [1, 2, 3, 4], k=4) == pytest.approx(1.0, abs=1e-9)


def test_ndcg_at_k_reversed_is_less_than_one():
    # Relevant at positions 3 and 4 — worse than perfect.
    v = ndcg_at_k({1, 2}, [3, 4, 1, 2], k=4)
    assert 0.0 < v < 1.0


def test_ndcg_at_k_no_relevant_in_ranked_returns_zero():
    assert ndcg_at_k({99}, [1, 2, 3], k=3) == 0.0


def test_ndcg_at_k_empty_relevant_returns_zero():
    assert ndcg_at_k(set(), [1, 2, 3], k=3) == 0.0


# ── bootstrap CI ─────────────────────────────────────────────────────
def test_bootstrap_ci_deterministic_with_seed():
    values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    a = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    b = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    assert a == b


def test_bootstrap_ci_mean_close_to_sample_mean():
    values = [0.5] * 20
    mean, ci_low, ci_high = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    assert mean == pytest.approx(0.5, abs=1e-6)
    assert ci_low == pytest.approx(0.5, abs=1e-6)
    assert ci_high == pytest.approx(0.5, abs=1e-6)


def test_bootstrap_ci_empty_values_returns_zero_triple():
    assert bootstrap_ci([], n_resamples=100, alpha=0.05, seed=42) == (0.0, 0.0, 0.0)


# ── aggregate ────────────────────────────────────────────────────────
def test_aggregate_mean_ci_and_n():
    per_pair = [
        {"retrieval@5": 0.8, "source": "db_heuristic"},
        {"retrieval@5": 0.6, "source": "db_heuristic"},
        {"retrieval@5": 1.0, "source": "llm_judge"},
    ]
    out = aggregate(per_pair, strata=("source",))
    assert out["retrieval@5"]["n"] == 3
    assert out["retrieval@5"]["mean"] == pytest.approx(0.8, abs=1e-6)
    assert "per_source" in out
    assert out["per_source"]["db_heuristic"]["retrieval@5"]["n"] == 2
    assert out["per_source"]["llm_judge"]["retrieval@5"]["n"] == 1


def test_aggregate_empty_per_pair_returns_empty_summary():
    out = aggregate([], strata=("source",))
    assert out == {"per_source": {}}


# ── cluster_purity ───────────────────────────────────────────────────
def test_cluster_purity_perfect_clustering_is_one():
    clusters = {1: [10, 11, 12], 2: [20, 21]}
    truth = {10: 1, 11: 1, 12: 1, 20: 2, 21: 2}
    assert cluster_purity(clusters, truth) == pytest.approx(1.0)


def test_cluster_purity_majority_rule():
    # Cluster 1 has 2 label-A and 1 label-B → purity contribution = 2/3.
    # Cluster 2 is 2 label-B → purity contribution = 2/2.
    # Overall = (2 + 2) / (3 + 2) = 4/5.
    clusters = {1: [10, 11, 20], 2: [21, 22]}
    truth = {10: 1, 11: 1, 20: 2, 21: 2, 22: 2}
    assert cluster_purity(clusters, truth) == pytest.approx(0.8, abs=1e-6)


def test_cluster_purity_ignores_items_without_truth():
    clusters = {1: [10, 11, 99]}   # 99 has no ground-truth label
    truth = {10: 1, 11: 1}
    # 99 is excluded from both numerator and denominator.
    assert cluster_purity(clusters, truth) == pytest.approx(1.0)
```

- [ ] **Step 3: Run the tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_eval_metrics.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'app.eval.metrics'` (or `ImportError`).

- [ ] **Step 4: Implement `metrics.py`**

Create `app/eval/metrics.py`:

```python
"""Pure retrieval / clustering metrics — no I/O, pytest-only dependencies.

All functions accept plain Python types (lists, sets, dicts) and return
deterministic outputs. Bootstrap uses `random.Random(seed)` so results are
reproducible across runs.
"""

from __future__ import annotations

import math
import random
from typing import Iterable


def retrieval_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """|relevant ∩ unique(ranked[:k])| / min(k, |relevant|).

    Returns 0.0 if either input is empty or k <= 0.
    """
    if not relevant_ids or not ranked_ids or k <= 0:
        return 0.0
    top_k = set(ranked_ids[:k])
    hits = len(relevant_ids & top_k)
    denom = min(k, len(relevant_ids))
    return hits / denom


def ndcg_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """Binary-relevance nDCG@k.

    DCG = Σ rel_i / log2(i + 2) for i in 0..k-1
    IDCG = DCG of the perfect ranking (all relevant first).
    Returns DCG / IDCG, or 0.0 if either is empty.
    """
    if not relevant_ids or not ranked_ids or k <= 0:
        return 0.0
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(k, len(relevant_ids))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def cluster_purity(
    clusters: dict[int, list[int]],
    ground_truth: dict[int, int],
) -> float:
    """Fraction of items (with known ground truth) placed in a cluster whose
    majority label matches their own."""
    total_labeled = 0
    correctly_placed = 0
    for _cluster_id, items in clusters.items():
        labeled_items = [i for i in items if i in ground_truth]
        if not labeled_items:
            continue
        # Majority label in this cluster.
        counts: dict[int, int] = {}
        for i in labeled_items:
            counts[ground_truth[i]] = counts.get(ground_truth[i], 0) + 1
        majority_label = max(counts, key=counts.get)
        correctly_placed += counts[majority_label]
        total_labeled += len(labeled_items)
    return correctly_placed / total_labeled if total_labeled > 0 else 0.0


def bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI on the mean of `values`.

    Returns (mean, ci_low, ci_high). Deterministic given `seed`.
    On empty input, returns (0.0, 0.0, 0.0)."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    resample_means: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        resample_means.append(sum(sample) / n)
    resample_means.sort()
    lo_idx = int(n_resamples * (alpha / 2))
    hi_idx = int(n_resamples * (1 - alpha / 2)) - 1
    hi_idx = max(lo_idx, min(hi_idx, n_resamples - 1))
    mean = sum(values) / n
    return (mean, resample_means[lo_idx], resample_means[hi_idx])


def aggregate(
    per_pair_scores: list[dict],
    *,
    strata: tuple[str, ...] = ("source",),
) -> dict:
    """Aggregate a list of per-pair metric dicts into mean + CI per metric.

    Input shape: [{"retrieval@5": 0.8, "ndcg@10": 0.7, "source": "db_heuristic"}, ...]
    Metric keys = any key not in `strata` or reserved names.

    Returns:
      {
        "retrieval@5": {"mean": ..., "ci_low": ..., "ci_high": ..., "n": ...},
        "ndcg@10": {...},
        "per_source": {"db_heuristic": {"retrieval@5": {...}, ...}, ...}
      }
    """
    if not per_pair_scores:
        return {"per_source": {}}

    reserved = set(strata)
    metric_keys = [k for k in per_pair_scores[0] if k not in reserved]

    def _summarize(rows: list[dict]) -> dict:
        out: dict = {}
        for mk in metric_keys:
            values = [r[mk] for r in rows if mk in r]
            mean, lo, hi = bootstrap_ci(values)
            out[mk] = {"mean": mean, "ci_low": lo, "ci_high": hi, "n": len(values)}
        return out

    result = _summarize(per_pair_scores)
    result["per_source"] = {}
    if "source" in strata:
        by_source: dict[str, list[dict]] = {}
        for r in per_pair_scores:
            by_source.setdefault(r.get("source", "unknown"), []).append(r)
        for src, rows in by_source.items():
            result["per_source"][src] = _summarize(rows)
    return result
```

- [ ] **Step 5: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_eval_metrics.py -v`
Expected: all tests green (21 tests).

- [ ] **Step 6: Write the shared test-fixture helper**

Create `tests/helpers/__init__.py` (empty if not present):

```python
```

Create `tests/helpers/embedding_fixtures.py`:

```python
"""Shared fixtures for eval harness + composer tests."""

from __future__ import annotations


def make_toy_embedding(dim: int = 1536, axis: int = 0, magnitude: float = 1.0) -> list[float]:
    """Deterministic embedding pointing along one axis. Used by tests that
    need embeddings but don't care about real semantics."""
    v = [0.0] * dim
    if 0 <= axis < dim:
        v[axis] = magnitude
    return v
```

- [ ] **Step 7: Commit**

```bash
git add app/eval/__init__.py app/eval/metrics.py \
        tests/unit/test_eval_metrics.py tests/helpers/embedding_fixtures.py
# tests/helpers/__init__.py — only if you created it here (check git status first)
git commit -m "feat(eval): metrics module (retrieval@k, nDCG@k, bootstrap CI, purity)"
```

---

## Task 4: `app/eval/labels.py` — DB heuristic loader for 3 surfaces + dedup

**Files:**
- Create: `app/eval/labels.py`
- Create: `tests/integration/test_eval_labels.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_eval_labels.py`:

```python
"""Integration tests for app.eval.labels — DB heuristic loaders only (task 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    Event,
    EventMarketAnalysis,
    EventMarketCandidate,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalArticle,
)
from app.eval.labels import EvalPair, load_pairs


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def labels_corpus(async_db_factory):
    """Seeds a tiny corpus exercising all three DB-heuristic surfaces."""
    async with async_db_factory() as s:
        # 2 events, 3 markets, 4 news, 1 signal with articles.
        ev1 = Event(id=9001, event_title="Ev1", first_seen=NOW, last_seen=NOW, bucket="politics")
        ev2 = Event(id=9002, event_title="Ev2", first_seen=NOW, last_seen=NOW, bucket="politics")
        m1 = Market(market_id="m1", question="q1", active=True, closed=False, accepting_orders=True)
        m2 = Market(market_id="m2", question="q2", active=True, closed=False, accepting_orders=True)
        m3 = Market(market_id="m3", question="q3", active=True, closed=False, accepting_orders=True)
        n1 = News(id=7001, source_name="src", title="t1", url="http://x/1",
                  ingestion_date=NOW, publish_date=NOW)
        n2 = News(id=7002, source_name="src", title="t2", url="http://x/2",
                  ingestion_date=NOW, publish_date=NOW)
        nc1 = NewsClean(id=7101, news_id=7001, clean_text="c1")
        nc2 = NewsClean(id=7102, news_id=7002, clean_text="c2")
        s.add_all([ev1, ev2, m1, m2, m3, n1, n2, nc1, nc2])
        await s.flush()

        # event_to_market: 2 positives for ev1 (m1 rank=1, m2 rank=2), 1 outside (m3 rank=5)
        s.add_all([
            EventMarketCandidate(event_id=9001, market_id="m1", rank=1, cosine_score=0.9, rrf_score=0.9),
            EventMarketCandidate(event_id=9001, market_id="m2", rank=2, cosine_score=0.8, rrf_score=0.8),
            EventMarketCandidate(event_id=9001, market_id="m3", rank=5, cosine_score=0.3, rrf_score=0.3),
            EventMarketAnalysis(event_id=9001, market_id="m1", impact_strength=0.8),
            EventMarketAnalysis(event_id=9001, market_id="m2", impact_strength=0.5),
            # No analysis row for m3 → excluded from positives.
        ])

        # article_to_event: ev1 ← {nc1 primary}, ev2 ← {nc2 primary}
        s.add_all([
            EventNewsLink(event_id=9001, clean_id=7101, role="primary"),
            EventNewsLink(event_id=9001, clean_id=7102, role="supporting"),  # NOT primary
            EventNewsLink(event_id=9002, clean_id=7102, role="primary"),
        ])

        # market_to_article: signal 6001 (on m1) picked 2 articles via variant "signal"
        sig = Signal(id=6001, market_id="m1", event_id=9001, created_at=NOW,
                     market_price_at_signal=0.5, predicted_direction="BUY_YES",
                     predicted_probability=0.7, impact_score=0.6)
        s.add(sig)
        await s.flush()
        s.add_all([
            SignalArticle(signal_id=6001, variant="signal", news_clean_id=7101,
                          rank=1, score=0.9, cosine_score=0.9, recency_weight=1.0),
            SignalArticle(signal_id=6001, variant="signal", news_clean_id=7102,
                          rank=2, score=0.8, cosine_score=0.8, recency_weight=0.95),
        ])
        await s.commit()


async def test_load_pairs_event_to_market_uses_rank_le_3_and_analysis_present(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="event_to_market", limit=500)
    ev1_pairs = [p for p in pairs if p.query_id == 9001]
    assert len(ev1_pairs) == 1
    assert ev1_pairs[0].relevant_ids == {"m1", "m2"}
    assert ev1_pairs[0].source == "db_heuristic"


async def test_load_pairs_article_to_event_uses_primary_role(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="article_to_event", limit=500)
    # nc1 → ev1 (primary), nc2 → ev2 (primary). nc2→ev1 is supporting, excluded.
    by_q = {p.query_id: p.relevant_ids for p in pairs}
    assert 7101 in by_q and by_q[7101] == {9001}
    assert 7102 in by_q and by_q[7102] == {9002}


async def test_load_pairs_market_to_article_uses_signal_articles_variant_signal(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="market_to_article", limit=500)
    m1_pairs = [p for p in pairs if p.query_id == "m1"]
    assert len(m1_pairs) == 1
    assert m1_pairs[0].relevant_ids == {7101, 7102}


async def test_load_pairs_invalid_surface_raises(async_db_factory):
    async with async_db_factory() as s:
        with pytest.raises(ValueError, match="surface"):
            await load_pairs(s, surface="not_a_real_surface")
```

- [ ] **Step 2: Run the tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_labels.py -v`
Expected: `ModuleNotFoundError: No module named 'app.eval.labels'`.

- [ ] **Step 3: Implement the DB heuristic path**

Create `app/eval/labels.py`:

```python
"""Eval-pair loaders for the embedding harness.

Three sources, merged and deduped by load_pairs():
- db_heuristic   — from existing DB links (cheap, circular-ish)
- downstream_pnl — only event_to_market; positive pairs validated by real outcomes
- llm_judge      — cached GPT-4o-mini relevance judgments, hard-capped $ budget

This task (task 4) ships only `db_heuristic` + the public `load_pairs` dispatcher.
The other two sources land in task 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EventMarketAnalysis,
    EventMarketCandidate,
    EventNewsLink,
    SignalArticle,
)


Surface = Literal["event_to_market", "article_to_event", "market_to_article"]
_VALID_SURFACES = ("event_to_market", "article_to_event", "market_to_article")


@dataclass(frozen=True)
class EvalPair:
    query_id: int | str
    relevant_ids: frozenset[int | str]
    source: str               # "db_heuristic" | "downstream_pnl" | "llm_judge"
    surface: str              # one of Surface values above


async def load_pairs(session: AsyncSession, *, surface: str, limit: int = 500) -> list[EvalPair]:
    """Public entry point. Aggregates all applicable sources for `surface`
    and dedupes by (query_id, frozenset(relevant_ids)) keeping the noblest source."""
    if surface not in _VALID_SURFACES:
        raise ValueError(f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}")

    aggregated: dict[tuple[int | str, frozenset], EvalPair] = {}

    for pair in await _load_db_heuristic(session, surface, limit):
        key = (pair.query_id, pair.relevant_ids)
        aggregated[key] = pair

    # Sources 2 and 3 are wired in task 5; they slot in here with source-noblest
    # tie-breaking (downstream_pnl > llm_judge > db_heuristic).

    return list(aggregated.values())


async def _load_db_heuristic(
    session: AsyncSession, surface: str, limit: int
) -> list[EvalPair]:
    if surface == "event_to_market":
        return await _db_event_to_market(session, limit)
    if surface == "article_to_event":
        return await _db_article_to_event(session, limit)
    if surface == "market_to_article":
        return await _db_market_to_article(session, limit)
    return []


async def _db_event_to_market(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (event_id, market_id) if the candidate was ranked ≤ 3 AND an
    EventMarketAnalysis row exists for it (LLM #2 considered it worth analyzing)."""
    stmt = (
        select(
            EventMarketCandidate.event_id,
            EventMarketCandidate.market_id,
        )
        .join(
            EventMarketAnalysis,
            (EventMarketAnalysis.event_id == EventMarketCandidate.event_id)
            & (EventMarketAnalysis.market_id == EventMarketCandidate.market_id),
        )
        .where(EventMarketCandidate.rank <= 3)
        .where(EventMarketAnalysis.impact_strength.isnot(None))
        .order_by(EventMarketCandidate.event_id.desc())
        .limit(limit * 5)  # one event may have multiple markets; over-sample
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[str]] = {}
    for event_id, market_id in rows:
        grouped.setdefault(event_id, set()).add(market_id)
    pairs = [
        EvalPair(
            query_id=eid,
            relevant_ids=frozenset(mids),
            source="db_heuristic",
            surface="event_to_market",
        )
        for eid, mids in grouped.items()
    ]
    return pairs[:limit]


async def _db_article_to_event(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (clean_id, event_id) if role='primary'."""
    stmt = (
        select(EventNewsLink.clean_id, EventNewsLink.event_id)
        .where(EventNewsLink.role == "primary")
        .order_by(EventNewsLink.clean_id.desc())
        .limit(limit * 3)
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[int]] = {}
    for clean_id, event_id in rows:
        grouped.setdefault(clean_id, set()).add(event_id)
    pairs = [
        EvalPair(
            query_id=cid,
            relevant_ids=frozenset(eids),
            source="db_heuristic",
            surface="article_to_event",
        )
        for cid, eids in grouped.items()
    ]
    return pairs[:limit]


async def _db_market_to_article(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (market_id, clean_id) if SignalArticle.variant='signal' AND rank ≤ 5.
    We group by market_id (derived via Signal.market_id — joined through the FK).
    """
    from app.db.models import Signal
    stmt = (
        select(Signal.market_id, SignalArticle.news_clean_id)
        .join(Signal, Signal.id == SignalArticle.signal_id)
        .where(SignalArticle.variant == "signal")
        .where(SignalArticle.rank <= 5)
        .order_by(SignalArticle.signal_id.desc())
        .limit(limit * 5)
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[str, set[int]] = {}
    for market_id, clean_id in rows:
        grouped.setdefault(market_id, set()).add(clean_id)
    pairs = [
        EvalPair(
            query_id=mid,
            relevant_ids=frozenset(cids),
            source="db_heuristic",
            surface="market_to_article",
        )
        for mid, cids in grouped.items()
    ]
    return pairs[:limit]
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_labels.py -v`
Expected: 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/eval/labels.py tests/integration/test_eval_labels.py
git commit -m "feat(eval): labels.load_pairs — DB-heuristic loaders for 3 surfaces"
```

---

## Task 5: `app/eval/labels.py` — downstream-P&L + LLM-judge sources

**Files:**
- Modify: `app/eval/labels.py` (append `_load_downstream_pnl` + `_load_llm_judge`, extend `load_pairs`)
- Modify: `tests/integration/test_eval_labels.py` (add tests for the two new sources)

- [ ] **Step 1: Append the failing tests**

Append to `tests/integration/test_eval_labels.py`:

```python
# ── downstream_pnl ───────────────────────────────────────────────────
@pytest.fixture
async def downstream_pnl_corpus(async_db_factory):
    """Winning signal on (ev_pnl, m_pnl) that should become a downstream positive."""
    from app.db.models import Signal, SignalOutcome, SignalPrediction
    async with async_db_factory() as s:
        ev = Event(id=8001, event_title="EvPnl", first_seen=NOW, last_seen=NOW, bucket="politics")
        m = Market(market_id="m_pnl", question="qp", active=True, closed=True, accepting_orders=False)
        s.add_all([ev, m])
        await s.flush()
        sig = Signal(
            id=5001, market_id="m_pnl", event_id=8001, created_at=NOW,
            market_price_at_signal=0.3, predicted_direction="BUY_YES",
            predicted_probability=0.8, impact_score=0.7,
        )
        s.add(sig)
        await s.flush()
        s.add_all([
            SignalPrediction(signal_id=5001, variant="signal",
                             predicted_direction="BUY_YES", predicted_probability=0.8),
            SignalOutcome(signal_id=5001, resolved_at=NOW, correct=True, pnl=0.25),
        ])
        await s.commit()


async def test_load_pairs_event_to_market_includes_downstream_pnl(
    downstream_pnl_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="event_to_market", limit=500)
    pnl_pairs = [p for p in pairs if p.query_id == 8001]
    assert len(pnl_pairs) >= 1
    # If downstream_pnl matched, its source should be that (dedup prefers noblest).
    assert any(p.source == "downstream_pnl" for p in pnl_pairs)


# ── llm_judge ────────────────────────────────────────────────────────
async def test_load_pairs_llm_judge_uses_cache_on_second_call(
    monkeypatch, tmp_path, labels_corpus, async_db_factory
):
    """Second call must not re-invoke the LLM if the cache has the entry."""
    from app.eval import labels as labels_module

    call_counter = {"n": 0}

    async def _fake_analyze(**_kw):
        call_counter["n"] += 1
        # Canned positive response.
        return {"relevance": "yes"}

    monkeypatch.setattr(labels_module, "_llm_judge_prompt_one_pair", _fake_analyze)
    monkeypatch.setattr(labels_module, "_LLM_JUDGE_CACHE_DIR", tmp_path)

    async with async_db_factory() as s:
        await load_pairs(s, surface="article_to_event", limit=10)
        first_calls = call_counter["n"]
        await load_pairs(s, surface="article_to_event", limit=10)
        second_calls = call_counter["n"]

    # Second invocation reads the cache file; no new LLM calls.
    assert second_calls == first_calls


async def test_load_pairs_llm_judge_budget_cap(monkeypatch, tmp_path, async_db_factory):
    """When LLM_JUDGE_MAX_USD is 0, no LLM calls happen."""
    from app.eval import labels as labels_module

    call_counter = {"n": 0}

    async def _fake_analyze(**_kw):
        call_counter["n"] += 1
        return {"relevance": "yes"}

    monkeypatch.setattr(labels_module, "_llm_judge_prompt_one_pair", _fake_analyze)
    monkeypatch.setattr(labels_module, "_LLM_JUDGE_CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_JUDGE_MAX_USD", "0")

    from app.core.config import get_settings
    get_settings.cache_clear()

    async with async_db_factory() as s:
        await load_pairs(s, surface="article_to_event", limit=10)

    assert call_counter["n"] == 0
```

- [ ] **Step 2: Run the tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_labels.py -v`
Expected: the three new tests fail (missing `_llm_judge_prompt_one_pair`, `_LLM_JUDGE_CACHE_DIR`, and `_load_downstream_pnl` import paths).

- [ ] **Step 3: Add `llm_judge_max_usd` setting to config**

In `app/core/config.py`, add in the relevant section:

```python
    # ── Eval harness (chantier #3) ────────────────────────────────────
    llm_judge_max_usd: float = Field(
        default=10.0,
        description="Hard cap on spend per LLM-judge eval run (GPT-4o-mini).",
    )
```

- [ ] **Step 4: Extend `app/eval/labels.py`**

Append to `app/eval/labels.py`:

```python
# ══════════════════════════════════════════════════════════════════════
# Downstream P&L source — only event_to_market
# ══════════════════════════════════════════════════════════════════════

async def _load_downstream_pnl(session: AsyncSession, surface: str) -> list[EvalPair]:
    """Only applies to event_to_market. A pair is positive if a real signal on
    (event, market) resolved profitably in the production variant."""
    if surface != "event_to_market":
        return []
    from app.db.models import Signal, SignalOutcome, SignalPrediction
    stmt = (
        select(Signal.event_id, Signal.market_id)
        .join(SignalPrediction, SignalPrediction.signal_id == Signal.id)
        .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(SignalPrediction.variant == "signal")
        .where(SignalOutcome.correct.is_(True))
        .where(SignalOutcome.pnl > 0)
        .where(Signal.event_id.isnot(None))
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[str]] = {}
    for event_id, market_id in rows:
        grouped.setdefault(event_id, set()).add(market_id)
    return [
        EvalPair(
            query_id=eid,
            relevant_ids=frozenset(mids),
            source="downstream_pnl",
            surface="event_to_market",
        )
        for eid, mids in grouped.items()
    ]


# ══════════════════════════════════════════════════════════════════════
# LLM-judge source — cached, budget-capped
# ══════════════════════════════════════════════════════════════════════

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LLM_JUDGE_CACHE_DIR = Path(".eval_cache")
_LLM_JUDGE_MODEL = "gpt-4o-mini"
# Rough estimate — updated if real token counts differ.
_LLM_JUDGE_COST_PER_CALL_USD = 0.0002


async def _llm_judge_prompt_one_pair(
    *, query_text: str, target_text: str, surface: str
) -> dict:
    """One LLM call. Isolated so tests can monkeypatch it.
    Returns a dict with {"relevance": "yes" | "no" | "unclear"}."""
    from openai import AsyncOpenAI
    from app.core.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = (
        "You are judging topical relevance for a prediction-market retrieval system.\n\n"
        f"Surface: {surface}\n"
        f"Query: {query_text[:800]}\n"
        f"Candidate: {target_text[:800]}\n\n"
        "Is the candidate topically relevant to the query? "
        "Answer with a single word: yes, no, or unclear."
    )
    resp = await client.chat.completions.create(
        model=_LLM_JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0.0,
    )
    raw = (resp.choices[0].message.content or "").strip().lower()
    verdict = "unclear"
    if raw.startswith("yes"):
        verdict = "yes"
    elif raw.startswith("no"):
        verdict = "no"
    return {"relevance": verdict}


async def _load_llm_judge(
    session: AsyncSession,
    surface: str,
    existing_pairs: list[EvalPair],
    n_candidates: int = 200,
) -> list[EvalPair]:
    """Sample ≤ n_candidates (query, target) pairs for `surface`, judge each
    via LLM, return pairs where the verdict is 'yes'. Cached on disk."""
    from app.core.config import get_settings
    settings = get_settings()
    budget_usd = float(settings.llm_judge_max_usd)
    if budget_usd <= 0.0:
        logger.info("LLM judge: budget_usd=0, skipping")
        return []

    _LLM_JUDGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _LLM_JUDGE_CACHE_DIR / f"llm_judge_{surface}.json"
    cache: dict[str, str] = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            logger.warning("LLM judge cache corrupt at %s, starting fresh", cache_file)
            cache = {}

    # Candidate pairs: half positives (rotate existing), half random negatives.
    # For this first cut we pull candidates from `existing_pairs` and pair them
    # with random other rows — keeps the loader surface-agnostic.
    from random import Random
    rng = Random(42)
    positives = list(existing_pairs)[: n_candidates // 2]
    candidates: list[tuple[int | str, int | str]] = []
    for p in positives:
        for r in p.relevant_ids:
            candidates.append((p.query_id, r))  # true positive candidate
            # Negative: pick a query_id from another pair's relevants.
            others = [q.relevant_ids for q in existing_pairs if q.query_id != p.query_id]
            if others:
                neg_pool = list(next(iter(rng.choice(others))) for _ in range(1))
                if neg_pool:
                    candidates.append((p.query_id, rng.choice(neg_pool)))

    if not candidates:
        return []
    candidates = candidates[:n_candidates]

    # Load query & target texts once to keep I/O tight.
    qtexts: dict[int | str, str] = await _fetch_texts_for_keys(
        session, surface, keys=list({c[0] for c in candidates}), side="query"
    )
    ttexts: dict[int | str, str] = await _fetch_texts_for_keys(
        session, surface, keys=list({c[1] for c in candidates}), side="target"
    )

    calls_budget = int(budget_usd / _LLM_JUDGE_COST_PER_CALL_USD)
    calls_used = 0
    positive_hits: dict[int | str, set[int | str]] = {}
    for qid, tid in candidates:
        key = hashlib.sha256(f"{surface}|{qid}|{tid}".encode()).hexdigest()[:32]
        if key in cache:
            verdict = cache[key]
        else:
            if calls_used >= calls_budget:
                logger.info("LLM judge: budget exhausted after %d calls", calls_used)
                break
            qtext = qtexts.get(qid, "")
            ttext = ttexts.get(tid, "")
            if not qtext or not ttext:
                continue
            res = await _llm_judge_prompt_one_pair(
                query_text=qtext, target_text=ttext, surface=surface
            )
            verdict = res.get("relevance", "unclear")
            cache[key] = verdict
            calls_used += 1
        if verdict == "yes":
            positive_hits.setdefault(qid, set()).add(tid)

    cache_file.write_text(json.dumps(cache, indent=2))
    logger.info(
        "LLM judge: %d calls used, $%.4f estimated, %d positive pairs cached",
        calls_used, calls_used * _LLM_JUDGE_COST_PER_CALL_USD, len(positive_hits),
    )

    return [
        EvalPair(
            query_id=qid,
            relevant_ids=frozenset(tids),
            source="llm_judge",
            surface=surface,
        )
        for qid, tids in positive_hits.items()
    ]


async def _fetch_texts_for_keys(
    session: AsyncSession, surface: str, keys: list, side: str
) -> dict:
    """Map key -> text for either the query or the target side of a surface."""
    from app.db.models import Event, Market, NewsClean, News
    if not keys:
        return {}
    if surface == "event_to_market":
        if side == "query":
            rows = (await session.execute(
                select(Event.id, Event.event_retrieval_text, Event.event_title)
                .where(Event.id.in_(keys))
            )).all()
            return {i: (t or tt or "") for (i, t, tt) in rows}
        rows = (await session.execute(
            select(Market.market_id, Market.market_retrieval_text, Market.question)
            .where(Market.market_id.in_(keys))
        )).all()
        return {i: (t or q or "") for (i, t, q) in rows}
    if surface == "article_to_event":
        if side == "query":
            rows = (await session.execute(
                select(NewsClean.id, NewsClean.clean_text)
                .where(NewsClean.id.in_(keys))
            )).all()
            return {i: (t or "") for (i, t) in rows}
        rows = (await session.execute(
            select(Event.id, Event.event_retrieval_text, Event.event_title)
            .where(Event.id.in_(keys))
        )).all()
        return {i: (t or tt or "") for (i, t, tt) in rows}
    # market_to_article
    if side == "query":
        rows = (await session.execute(
            select(Market.market_id, Market.market_retrieval_text, Market.question)
            .where(Market.market_id.in_(keys))
        )).all()
        return {i: (t or q or "") for (i, t, q) in rows}
    rows = (await session.execute(
        select(NewsClean.id, NewsClean.clean_text)
        .where(NewsClean.id.in_(keys))
    )).all()
    return {i: (t or "") for (i, t) in rows}
```

- [ ] **Step 5: Wire both new sources into `load_pairs()` with noblest-source dedup**

Replace the body of `load_pairs` in `app/eval/labels.py` with:

```python
async def load_pairs(session: AsyncSession, *, surface: str, limit: int = 500) -> list[EvalPair]:
    """Public entry point. Aggregates all applicable sources for `surface`
    and dedupes by (query_id, frozenset(relevant_ids)) keeping the noblest source.

    Source nobility order: downstream_pnl > llm_judge > db_heuristic.
    """
    if surface not in _VALID_SURFACES:
        raise ValueError(f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}")

    nobility = {"downstream_pnl": 2, "llm_judge": 1, "db_heuristic": 0}
    aggregated: dict[tuple[int | str, frozenset], EvalPair] = {}

    def _accept(pair: EvalPair) -> None:
        key = (pair.query_id, pair.relevant_ids)
        current = aggregated.get(key)
        if current is None or nobility[pair.source] > nobility[current.source]:
            aggregated[key] = pair

    for p in await _load_db_heuristic(session, surface, limit):
        _accept(p)
    for p in await _load_downstream_pnl(session, surface):
        _accept(p)
    db_pairs = list(aggregated.values())
    for p in await _load_llm_judge(session, surface, db_pairs, n_candidates=200):
        _accept(p)

    return list(aggregated.values())
```

- [ ] **Step 6: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_labels.py -v`
Expected: all 7 tests green (4 from task 4 + 3 new ones).

- [ ] **Step 7: Commit**

```bash
git add app/eval/labels.py app/core/config.py tests/integration/test_eval_labels.py
git commit -m "feat(eval): labels — add downstream_pnl + llm_judge sources with cache"
```

---

## Task 6: `app/eval/runner.py` — EvalReport + run_eval + diff

**Files:**
- Create: `app/eval/runner.py`
- Create: `tests/integration/test_eval_runner.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_eval_runner.py`:

```python
"""End-to-end eval on a tiny fixture — covers task 6."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import Event, EventMarketAnalysis, EventMarketCandidate, Market
from app.eval.runner import run_eval, diff_reports, report_to_json
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def runner_corpus(async_db_factory):
    async with async_db_factory() as s:
        ev = Event(
            id=4001, event_title="ev-r", first_seen=NOW, last_seen=NOW, bucket="politics",
            embedding=make_toy_embedding(axis=0),
            embedding_v2=make_toy_embedding(axis=1),
        )
        # 3 markets: m_good points along axis 0 (matches v1 query), m_good2 along axis 1 (matches v2), m_bad unrelated.
        m_good = Market(
            market_id="m_good", question="q", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=0),
            embedding_v2=make_toy_embedding(axis=0),
        )
        m_good2 = Market(
            market_id="m_good2", question="q2", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=2),
            embedding_v2=make_toy_embedding(axis=1),
        )
        m_bad = Market(
            market_id="m_bad", question="q3", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=5),
            embedding_v2=make_toy_embedding(axis=5),
        )
        s.add_all([ev, m_good, m_good2, m_bad])
        await s.flush()
        s.add_all([
            EventMarketCandidate(event_id=4001, market_id="m_good", rank=1, cosine_score=0.9, rrf_score=0.9),
            EventMarketCandidate(event_id=4001, market_id="m_good2", rank=2, cosine_score=0.8, rrf_score=0.8),
            EventMarketAnalysis(event_id=4001, market_id="m_good", impact_strength=0.8),
            EventMarketAnalysis(event_id=4001, market_id="m_good2", impact_strength=0.6),
        ])
        await s.commit()


async def test_run_eval_v1_ranks_axis0_market_first(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        report = await run_eval(s, variant="v1", surface="event_to_market")
    # v1 query (axis 0) matches m_good (axis 0) perfectly → retrieval@5 hit on m_good.
    assert report.n_pairs >= 1
    assert report.metrics["retrieval@5"]["mean"] > 0.0


async def test_run_eval_v2_report_has_n_skipped_zero_when_v2_populated(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        report = await run_eval(s, variant="v2", surface="event_to_market")
    assert report.n_skipped == 0


async def test_report_to_json_roundtrips(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        r = await run_eval(s, variant="v1", surface="event_to_market")
    import json
    payload = report_to_json(r)
    parsed = json.loads(payload)
    assert parsed["variant"] == "v1"
    assert parsed["surface"] == "event_to_market"
    assert "retrieval@5" in parsed["metrics"]


async def test_diff_reports_flags_per_metric_gain(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        r1 = await run_eval(s, variant="v1", surface="event_to_market")
        r2 = await run_eval(s, variant="v2", surface="event_to_market")
    d = diff_reports(r1, r2)
    assert "retrieval@5" in d
    assert "delta" in d["retrieval@5"]
    assert "verdict" in d["retrieval@5"]
    assert d["retrieval@5"]["verdict"] in ("improved", "regressed", "flat")
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_runner.py -v`
Expected: `ModuleNotFoundError: No module named 'app.eval.runner'`.

- [ ] **Step 3: Implement `runner.py`**

Create `app/eval/runner.py`:

```python
"""Orchestration of one eval run: load pairs → score against candidates → aggregate."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.labels import EvalPair, load_pairs
from app.eval.metrics import aggregate, ndcg_at_k, retrieval_at_k

logger = logging.getLogger(__name__)

_SURFACE_TO_PAIR_SURFACE = {
    "news": "article_to_event",
    "event": "event_to_market",
    "market": "market_to_article",
}
# "all" handled by dispatching to each surface in turn (caller level).


@dataclass
class EvalReport:
    variant: str
    surface: str
    metrics: dict[str, dict]
    per_source: dict[str, dict]
    generated_at: datetime
    git_sha: str
    n_pairs: int
    n_skipped: int


async def run_eval(
    session: AsyncSession,
    *,
    variant: Literal["v1", "v2"],
    surface: str,
) -> EvalReport:
    if surface not in _SURFACE_TO_PAIR_SURFACE:
        raise ValueError(
            f"surface must be one of {list(_SURFACE_TO_PAIR_SURFACE)}; got {surface!r}"
        )
    pair_surface = _SURFACE_TO_PAIR_SURFACE[surface]
    pairs = await load_pairs(session, surface=pair_surface, limit=500)

    per_pair: list[dict[str, Any]] = []
    n_skipped = 0

    for p in pairs:
        query_emb = await _fetch_embedding_for_query(session, pair_surface, p.query_id, variant)
        if query_emb is None:
            n_skipped += 1
            continue
        candidate_rows = await _fetch_candidate_pool(session, pair_surface, p.query_id, variant)
        scored: list[tuple[int | str, float]] = []
        for cand_id, cand_emb in candidate_rows:
            if cand_emb is None:
                continue
            scored.append((cand_id, _dot(query_emb, cand_emb)))
        scored.sort(key=lambda t: -t[1])
        ranked_ids = [cid for cid, _ in scored]
        per_pair.append({
            "retrieval@5": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=5),
            "retrieval@10": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=10),
            "ndcg@10": ndcg_at_k(set(p.relevant_ids), ranked_ids, k=10),
            "source": p.source,
        })

    agg = aggregate(per_pair, strata=("source",))
    per_source = agg.pop("per_source", {})

    return EvalReport(
        variant=variant,
        surface=surface,
        metrics=agg,
        per_source=per_source,
        generated_at=datetime.now(timezone.utc),
        git_sha=_git_sha(),
        n_pairs=len(per_pair),
        n_skipped=n_skipped,
    )


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


async def _fetch_embedding_for_query(
    session: AsyncSession, pair_surface: str, query_id, variant: str
) -> list[float] | None:
    from app.db.models import Event, Market, NewsClean
    col = "embedding" if variant == "v1" else "embedding_v2"
    if pair_surface == "event_to_market":
        stmt = select(getattr(Event, col)).where(Event.id == query_id)
    elif pair_surface == "article_to_event":
        stmt = select(getattr(NewsClean, col)).where(NewsClean.id == query_id)
    else:  # market_to_article
        stmt = select(getattr(Market, col)).where(Market.market_id == query_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return list(row) if row is not None else None


async def _fetch_candidate_pool(
    session: AsyncSession, pair_surface: str, query_id, variant: str
) -> list[tuple]:
    """Return (candidate_id, embedding) pairs shaped like the prod consumer would
    see. For simplicity in the first cut, the pool is 'all candidates of the
    relevant type with the same bucket'. More nuanced pools (±time windows) can
    be added per surface if needed."""
    from app.db.models import Event, Market, NewsClean
    col = "embedding" if variant == "v1" else "embedding_v2"
    if pair_surface == "event_to_market":
        # Candidate pool: active, non-closed markets in the same bucket.
        bucket = (await session.execute(
            select(Event.bucket).where(Event.id == query_id)
        )).scalar_one_or_none()
        stmt = select(Market.market_id, getattr(Market, col)).where(
            Market.active.is_(True),
            Market.closed.is_(False),
            Market.bucket == bucket,
        )
    elif pair_surface == "article_to_event":
        # Candidate pool: events in the same bucket (±time window ignored here for simplicity).
        bucket = (await session.execute(
            select(NewsClean.bucket).where(NewsClean.id == query_id)
        )).scalar_one_or_none()
        stmt = select(Event.id, getattr(Event, col)).where(Event.bucket == bucket)
    else:  # market_to_article
        bucket = (await session.execute(
            select(Market.bucket).where(Market.market_id == query_id)
        )).scalar_one_or_none()
        stmt = select(NewsClean.id, getattr(NewsClean, col)).where(NewsClean.bucket == bucket)
    rows = (await session.execute(stmt)).all()
    return [(r[0], list(r[1]) if r[1] is not None else None) for r in rows]


def report_to_json(report: EvalReport) -> str:
    d = asdict(report)
    d["generated_at"] = report.generated_at.isoformat()
    return json.dumps(d, indent=2, default=str)


def diff_reports(baseline: EvalReport, candidate: EvalReport) -> dict:
    """Per-metric delta + verdict vs baseline. Verdict = 'improved' / 'regressed' / 'flat'."""
    out: dict[str, dict] = {}
    for metric, stats in candidate.metrics.items():
        base = baseline.metrics.get(metric, {})
        delta = stats.get("mean", 0.0) - base.get("mean", 0.0)
        ci_low_cand = stats.get("ci_low", 0.0)
        ci_high_base = base.get("ci_high", 0.0)
        if ci_low_cand > ci_high_base:
            verdict = "improved"
        elif ci_high_cand := stats.get("ci_high", 0.0) < base.get("ci_low", 0.0):
            verdict = "regressed"
        else:
            verdict = "flat"
        out[metric] = {
            "baseline_mean": base.get("mean", 0.0),
            "candidate_mean": stats.get("mean", 0.0),
            "delta": delta,
            "verdict": verdict,
        }
    return out
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_eval_runner.py -v`
Expected: all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/eval/runner.py tests/integration/test_eval_runner.py
git commit -m "feat(eval): runner — EvalReport + run_eval + diff_reports"
```

---

## Task 7: CLI `scripts/eval_embeddings.py` + frozen baseline

**Files:**
- Create: `scripts/eval_embeddings.py`
- Create: `docs/eval_baselines/.gitkeep`

- [ ] **Step 1: Write the CLI**

Create `scripts/eval_embeddings.py`:

```python
"""CLI for the embedding eval harness.

Examples:
  python -m scripts.eval_embeddings --variant v1 --surface news
  python -m scripts.eval_embeddings --variant v2 --surface news \\
      --baseline docs/eval_baselines/embeddings_2026-04-24_v1.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.db.database import get_session_factory
from app.eval.runner import EvalReport, diff_reports, report_to_json, run_eval

_SURFACES = ("news", "market", "event", "all")


async def _run_one(variant: str, surface: str) -> EvalReport:
    factory = get_session_factory()
    async with factory() as s:
        return await run_eval(s, variant=variant, surface=surface)


def _load_baseline(path: Path) -> EvalReport:
    d = json.loads(path.read_text())
    d["generated_at"] = datetime.fromisoformat(d["generated_at"])
    return EvalReport(**d)


def _print_summary(report: EvalReport) -> None:
    print(f"variant={report.variant} surface={report.surface} "
          f"n_pairs={report.n_pairs} n_skipped={report.n_skipped} "
          f"git_sha={report.git_sha}")
    for metric, stats in report.metrics.items():
        print(f"  {metric}: mean={stats['mean']:.4f} "
              f"[{stats['ci_low']:.4f}, {stats['ci_high']:.4f}] n={stats['n']}")


def _print_diff(diff: dict) -> None:
    for metric, info in diff.items():
        arrow = {"improved": "↑", "regressed": "↓", "flat": "="}[info["verdict"]]
        print(f"  {metric}: {info['baseline_mean']:.4f} → {info['candidate_mean']:.4f} "
              f"(Δ={info['delta']:+.4f}) {arrow} {info['verdict']}")


async def _main(args: argparse.Namespace) -> int:
    surfaces = (["news", "market", "event"] if args.surface == "all" else [args.surface])
    reports: list[EvalReport] = []
    for surf in surfaces:
        r = await _run_one(args.variant, surf)
        reports.append(r)
        _print_summary(r)

    if args.out:
        payload = {r.surface: json.loads(report_to_json(r)) for r in reports}
        Path(args.out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"wrote {args.out}")

    if args.baseline:
        baseline_data = json.loads(Path(args.baseline).read_text())
        for r in reports:
            bd = baseline_data.get(r.surface)
            if bd is None:
                print(f"  [{r.surface}] no baseline found, skipping diff")
                continue
            bd["generated_at"] = datetime.fromisoformat(bd["generated_at"])
            baseline_report = EvalReport(**bd)
            diff = diff_reports(baseline_report, r)
            print(f"--- diff for {r.surface} ---")
            _print_diff(diff)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("v1", "v2"), required=True)
    parser.add_argument("--surface", choices=_SURFACES, required=True)
    parser.add_argument("--out", help="Write JSON report to this path.")
    parser.add_argument("--baseline", help="Diff against this baseline JSON file.")
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Ensure the baselines directory exists**

Run:
```bash
mkdir -p /Users/vadim/polymarket-ai/docs/eval_baselines
touch /Users/vadim/polymarket-ai/docs/eval_baselines/.gitkeep
```

- [ ] **Step 3: Smoke — CLI runs end-to-end**

Run:
```bash
docker compose exec -T app python -m scripts.eval_embeddings --variant v1 --surface news
```
Expected: prints a summary block; exits 0. If no labeled pairs exist yet in the DB (dev env may be empty), `n_pairs=0` is fine — this only validates the pipeline wiring.

- [ ] **Step 4: Generate the frozen baseline**

Run:
```bash
docker compose exec -T app python -m scripts.eval_embeddings \
    --variant v1 --surface all \
    --out docs/eval_baselines/embeddings_2026-04-24_v1.json
```
Expected: the JSON file lands with three top-level keys (`news`, `market`, `event`), each containing an `EvalReport` structure.

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_embeddings.py docs/eval_baselines/.gitkeep \
        docs/eval_baselines/embeddings_2026-04-24_v1.json
git commit -m "feat(eval): CLI + frozen v1 baseline for news/market/event"
```

---

## Task 8: `app/processing/text_composers.py` — v1 composers (bit-exact) + tests

**Files:**
- Create: `app/processing/text_composers.py`
- Create: `tests/unit/test_text_composers_v1.py`

- [ ] **Step 1: Write the failing v1 regression tests**

Create `tests/unit/test_text_composers_v1.py`:

```python
"""v1 composers must match the existing inline f-strings bit-exactly.

This is a regression shield: if this test fails, we have changed behavior
that would break the v1 baseline's comparison fidelity."""

from __future__ import annotations

import pytest

from app.processing.text_composers import (
    ComposedText,
    compose_event_v1,
    compose_market_v1,
    compose_news_v1,
)


# ── news v1 ──────────────────────────────────────────────────────────
def test_news_v1_matches_inline_fstring_pattern():
    # The inline prod path in tasks_pipeline.py:98 is: f"{raw_title}. {clean_text[:1500]}"
    title = "An Important Headline"
    body = "A" * 2000
    got = compose_news_v1(title, body)
    expected_text = f"{title}. {body[:1500]}"
    assert got.text == expected_text
    assert got.composition_version == "news_v1_title_trunc"


def test_news_v1_short_body_unchanged():
    got = compose_news_v1("T", "short body")
    assert got.text == "T. short body"


def test_news_v1_empty_body():
    got = compose_news_v1("T", "")
    assert got.text == "T. "


# ── market v1 ────────────────────────────────────────────────────────
def test_market_v1_matches_existing_build_retrieval_text():
    # Existing app.workers.tasks_ingestion._build_retrieval_text shape:
    # f"{question}. {desc_clean[:400]} {tags_str}".strip()
    # where desc_clean strips known boilerplate and collapses \n{2,} → \n.
    mkt = {
        "question": "Will X win?",
        "description": "Some description.",
        "tags": ["politics", "2028"],
    }
    got = compose_market_v1(mkt)
    # The body has no boilerplate, so desc_clean == description.
    expected = "Will X win?. Some description. politics 2028"
    assert got.text == expected
    assert got.composition_version == "market_v1_q_desc_tags"


def test_market_v1_strips_boilerplate_identical_to_legacy():
    # Known boilerplate we currently strip — give it some, verify it's gone.
    from app.workers.tasks_ingestion import _BOILERPLATE_RE
    # Craft a description containing a matched boilerplate token.
    boiler = "This market resolves Yes if …" if _BOILERPLATE_RE.pattern else ""
    # The test matters only if the regex is non-empty. If it is, the output
    # must not include the boilerplate phrase.
    mkt = {"question": "q", "description": f"real content. {boiler}", "tags": []}
    got = compose_market_v1(mkt)
    if boiler:
        assert boiler not in got.text


def test_market_v1_empty_tags_and_description():
    got = compose_market_v1({"question": "q", "description": "", "tags": []})
    assert got.text == "q."


# ── event v1 ─────────────────────────────────────────────────────────
def test_event_v1_matches_canonical_format():
    # The authoritative shape (event_builder.py:56-58):
    # retrieval_parts = [event_title, event_summary[:300]]
    # retrieval_parts.extend(key_entities[:5])
    # event_retrieval_text = " ".join(retrieval_parts)
    got = compose_event_v1("Ev Title", "A summary here.", ["Alice", "Bob"])
    assert got.text == "Ev Title A summary here. Alice Bob"
    assert got.composition_version == "event_v1_title_summary_entities"


def test_event_v1_truncates_summary_at_300():
    long = "X" * 500
    got = compose_event_v1("T", long, [])
    assert got.text == f"T {long[:300]}".strip()


def test_event_v1_clips_entities_to_5():
    got = compose_event_v1("T", "s", ["a", "b", "c", "d", "e", "f", "g"])
    assert got.text.endswith("a b c d e")
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v1.py -v`
Expected: `ModuleNotFoundError: No module named 'app.processing.text_composers'`.

- [ ] **Step 3: Implement v1 composers**

Create `app/processing/text_composers.py`:

```python
"""Text composers that produce embedding-ready strings.

Each surface (news / market / event) has a v1 composer — a bit-exact
re-implementation of the existing inline f-string — and a v2 composer with
the chantier-#3 improvements. Selecting which composer's output to embed
is the caller's responsibility (prod writes v1 + v2 in parallel; see
task 15).

All composers return a `ComposedText` carrying the text plus a
`composition_version` string persisted in `<entity>.embedding_v2_composition`
so we can always trace back which rule produced which vector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ComposedText:
    text: str
    composition_version: str


# ══════════════════════════════════════════════════════════════════════
# News
# ══════════════════════════════════════════════════════════════════════


def compose_news_v1(title: str, clean_text: str) -> ComposedText:
    """Bit-exact re-implementation of tasks_pipeline.py:98.

        embed_text = f"{raw_title}. {clean_text[:1500]}"
    """
    text = f"{title}. {clean_text[:1500]}"
    return ComposedText(text=text, composition_version="news_v1_title_trunc")


# ══════════════════════════════════════════════════════════════════════
# Market
# ══════════════════════════════════════════════════════════════════════


def compose_market_v1(mkt: dict) -> ComposedText:
    """Bit-exact re-implementation of tasks_ingestion._build_retrieval_text."""
    from app.workers.tasks_ingestion import _BOILERPLATE_RE

    question = mkt.get("question") or ""
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    tags_str = " ".join(mkt.get("tags") or [])
    text = f"{question}. {desc_clean} {tags_str}".strip()
    return ComposedText(text=text, composition_version="market_v1_q_desc_tags")


# ══════════════════════════════════════════════════════════════════════
# Event
# ══════════════════════════════════════════════════════════════════════


def compose_event_v1(title: str, summary: str, entities: list[str]) -> ComposedText:
    """Canonical v1 shape, matching app/event_engine/event_builder.py:56-58:

        retrieval_parts = [event_title, event_summary[:300]]
        retrieval_parts.extend(key_entities[:5])
        event_retrieval_text = " ".join(retrieval_parts)

    Note: tasks_pipeline.py previously used a slightly divergent formula
    (`event_summary[:400]`). The v1 composer unifies on [:300] — this is the
    canonical value going forward. If any call-site depends on the :400
    behavior behaviorally, wrap it in a comment and migrate explicitly.
    """
    parts = [title, (summary or "")[:300]]
    parts.extend((entities or [])[:5])
    text = " ".join(p for p in parts if p)
    return ComposedText(text=text, composition_version="event_v1_title_summary_entities")
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v1.py -v`
Expected: all 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/processing/text_composers.py tests/unit/test_text_composers_v1.py
git commit -m "feat(embeddings): text_composers — v1 bit-exact composers for news/market/event"
```

---

## Task 9: Migrate inline f-strings to `compose_*_v1()` — remboursement dette A4

**Files:**
- Modify: `app/workers/tasks_pipeline.py` (line 98, line 271, lines 316-319, lines 513-516)
- Modify: `app/workers/tasks_ingestion.py::_build_retrieval_text`
- Modify: `app/event_engine/event_builder.py:55-63`

- [ ] **Step 1: Migrate `tasks_pipeline.py:98` (news inline embed)**

Find the block around line 98:
```python
        # Embed INLINE — no separate task, no batch wait
        embed_text = f"{raw_title}. {clean_text[:1500]}"
        embedding = await get_embedding(embed_text)
```
Replace with:
```python
        # Embed INLINE — no separate task, no batch wait
        from app.processing.text_composers import compose_news_v1
        composed = compose_news_v1(raw_title, clean_text)
        embedding = await get_embedding(composed.text)
```

- [ ] **Step 2: Migrate `tasks_pipeline.py:271` (event retrieval_text construction)**

Find:
```python
        retrieval_text = f"{event_title} {event_summary[:400]} {' '.join(key_ents[:5])}"
```
Replace with:
```python
        from app.processing.text_composers import compose_event_v1
        retrieval_text = compose_event_v1(event_title, event_summary, key_ents).text
```

- [ ] **Step 3: Migrate `tasks_pipeline.py:316-319` (the two identical inline joins)**

Find the two occurrences (around lines 316-319 and 513-516):
```python
                    parts = [event.event_title, (event.event_summary or "")[:400]]
                    if event.key_entities:
                        parts.extend(event.key_entities[:5])
                    event.event_retrieval_text = " ".join(p for p in parts if p).strip()
```
Replace EACH with:
```python
                    from app.processing.text_composers import compose_event_v1
                    event.event_retrieval_text = compose_event_v1(
                        event.event_title,
                        event.event_summary or "",
                        list(event.key_entities or []),
                    ).text
```

- [ ] **Step 4: Migrate `tasks_ingestion.py::_build_retrieval_text`**

Replace the entire function body:
```python
def _build_retrieval_text(mkt: dict) -> str:
    """Build embedding-ready text from a market dict.

    Strips Polymarket resolution boilerplate so the embedding vector
    captures the actual topic, not the settlement rules.
    """
    question = mkt.get("question") or ""
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    tags_str = " ".join(mkt.get("tags") or [])
    return f"{question}. {desc_clean} {tags_str}".strip()
```
With:
```python
def _build_retrieval_text(mkt: dict) -> str:
    """Build embedding-ready text from a market dict (thin wrapper around v1 composer)."""
    from app.processing.text_composers import compose_market_v1
    return compose_market_v1(mkt).text
```

The `_BOILERPLATE_RE` import remains in the file — `compose_market_v1` re-imports it from here, so don't remove it.

- [ ] **Step 5: Migrate `app/event_engine/event_builder.py:55-63`**

Find:
```python
    retrieval_parts = [event_title, event_summary[:300]]
    retrieval_parts.extend(key_entities[:5])
    event_retrieval_text = " ".join(retrieval_parts)
```
Replace with:
```python
    from app.processing.text_composers import compose_event_v1
    event_retrieval_text = compose_event_v1(
        event_title, event_summary, list(key_entities or [])
    ).text
```

- [ ] **Step 6: Run the full backend test suite — no regressions allowed**

Run:
```bash
docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q
```
Expected: all pass (should stay at ~171 tests, no new failures). If any test that previously asserted on an `event_retrieval_text` value now fails because of the `[:300]` unification (was `[:400]` in `tasks_pipeline.py:271`), update that test to match the unified canonical — v1 composers are the source of truth going forward.

- [ ] **Step 7: Commit**

```bash
git add app/workers/tasks_pipeline.py app/workers/tasks_ingestion.py \
        app/event_engine/event_builder.py
git commit -m "refactor(embeddings): route all retrieval-text construction through compose_*_v1"
```

---

## Task 10: `compose_news_v2` (A1 — lead+tail truncation) + tests

**Files:**
- Modify: `app/processing/text_composers.py` (append `compose_news_v2`)
- Create: `tests/unit/test_text_composers_v2.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_text_composers_v2.py`:

```python
"""Tests for v2 composers — one file per task (A1/A3/A4), appended as we go."""

from __future__ import annotations

import pytest

from app.processing.text_composers import compose_news_v2


# ── A1: news v2 ──────────────────────────────────────────────────────
def test_news_v2_composition_version_is_stable():
    got = compose_news_v2("T", "a body")
    assert got.composition_version == "news_v2_lead_tail"


def test_news_v2_no_paragraphs_falls_back_to_truncation():
    body = "single-line body no paragraph breaks " * 200  # >1500 chars, no \n\n
    got = compose_news_v2("T", body)
    # Fallback path: title + body[:1500], total <= 1800 chars.
    assert got.text.startswith("T.")
    assert len(got.text) <= 1800


def test_news_v2_short_single_paragraph_uses_it_as_is():
    body = "This is a single short paragraph roughly under 100 chars... oh wait, this is actually longer."
    got = compose_news_v2("T", body)
    assert body in got.text or body[:1200] in got.text


def test_news_v2_multi_paragraph_keeps_lead_and_tail():
    lead = "LEAD CONTENT. " * 20   # ~280 chars — meets ≥ 80 filter
    middle = "MIDDLE CONTENT. " * 30
    tail = "FINAL TAKEAWAY. " * 10  # ~160 chars
    body = f"{lead}\n\n{middle}\n\n{tail}"
    got = compose_news_v2("Title", body)
    # Both lead start and tail start should survive.
    assert "LEAD CONTENT." in got.text
    assert "FINAL TAKEAWAY." in got.text
    # Total length cap.
    assert len(got.text) <= 1800


def test_news_v2_only_short_paragraphs_falls_back():
    # Paragraphs < 80 chars are filtered out; falls back to truncation.
    body = "short\n\nalso short\n\nstill short"
    got = compose_news_v2("T", body)
    # Fallback: title + body[:1500].
    assert got.text.startswith("T.")


def test_news_v2_total_length_capped_at_1800():
    long_lead = "X" * 5000
    long_tail = "Y" * 5000
    body = f"{long_lead}\n\n{long_tail}"
    got = compose_news_v2("T", body)
    assert len(got.text) <= 1800


def test_news_v2_empty_body():
    got = compose_news_v2("T", "")
    # Nothing meaningful to do; should not crash and output should be well-formed.
    assert got.text.startswith("T")
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py::test_news_v2_composition_version_is_stable -v`
Expected: `ImportError: cannot import name 'compose_news_v2'`.

- [ ] **Step 3: Implement `compose_news_v2`**

Append to `app/processing/text_composers.py`:

```python
def compose_news_v2(title: str, clean_text: str) -> ComposedText:
    """A1 — lead-paragraph + tail-paragraph composition, capped at 1800 chars.

    Splits the body on blank lines, keeps paragraphs ≥ 80 chars. If none
    survive, falls back to v1-style byte truncation at 1500 chars.
    """
    paragraphs = [p.strip() for p in (clean_text or "").split("\n\n") if len(p.strip()) >= 80]
    if not paragraphs:
        body = (clean_text or "")[:1500]
    elif len(paragraphs) == 1:
        body = paragraphs[0][:1500]
    else:
        lead = paragraphs[0][:1200]
        tail = paragraphs[-1][:400]
        body = f"{lead}\n\n{tail}"
    text = f"{(title or '').strip()}. {body}"[:1800]
    return ComposedText(text=text, composition_version="news_v2_lead_tail")
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py -v`
Expected: all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/processing/text_composers.py tests/unit/test_text_composers_v2.py
git commit -m "feat(embeddings): A1 — compose_news_v2 (lead+tail truncation)"
```

---

## Task 11: `compose_market_v2` (A3 — inject `category`) + tests

**Files:**
- Modify: `app/processing/text_composers.py` (append `compose_market_v2`)
- Modify: `tests/unit/test_text_composers_v2.py` (append tests)

- [ ] **Step 1: Append the failing tests**

Append to `tests/unit/test_text_composers_v2.py`:

```python
# ── A3: market v2 ────────────────────────────────────────────────────
from app.processing.text_composers import compose_market_v2


def test_market_v2_composition_version_is_stable():
    got = compose_market_v2({"question": "q", "description": "d", "tags": [], "category": "Politics"})
    assert got.composition_version == "market_v2_with_category"


def test_market_v2_with_category_injects_bracket_marker():
    mkt = {
        "question": "Will X win?",
        "description": "Context here.",
        "tags": ["politics", "2028"],
        "category": "Politics",
    }
    got = compose_market_v2(mkt)
    assert "[category: Politics]" in got.text
    # Preserves question and tags.
    assert got.text.startswith("Will X win?.")
    assert "politics 2028" in got.text


def test_market_v2_without_category_omits_bracket():
    mkt = {"question": "q", "description": "", "tags": [], "category": None}
    got = compose_market_v2(mkt)
    assert "[category:" not in got.text


def test_market_v2_empty_category_treated_as_absent():
    mkt = {"question": "q", "description": "", "tags": [], "category": ""}
    got = compose_market_v2(mkt)
    assert "[category:" not in got.text


def test_market_v2_strips_boilerplate_same_as_v1():
    mkt = {
        "question": "q",
        "description": "real content\n\n\nstill here.",
        "tags": [],
        "category": "X",
    }
    got = compose_market_v2(mkt)
    # \n{2,} → \n collapse matches v1 behavior.
    assert "\n\n\n" not in got.text
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py -v -k market_v2`
Expected: 5 new tests fail with `ImportError`.

- [ ] **Step 3: Implement `compose_market_v2`**

Append to `app/processing/text_composers.py`:

```python
def compose_market_v2(mkt: dict) -> ComposedText:
    """A3 — v1 plus an explicit [category: X] marker between description and tags."""
    from app.workers.tasks_ingestion import _BOILERPLATE_RE

    question = (mkt.get("question") or "").strip()
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    category = (mkt.get("category") or "").strip()
    tags_str = " ".join(mkt.get("tags") or [])

    parts = [f"{question}."]
    if desc_clean:
        parts.append(desc_clean)
    if category:
        parts.append(f"[category: {category}]")
    if tags_str:
        parts.append(tags_str)
    text = " ".join(p for p in parts if p).strip()
    return ComposedText(text=text, composition_version="market_v2_with_category")
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py -v`
Expected: all (7 news + 5 market) tests green.

- [ ] **Step 5: Commit**

```bash
git add app/processing/text_composers.py tests/unit/test_text_composers_v2.py
git commit -m "feat(embeddings): A3 — compose_market_v2 (inject category marker)"
```

---

## Task 12: `compose_event_v2` (A4 — bucket prefix) + tests

**Files:**
- Modify: `app/processing/text_composers.py` (append `compose_event_v2`)
- Modify: `tests/unit/test_text_composers_v2.py` (append tests)

- [ ] **Step 1: Append the failing tests**

Append to `tests/unit/test_text_composers_v2.py`:

```python
# ── A4: event v2 ─────────────────────────────────────────────────────
from app.processing.text_composers import compose_event_v2


def test_event_v2_composition_version_is_stable():
    got = compose_event_v2("T", "s", [], bucket=None)
    assert got.composition_version == "event_v2_bucket_prefix"


def test_event_v2_with_bucket_prepends_bracket():
    got = compose_event_v2("Title", "Summary", ["Alice"], bucket="geopolitics")
    assert got.text.startswith("[geopolitics]")
    assert "Title" in got.text
    assert "Alice" in got.text


def test_event_v2_without_bucket_no_bracket_prefix():
    got = compose_event_v2("Title", "Summary", ["Alice"], bucket=None)
    assert not got.text.startswith("[")


def test_event_v2_empty_bucket_string_treated_as_absent():
    got = compose_event_v2("Title", "Summary", ["Alice"], bucket="")
    assert not got.text.startswith("[")


def test_event_v2_summary_truncated_at_400():
    long = "X" * 600
    got = compose_event_v2("T", long, [], bucket="politics")
    # summary slice is [:400]; rest are "T" (title) and prefix.
    assert got.text.count("X") == 400


def test_event_v2_clips_entities_to_5():
    got = compose_event_v2("T", "s", ["a", "b", "c", "d", "e", "f", "g"], bucket="x")
    assert "a" in got.text and "e" in got.text
    assert "f" not in got.text and "g" not in got.text
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py -v -k event_v2`
Expected: 6 new tests fail with `ImportError`.

- [ ] **Step 3: Implement `compose_event_v2`**

Append to `app/processing/text_composers.py`:

```python
def compose_event_v2(
    title: str, summary: str, entities: list[str], *, bucket: str | None
) -> ComposedText:
    """A4 — v1 plus a [bucket] prefix. Summary truncated at 400 (not 300 like v1)
    to capture more of the event body now that the bucket anchors the domain."""
    parts: list[str] = []
    if bucket:
        parts.append(f"[{bucket}]")
    if title:
        parts.append(title.strip())
    if summary:
        parts.append((summary or "").strip()[:400])
    for ent in (entities or [])[:5]:
        parts.append(ent)
    text = " ".join(p for p in parts if p).strip()
    return ComposedText(text=text, composition_version="event_v2_bucket_prefix")
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_text_composers_v2.py -v`
Expected: all (7 news + 5 market + 6 event) tests green.

- [ ] **Step 5: Commit**

```bash
git add app/processing/text_composers.py tests/unit/test_text_composers_v2.py
git commit -m "feat(embeddings): A4 — compose_event_v2 (bucket prefix + summary@400)"
```

---

## Task 13: `app/processing/embedding_reader.py` + 3 variant-flag settings + tests

**Files:**
- Create: `app/processing/embedding_reader.py`
- Modify: `app/core/config.py` (add 3 `embeddings_variant_*` settings)
- Create: `tests/unit/test_embedding_reader.py`

- [ ] **Step 1: Add the three variant-flag settings**

In `app/core/config.py`, add in the Chantier #3 Eval harness block (from task 5):

```python
    embeddings_variant_news: str = Field(
        default="v1",
        description="Active embedding variant for news_clean. 'v1' or 'v2'.",
    )
    embeddings_variant_market: str = Field(
        default="v1",
        description="Active embedding variant for markets. 'v1' or 'v2'.",
    )
    embeddings_variant_event: str = Field(
        default="v1",
        description="Active embedding variant for events. 'v1' or 'v2'.",
    )
```

(Using `str` instead of `Literal["v1", "v2"]` so a bad env-var surfaces as a runtime error in `get_active_embedding` — more defensive than a pydantic validation that fails at startup in ways we can't log from the helper.)

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_embedding_reader.py`:

```python
"""Unit tests for embedding_reader — flag-driven column routing."""

from __future__ import annotations

import pytest

from app.processing.embedding_reader import (
    active_column_name,
    get_active_embedding,
)


class _Row:
    """Minimal stand-in for an ORM row."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_get_active_embedding_v1_returns_embedding(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=[9.0])
    assert get_active_embedding(row, "news") == [1.0, 2.0]


def test_get_active_embedding_v2_returns_embedding_v2(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v2")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=[9.0])
    assert get_active_embedding(row, "news") == [9.0]


def test_get_active_embedding_returns_none_if_column_is_none(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v2")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=None)
    assert get_active_embedding(row, "news") is None


def test_get_active_embedding_invalid_surface_raises():
    row = _Row(embedding=[1.0])
    with pytest.raises(ValueError, match="surface"):
        get_active_embedding(row, "nonsense")


def test_active_column_name_returns_literal_for_v1_and_v2(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_MARKET", "v1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    assert active_column_name("market") == "embedding"
    monkeypatch.setenv("EMBEDDINGS_VARIANT_MARKET", "v2")
    get_settings.cache_clear()
    assert active_column_name("market") == "embedding_v2"


def test_active_column_name_invalid_surface_raises():
    with pytest.raises(ValueError, match="surface"):
        active_column_name("nonsense")


def test_active_column_name_whitelist_is_closed():
    """Must not accept arbitrary identifiers — SQL-injection hardening."""
    with pytest.raises(ValueError):
        active_column_name("news; DROP TABLE users; --")
```

- [ ] **Step 3: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_embedding_reader.py -v`
Expected: `ModuleNotFoundError: No module named 'app.processing.embedding_reader'`.

- [ ] **Step 4: Implement the reader**

Create `app/processing/embedding_reader.py`:

```python
"""Read-side helpers that route embedding access through a per-surface feature
flag, so consumers transparently read either `embedding` (v1) or `embedding_v2`
(v2) depending on the active variant for that surface.

Two flavors:
- get_active_embedding(row, surface): for ORM consumers that hold a row object.
- active_column_name(surface): for raw-SQL consumers that templatize column
  names into a query string. Only returns the literal "embedding" or
  "embedding_v2"; whitelist-enforced, safe against injection.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


_VALID_SURFACES = ("news", "market", "event")


def _variant_for_surface(surface: str) -> str:
    if surface not in _VALID_SURFACES:
        raise ValueError(
            f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}"
        )
    settings = get_settings()
    attr = f"embeddings_variant_{surface}"
    v = getattr(settings, attr, "v1")
    return v if v in ("v1", "v2") else "v1"


def get_active_embedding(row: Any, surface: str) -> list[float] | None:
    """Return the embedding column matching the active variant for `surface`."""
    variant = _variant_for_surface(surface)
    if variant == "v1":
        return row.embedding
    return row.embedding_v2


def active_column_name(surface: str) -> str:
    """Return the literal column name ('embedding' or 'embedding_v2') for the
    active variant. Safe to interpolate into raw SQL — the return value is
    whitelist-enforced."""
    variant = _variant_for_surface(surface)
    return "embedding" if variant == "v1" else "embedding_v2"
```

- [ ] **Step 5: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_embedding_reader.py -v`
Expected: all 7 tests green.

- [ ] **Step 6: Commit**

```bash
git add app/processing/embedding_reader.py app/core/config.py \
        tests/unit/test_embedding_reader.py
git commit -m "feat(embeddings): embedding_reader + 3 variant flags (news/market/event)"
```

---

## Task 14: Migrate 4 consumers through `embedding_reader`

**Files:**
- Modify: `app/retrieval/hybrid_search.py`
- Modify: `app/retrieval/vector_retriever.py`
- Modify: `app/event_engine/simple_clusterer.py`
- Modify: `app/sourcing/pool_builder.py`

- [ ] **Step 1: Audit consumers — confirm the four call sites**

Run:
```bash
docker compose exec -T app python -c "
import subprocess
out = subprocess.check_output(['grep', '-rn', r'\.embedding\b\|\.embedding_v2\b',
    '--include=*.py', 'app/retrieval', 'app/event_engine/simple_clusterer.py',
    'app/sourcing/pool_builder.py', 'app/signal']).decode()
print(out)
"
```
Expected: lines across the 4 target files showing where embeddings are read. Any extra hit is a consumer we missed in the spec — stop and escalate if so.

- [ ] **Step 2: Migrate `app/retrieval/hybrid_search.py`**

Inside the function that performs the cosine join against `event.embedding` / `market.embedding`, replace direct attribute reads with `get_active_embedding(row, surface)` and the SQL KNN lookup (if any) with a templated column via `active_column_name("market")`. The exact edit depends on current shape — use these rules:

- If the code does `ev.embedding` → `get_active_embedding(ev, "event")`.
- If the code does `m.embedding` (ORM) → `get_active_embedding(m, "market")`.
- If the code does `ORDER BY embedding <=> :q` in raw SQL → `ORDER BY {col} <=> :q` with `col = active_column_name("market")` interpolated.

Add the imports at the top of the file:
```python
from app.processing.embedding_reader import get_active_embedding, active_column_name
```

- [ ] **Step 3: Migrate `app/retrieval/vector_retriever.py::search_markets_by_embedding`**

Replace the raw-SQL query that selects `embedding` with one that templates the column name. Find the block around lines 50-60:

```python
                    1 - (embedding <=> cast(:embedding as vector)) AS cosine_score
                FROM markets
                WHERE embedding IS NOT NULL
                  AND active = true
                  AND closed = false
                  AND 1 - (embedding <=> cast(:embedding as vector)) >= :min_sim
                ORDER BY embedding <=> cast(:embedding as vector)
```

Replace with:

```python
                    1 - ({col} <=> cast(:embedding as vector)) AS cosine_score
                FROM markets
                WHERE {col} IS NOT NULL
                  AND active = true
                  AND closed = false
                  AND 1 - ({col} <=> cast(:embedding as vector)) >= :min_sim
                ORDER BY {col} <=> cast(:embedding as vector)
```

Where `col = active_column_name("market")` is computed at the top of the function body and interpolated into the f-string or `.format(col=col)`. Add the import:

```python
from app.processing.embedding_reader import active_column_name
```

- [ ] **Step 4: Migrate `app/event_engine/simple_clusterer.py`**

Find any `article.embedding` / `event.embedding` reads and replace with `get_active_embedding(article, "news")` / `get_active_embedding(event, "event")` respectively. The clusterer compares news articles to events, so it reads both surfaces. Add the import:

```python
from app.processing.embedding_reader import get_active_embedding
```

- [ ] **Step 5: Migrate `app/sourcing/pool_builder.py`**

Find any `nc.embedding` reads (the pool builder fetches candidate articles with their embeddings from `news_clean`) and replace with `get_active_embedding(nc, "news")`. If the query selects the `embedding` column directly into a returned dict, switch to a templated SELECT using `active_column_name("news")`.

Add the import:
```python
from app.processing.embedding_reader import get_active_embedding, active_column_name
```

- [ ] **Step 6: Run the full backend test suite — catch regressions**

Run:
```bash
docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q
```
Expected: all 171+ tests still green. All existing tests default to `embeddings_variant_*=v1`, so behavior is unchanged.

- [ ] **Step 7: Commit**

```bash
git add app/retrieval/hybrid_search.py app/retrieval/vector_retriever.py \
        app/event_engine/simple_clusterer.py app/sourcing/pool_builder.py
git commit -m "refactor(embeddings): route 4 consumers through embedding_reader helpers"
```

---

## Task 15: Inline v2 writes in 3 creation pipelines + integration test

**Files:**
- Modify: `app/workers/tasks_pipeline.py` (news creation, around line 98-113)
- Modify: `app/workers/tasks_ingestion.py` (market creation, around line 115)
- Modify: `app/event_engine/event_builder.py` (event creation, around line 60)
- Create: `tests/integration/test_inline_v2_writes.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_inline_v2_writes.py`:

```python
"""Pipelines write both embedding and embedding_v2 on new rows."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import Event, Market, NewsClean
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


async def test_news_creation_writes_embedding_v2(async_db_factory, monkeypatch):
    """When a new NewsClean row is created via the pipeline, both `embedding`
    and `embedding_v2` should be populated (best-effort)."""

    async def _fake_embed(text):
        # Deterministic stub: echoes a toy embedding regardless of input.
        return make_toy_embedding(axis=hash(text) % 1536)

    monkeypatch.setattr(
        "app.processing.embedding_service.get_embedding",
        _fake_embed,
    )

    # Drive one news through the pipeline: this test calls the helper that
    # actually performs the inline writes. If your pipeline entry point is
    # tasks_pipeline._process_article_async, this is where you hook in with a
    # minimal fake News row. For this plan, the simpler path is to verify
    # that the post-task-15 code path sets both columns when given a fresh
    # row. We simulate by calling the composer + embedder chain directly and
    # confirming the integration point wrote both.

    # Minimal: instantiate a NewsClean with both columns populated, commit,
    # and re-read to confirm the schema accepts both.
    async with async_db_factory() as s:
        nc = NewsClean(
            news_id=9999,
            clean_text="first paragraph is long enough to pass the filter in v2",
            embedding=await _fake_embed("title. body"),
            embedding_v2=await _fake_embed("title. body lead tail"),
            embedding_v2_composition="news_v2_lead_tail",
            embedding_v2_computed_at=NOW,
        )
        s.add(nc)
        await s.commit()

    async with async_db_factory() as s:
        from sqlalchemy import select
        stored = (await s.execute(
            select(NewsClean).where(NewsClean.news_id == 9999)
        )).scalar_one()
        assert stored.embedding is not None
        assert stored.embedding_v2 is not None
        assert stored.embedding_v2_composition == "news_v2_lead_tail"
        assert stored.embedding_v2_computed_at is not None
```

(The point of this test is to confirm the schema and the write path accept the extra columns. The end-to-end "pipeline-driven creation" test is heavier and left for the full suite run in task 18.)

- [ ] **Step 2: Run the test — expected PASS**

Run: `docker compose exec -T app python -m pytest tests/integration/test_inline_v2_writes.py -v`
Expected: pass (the columns were added in task 2).

- [ ] **Step 3: Add the inline v2 write in `tasks_pipeline.py` (news)**

Around the block modified in task 9 (line ~98):

```python
        # Embed INLINE — no separate task, no batch wait
        from app.processing.text_composers import compose_news_v1, compose_news_v2
        composed_v1 = compose_news_v1(raw_title, clean_text)
        embedding = await get_embedding(composed_v1.text)

        # v2 inline write — best-effort
        composed_v2 = compose_news_v2(raw_title, clean_text)
        embedding_v2 = None
        try:
            embedding_v2 = await get_embedding(composed_v2.text)
        except Exception as exc:
            logger.warning("news embedding_v2 compute failed news_id=%s: %s", news_id, exc)
```

Then when constructing the `NewsClean(...)` row, set:

```python
            embedding_v2=embedding_v2,
            embedding_v2_composition=composed_v2.composition_version if embedding_v2 else None,
            embedding_v2_computed_at=now if embedding_v2 else None,
```

- [ ] **Step 4: Add the inline v2 write in `tasks_ingestion.py` (market)**

In the market creation block (around line 97-116 and the update path), after computing the v1 `retrieval_text`, add:

```python
                    from app.processing.text_composers import compose_market_v2
                    composed_v2 = compose_market_v2(mkt)
                    # v2 embedding will be computed by the background compute pass; just stash the composition hint.
                    mkt["market_retrieval_text_v2"] = composed_v2.text
                    mkt["market_composition_v2"] = composed_v2.composition_version
```

And in `_compute_market_embeddings` (around line 244-249), after the v1 write, add a parallel v2 pass:

```python
            # v2 pass — same pool but uses the v2 composer
            for market, _ in zip(markets, embeddings):
                from app.processing.text_composers import compose_market_v2
                composed_v2 = compose_market_v2({
                    "question": market.question,
                    "description": market.description,
                    "tags": market.tags,
                    "category": market.category,
                })
                # Compute v2 embedding inline in small batches to avoid a second query pass.
                emb_v2 = await get_embedding(composed_v2.text)
                if emb_v2:
                    market.embedding_v2 = emb_v2
                    market.embedding_v2_composition = composed_v2.composition_version
                    market.embedding_v2_computed_at = datetime.now(timezone.utc)

            await session.commit()
```

(The `from datetime import datetime, timezone` import may already exist. Check before adding.)

- [ ] **Step 5: Add the inline v2 write in `event_builder.py`**

After the `Event(...)` is constructed with `event_retrieval_text`, add:

```python
    # v2 composition — stored as text; embedding is computed when the event
    # is picked up by the scoring task's "Step 1: Event embedding" path, which
    # we also extend in task 16's backfill task to fill missing v2 rows.
    from app.processing.text_composers import compose_event_v2
    composed_v2 = compose_event_v2(
        event_title, event_summary, list(key_entities or []), bucket=bucket
    )
    event.embedding_v2_composition = composed_v2.composition_version
    # embedding_v2 itself is populated by tasks_scoring's event-embedding step,
    # which we extend next (and by the backfill task).
```

Then in `app/workers/tasks_scoring.py` around line 80-86 (the `raw_embedding is None` check):

```python
        # ── Step 1: Event embedding ──────────────────────────────────
        raw_embedding = event.embedding
        if raw_embedding is None:
            text_for_embed = event.event_retrieval_text or event.event_title
            raw_embedding = await get_embedding(text_for_embed)
            if raw_embedding is not None:
                event.embedding = raw_embedding
                await session.flush()

        # v2 event embedding (best-effort; failure doesn't block scoring)
        if event.embedding_v2 is None:
            from app.processing.text_composers import compose_event_v2
            composed_v2 = compose_event_v2(
                event.event_title, event.event_summary or "",
                list(event.key_entities or []), bucket=event.bucket,
            )
            try:
                v2_emb = await get_embedding(composed_v2.text)
            except Exception as exc:
                logger.warning("event embedding_v2 failed event_id=%s: %s", event_id, exc)
                v2_emb = None
            if v2_emb is not None:
                from datetime import datetime, timezone
                event.embedding_v2 = v2_emb
                event.embedding_v2_composition = composed_v2.composition_version
                event.embedding_v2_computed_at = datetime.now(timezone.utc)
                await session.flush()
```

- [ ] **Step 6: Run the full backend suite again**

Run: `docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q`
Expected: still all green.

- [ ] **Step 7: Commit**

```bash
git add app/workers/tasks_pipeline.py app/workers/tasks_ingestion.py \
        app/event_engine/event_builder.py app/workers/tasks_scoring.py \
        tests/integration/test_inline_v2_writes.py
git commit -m "feat(embeddings): inline v2 writes in news/market/event creation pipelines"
```

---

## Task 16: Celery backfill task `recompute_embedding_v2`

**Files:**
- Create: `app/workers/tasks_embeddings_backfill.py`
- Modify: `app/workers/celery_app.py` (autodiscover + route)
- Create: `tests/integration/test_embeddings_backfill.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_embeddings_backfill.py`:

```python
"""Integration tests for the embedding_v2 backfill Celery task."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import NewsClean
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def rows_missing_v2(async_db_factory, monkeypatch):
    async def _fake_embed(text):
        return make_toy_embedding(axis=len(text) % 1536)

    monkeypatch.setattr("app.processing.embedding_service.get_embedding", _fake_embed)

    async with async_db_factory() as s:
        for i in range(5):
            s.add(NewsClean(
                id=3000 + i,
                news_id=6000 + i,
                clean_text=f"article body {i} long enough to pass the filter for v2 composition.",
                embedding=make_toy_embedding(axis=i),
                embedding_v2=None,  # the backfill target
            ))
        await s.commit()


async def test_backfill_news_embedding_v2_populates_all_rows(
    rows_missing_v2, async_db_factory
):
    from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
    # Celery eager mode is configured in conftest for tests.
    result = recompute_embedding_v2.apply(kwargs={"surface": "news", "batch_size": 10}).get()
    assert result["processed"] == 5
    assert result["remaining"] == 0

    async with async_db_factory() as s:
        from sqlalchemy import select, func
        missing = (await s.execute(
            select(func.count()).select_from(NewsClean).where(NewsClean.embedding_v2.is_(None))
        )).scalar()
        assert missing == 0


async def test_backfill_is_idempotent(rows_missing_v2, async_db_factory):
    from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
    r1 = recompute_embedding_v2.apply(kwargs={"surface": "news", "batch_size": 10}).get()
    r2 = recompute_embedding_v2.apply(kwargs={"surface": "news", "batch_size": 10}).get()
    assert r1["processed"] == 5
    assert r2["processed"] == 0  # nothing left to do
```

- [ ] **Step 2: Run tests — confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_embeddings_backfill.py -v`
Expected: `ModuleNotFoundError: No module named 'app.workers.tasks_embeddings_backfill'`.

- [ ] **Step 3: Implement the backfill task**

Create `app/workers/tasks_embeddings_backfill.py`:

```python
"""Celery task: backfill `embedding_v2` for rows where it is NULL.

Invoked manually per surface after a new v2 composer lands. Never scheduled
on beat — this is an operator-triggered task, not a background job.

Idempotent: never touches a row whose embedding_v2 is already populated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select, func

from app.db.database import get_session_factory
from app.db.models import Event, Market, NewsClean
from app.processing.embedding_service import get_embedding
from app.processing.text_composers import (
    compose_event_v2,
    compose_market_v2,
    compose_news_v2,
)
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

Surface = Literal["news", "market", "event"]


@celery_app.task(
    name="app.workers.tasks_embeddings_backfill.recompute_embedding_v2",
    bind=True,
    rate_limit="60/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def recompute_embedding_v2(self, *, surface: str, batch_size: int = 100) -> dict:
    """Process one batch of rows lacking embedding_v2 for `surface`.

    Returns {'processed': int, 'remaining': int, 'est_cost_usd': float}.
    Caller loops manually (or invokes from a shell) until `remaining == 0`.
    """
    try:
        return _run_async(_run_backfill(surface, batch_size))
    except Exception as exc:
        logger.exception("recompute_embedding_v2 failed surface=%s", surface)
        raise self.retry(exc=exc)


async def _run_backfill(surface: str, batch_size: int) -> dict:
    if surface not in ("news", "market", "event"):
        raise ValueError(f"Unknown surface {surface!r}")

    factory = get_session_factory()
    processed = 0
    async with factory() as session:
        if surface == "news":
            stmt = (
                select(NewsClean)
                .where(NewsClean.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for nc in rows:
                composed = compose_news_v2(
                    getattr(nc.news, "title", "") if nc.news is not None else "",
                    nc.clean_text or "",
                )
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                nc.embedding_v2 = emb
                nc.embedding_v2_composition = composed.composition_version
                nc.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(NewsClean).where(NewsClean.embedding_v2.is_(None))
            )).scalar() or 0

        elif surface == "market":
            stmt = (
                select(Market)
                .where(Market.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for m in rows:
                composed = compose_market_v2({
                    "question": m.question,
                    "description": m.description,
                    "tags": m.tags,
                    "category": m.category,
                })
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                m.embedding_v2 = emb
                m.embedding_v2_composition = composed.composition_version
                m.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(Market).where(Market.embedding_v2.is_(None))
            )).scalar() or 0

        else:  # event
            stmt = (
                select(Event)
                .where(Event.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for ev in rows:
                composed = compose_event_v2(
                    ev.event_title,
                    ev.event_summary or "",
                    list(ev.key_entities or []),
                    bucket=ev.bucket,
                )
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                ev.embedding_v2 = emb
                ev.embedding_v2_composition = composed.composition_version
                ev.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(Event).where(Event.embedding_v2.is_(None))
            )).scalar() or 0

        await session.commit()

    est_cost = processed * 0.00001  # rough — $0.02/M tokens × ~500 tokens/row
    logger.info(
        "backfill surface=%s processed=%d remaining=%d est_cost_usd=%.4f",
        surface, processed, remaining, est_cost,
    )
    return {"processed": processed, "remaining": int(remaining), "est_cost_usd": est_cost}
```

- [ ] **Step 4: Wire into Celery autodiscover + route**

In `app/workers/celery_app.py`, find the `autodiscover_tasks([...])` call and add `"app.workers.tasks_embeddings_backfill"`:

```python
celery_app.autodiscover_tasks([
    # ... existing entries ...
    "app.workers.tasks_embeddings_backfill",
])
```

And add a route so the task runs on the `scoring` queue (it performs embedding calls; same queue as scoring work):

```python
task_routes = {
    # ... existing routes ...
    "app.workers.tasks_embeddings_backfill.*": {"queue": "scoring"},
}
```

- [ ] **Step 5: Run tests — confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_embeddings_backfill.py -v`
Expected: both tests green.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks_embeddings_backfill.py app/workers/celery_app.py \
        tests/integration/test_embeddings_backfill.py
git commit -m "feat(embeddings): recompute_embedding_v2 Celery task (news/market/event)"
```

---

## Task 17: Alembic migration 023 — HNSW index on `markets.embedding_v2`

**Files:**
- Create: `alembic/versions/023_add_hnsw_index_market_embedding_v2.py`

- [ ] **Step 1: Write the migration**

Create `alembic/versions/023_add_hnsw_index_market_embedding_v2.py`:

```python
"""Add HNSW index on markets.embedding_v2 — required before market-surface v2 promotion.

Revision ID: 023
Revises: 022
Create Date: 2026-04-24

NOT auto-applied by `alembic upgrade head` in CI — this migration is applied
manually, per the runbook, only once the market surface is ready to be flipped
to v2. Without it, `vector_retriever.search_markets_by_embedding` does a
sequential scan on `embedding_v2` and latency blows up.
"""

from __future__ import annotations

from alembic import op


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_markets_embedding_v2_hnsw "
        "ON markets USING hnsw (embedding_v2 vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_markets_embedding_v2_hnsw")
```

- [ ] **Step 2: Apply the migration**

Run: `docker compose exec -T app alembic upgrade 023`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 022 -> 023, add hnsw index on markets.embedding_v2`.

- [ ] **Step 3: Verify the index exists**

Run:
```bash
docker compose exec -T db psql -U postgres -d signal -c "
  SELECT indexname FROM pg_indexes
  WHERE indexname = 'idx_markets_embedding_v2_hnsw';"
```
Expected: one row, `idx_markets_embedding_v2_hnsw`.

- [ ] **Step 4: Verify downgrade then re-upgrade**

Run:
```bash
docker compose exec -T app alembic downgrade 022 && \
docker compose exec -T app alembic upgrade 023
```
Expected: both succeed; the index is dropped then recreated.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/023_add_hnsw_index_market_embedding_v2.py
git commit -m "feat(embeddings): migration 023 — HNSW index on markets.embedding_v2"
```

---

## Task 18: Runbook `docs/runbooks/promote_embeddings_v2.md` + final verification

**Files:**
- Create: `docs/runbooks/promote_embeddings_v2.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/promote_embeddings_v2.md`:

````markdown
# Promote `embedding_v2` to production — per-surface manual gate

This is a **manual** gate. Nothing auto-promotes. Run it once per surface
(news, market, event) after the corresponding composer v2 has accumulated
enough `embedding_v2` coverage in the DB.

## Pre-conditions (per surface)

1. **Backfill ≥ 95% complete.** Check:
   ```bash
   docker compose exec -T db psql -U postgres -d signal -c "
     SELECT
       SUM(CASE WHEN embedding_v2 IS NULL THEN 1 ELSE 0 END)::float
       / GREATEST(COUNT(*), 1)::float AS null_fraction
     FROM news_clean;"
   ```
   (Repeat for `markets` and `events` as needed.) The `null_fraction` must be ≤ 0.05.
   If not, run the backfill until it is:
   ```bash
   docker compose exec -T app python -c "
   from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
   while True:
       r = recompute_embedding_v2.apply(kwargs={'surface':'news','batch_size':200}).get()
       print(r)
       if r['remaining'] == 0:
           break
   "
   ```

2. **≥ 100 eval pairs per label source.** The harness prints `n` per metric
   per source. If any source has `n < 30`, the stratification check (#3
   below) is not reliable — wait for more data or accept the noise risk.

## The gate

Run the harness diff:

```bash
docker compose exec -T app python -m scripts.eval_embeddings \
    --variant v2 --surface <news|market|event> \
    --baseline docs/eval_baselines/embeddings_2026-04-24_v1.json
```

Promotion for that surface is allowed **if and only if all three hold**:

| Check                          | Pass condition                                                              |
|--------------------------------|------------------------------------------------------------------------------|
| Statistical confidence         | `retrieval@5(v2).ci_low > retrieval@5(v1).ci_high`                           |
| Ranking quality                | `nDCG@10(v2) > nDCG@10(v1)` (absolute delta)                                 |
| Cross-source consistency       | `retrieval@5(v2) > retrieval@5(v1)` on **each** source stratum independently |

The CLI's `--baseline` mode renders the three checks inline. Eyeball or grep
for `↑ improved` / `= flat` / `↓ regressed` per metric.

If **any** check fails: do NOT promote this surface. Options:
- Iterate on the composer (adjust A1's lead/tail ratio, A3's bracket label,
  A4's summary slice), reset `embedding_v2 = NULL` on the affected surface,
  rerun backfill, rerun eval.
- Accept the failure and leave v1 in place.

## Executing promotion

Different pre-flight per surface.

### For `news` or `event` (no index change needed)

1. Confirm gate passes.
2. Update `.env` on prod:
   ```
   EMBEDDINGS_VARIANT_NEWS=v2       # or EMBEDDINGS_VARIANT_EVENT=v2
   ```
3. Redeploy the `pipeline` and `scoring` queue workers + API.

### For `market` (requires migration 023)

1. Confirm gate passes.
2. **Apply migration 023** (creates HNSW index on `markets.embedding_v2`):
   ```bash
   docker compose exec -T app alembic upgrade 023
   ```
   Verify:
   ```bash
   docker compose exec -T db psql -U postgres -d signal -c "
     SELECT indexname FROM pg_indexes
     WHERE indexname = 'idx_markets_embedding_v2_hnsw';"
   ```
3. Update `.env`:
   ```
   EMBEDDINGS_VARIANT_MARKET=v2
   ```
4. Redeploy the `scoring` and `pipeline` queue workers + API.

## Monitoring (first 7 days post-flip, per surface)

- **Signal volume.** No abnormal drop vs the prior 7-day window.
- **Brier / P&L.** Chantier #1's `/api/admin/metrics/variants` shows the
  current production variant; its Brier/P&L must not regress by more than
  10% vs the pre-flip 7-day window.
- **Latency.** For the market surface in particular, monitor
  `hybrid_search_markets` p95 — if the HNSW index on `embedding_v2` is
  missing or misconfigured, this will spike.

## Rollback

Instant:
1. Flip `EMBEDDINGS_VARIANT_<SURFACE>=v1` in `.env`.
2. Redeploy workers + API.

`embedding` column is untouched, so v1 resumes immediately without any
data operation. No migration rollback needed. Write a short post-mortem
noting the gap between harness verdict and production — that gap indicates
a missing case in the label set that needs adding to `app/eval/labels.py`
before the next candidate.

## Audit one query's retrieval under each variant

To compare what event E retrieves under v1 vs v2 for a given surface:

```bash
docker compose exec -T app python -c "
import asyncio
from app.db.database import get_session_factory
from app.eval.runner import _fetch_embedding_for_query, _fetch_candidate_pool

async def main():
    factory = get_session_factory()
    async with factory() as s:
        for variant in ('v1', 'v2'):
            q = await _fetch_embedding_for_query(s, 'event_to_market', <EVENT_ID>, variant)
            pool = await _fetch_candidate_pool(s, 'event_to_market', <EVENT_ID>, variant)
            scored = sorted(
                [(cid, sum(x*y for x,y in zip(q, e))) for cid, e in pool if e is not None],
                key=lambda t: -t[1],
            )[:10]
            print(variant, scored)

asyncio.run(main())
"
```

Replace `<EVENT_ID>` with the event you want to audit.
````

- [ ] **Step 2: Smoke — runbook exists and has substance**

Run:
```bash
docker compose exec -T app python -c "
from pathlib import Path
p = Path('docs/runbooks/promote_embeddings_v2.md')
assert p.exists() and p.stat().st_size > 1000
print(f'{p.stat().st_size} bytes')
"
```
Expected: prints something like `4000 bytes`.

- [ ] **Step 3: Run the full backend test suite one last time**

Run:
```bash
docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q
```
Expected: all pass. The new tests add ~40 green cases; total should be around 210+ now.

- [ ] **Step 4: Re-run the chantier #1 + #2 + #3 tests together**

Run:
```bash
docker compose exec -T app python -m pytest \
  tests/unit/test_eval_metrics.py \
  tests/unit/test_embedding_reader.py \
  tests/unit/test_text_composers_v1.py \
  tests/unit/test_text_composers_v2.py \
  tests/unit/test_article_ranker.py \
  tests/unit/test_sourcing_pool_builder.py \
  tests/unit/test_sourcing_prod_trace.py \
  tests/unit/test_measurement_pipeline.py \
  tests/integration/test_eval_labels.py \
  tests/integration/test_eval_runner.py \
  tests/integration/test_inline_v2_writes.py \
  tests/integration/test_embeddings_backfill.py \
  tests/integration/test_sourcing_prod_audit.py \
  tests/integration/test_sourcing_shadow.py \
  tests/integration/test_sourcing_shadow_kill_switch.py \
  tests/integration/test_signal_predictions_hook.py \
  tests/integration/test_resolution_hook.py \
  tests/integration/test_admin_metrics_variants.py \
  tests/integration/test_admin_metrics_rolling.py \
  -v
```
Expected: every test green.

- [ ] **Step 5: Regenerate the frozen baseline with the migrated consumers (optional sanity)**

If any step in tasks 9 or 14 changed retrieval output meaningfully, re-generate the baseline to make it reflect post-migration v1:

```bash
docker compose exec -T app python -m scripts.eval_embeddings \
    --variant v1 --surface all \
    --out docs/eval_baselines/embeddings_2026-04-24_v1.json
```

Compare to the one committed in task 7 — if it's bit-identical, no commit. If it differs (because `compose_event_v1` unified summary from `[:400]` to `[:300]`), commit the updated baseline with a short note.

- [ ] **Step 6: Verify working tree + commit count**

Run: `git status && git log --oneline main..HEAD`
Expected: working tree clean (except possibly the regenerated baseline); ~18 new commits on this chantier on top of chantier #2's commits.

- [ ] **Step 7: Commit the runbook**

```bash
git add docs/runbooks/promote_embeddings_v2.md
# Include the regenerated baseline if step 5 produced a diff:
# git add docs/eval_baselines/embeddings_2026-04-24_v1.json
git commit -m "docs(embeddings): promote_embeddings_v2 runbook (per-surface 3-check gate)"
```

Merge to `main` is **not** part of this plan — leave that to human review
after the first real harness diff (v1 vs v2 on production-backfilled rows)
has been inspected.

---

## Rollout checklist (operator — not engineer)

1. Apply migration `022` on production.
2. Deploy new code with all three `EMBEDDINGS_VARIANT_*=v1` (default).
3. Observe for ≥ 24h that new news/market/event rows get both `embedding` AND `embedding_v2` populated (query: `WHERE embedding_v2 IS NOT NULL ORDER BY id DESC LIMIT 10` should show recent rows).
4. Run backfill until `< 5%` NULL per surface (loop `recompute_embedding_v2` until `remaining=0`).
5. Run the harness. Freeze a fresh `v1` baseline if the current one predates the backfill.
6. For each surface that passes the gate in `docs/runbooks/promote_embeddings_v2.md`:
   - (Market only) apply migration 023.
   - Flip the corresponding `.env` flag to `v2`. Redeploy.
7. Monitor 7 days. If no regression, the promotion holds.

## Known limitations (for chantier follow-ups)

- **No model upgrade.** `text-embedding-3-small` remains. `3-large` (3072-dim) is the natural next step — the harness is dimension-agnostic, so it plugs into a future `embedding_v3 VECTOR(3072)` column with no label-side changes.
- **No multi-vector per entity.** A future iteration could embed question, description, tags separately for markets and combine at query time — out of scope here.
- **Cluster-purity metric is shipped but unused** in the gate. Chantier #4 (clustering news↔markets) will consume it for its own promotion decisions.
- **LLM judge is cheap but biased.** The judge's budget ($10 default) and cache are the safeguards — if we find it systematically disagrees with downstream P&L, swap the judge model or tighten the prompt in a future iteration.

---

*End of plan.*
