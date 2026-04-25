# Signal Sourcing & Traceability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-rank the articles fed to each signal's reasoning step (from "top-5 by recency" to "top-5 by `α·cosine + β·recency` against the specific market embedding"), ship it behind a **shadow variant** (`signal_v2_reranked`) so chantier #1's metrics measure the impact, and write every signal × variant's article set into a new `signal_articles` table for audit.

**Architecture:** One new table `signal_articles (signal_id, variant, news_clean_id) PK`. The production path writes an audit row per article it already used (variant=`"signal"`). The shadow path fires a Celery task per signal that re-ranks the 72h article pool with a pure `ArticleRanker`, re-calls `reasoning_analyzer` with the re-ranked top-5, and writes one `SignalPrediction(variant="signal_v2_reranked")` + 5 `SignalArticle` rows. Kill-switch (`SOURCING_SHADOW_ENABLED`), rate-limit (`30/m`), 3 retries. Chantier #1's admin endpoint (`/api/admin/metrics/variants`) surfaces the new variant without any endpoint change.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async (`Mapped`/`mapped_column`), Alembic (revision `021`, `down_revision="020"`), pgvector 1536-dim, Celery + Redis, `_run_async` helper for async-in-Celery, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-04-24-signal-sourcing-design.md`. Read it once before starting — the scoring formula, the schema, and the task's retry policy all come from there.

**Depends on (already shipped in chantier #1):**
- `SignalPrediction` model + `uq_signal_predictions_signal_variant`
- `app/measurement/pipeline.py::schedule_shadow_variants` (stub we replace)
- `app/measurement/variant_registry.py::get_registry` (unchanged — shadow doesn't register in the registry; it runs via its own Celery task)
- `/api/admin/metrics/variants` endpoint
- `app/workers/_async_helpers.run_async`

**Branch target:** `sourcing/traceability` off the chantier-#1 branch (create a worktree before Task 1).

---

## File structure (created / modified)

**New files:**
- `alembic/versions/021_signal_articles.py` — migration
- `app/sourcing/__init__.py` — package, re-exports `ArticleRanker` + `RankedArticle`
- `app/sourcing/article_ranker.py` — pure `ArticleRanker` class + `RankedArticle` dataclass
- `app/sourcing/pool_builder.py` — `fetch_candidate_articles(session, event_id, t0, window_hours)`
- `app/sourcing/prod_trace.py` — `record_prod_signal_articles(session, signal_id, articles)`
- `app/workers/tasks_sourcing.py` — `@celery_app.task sourcing_shadow_rerun`
- `docs/runbooks/promote_signal_v2.md` — promotion gate runbook
- `tests/unit/test_article_ranker.py`
- `tests/unit/test_sourcing_pool_builder.py`
- `tests/unit/test_sourcing_prod_trace.py`
- `tests/integration/test_sourcing_prod_audit.py`
- `tests/integration/test_sourcing_shadow.py`
- `tests/integration/test_sourcing_shadow_kill_switch.py`

**Modified files:**
- `app/db/models.py` — add `SignalArticle` ORM class
- `app/signal/signal_builder.py::_persist_signal` — call `record_prod_signal_articles(...)` after `record_baselines`
- `app/measurement/pipeline.py::schedule_shadow_variants` — body becomes `sourcing_shadow_rerun.delay(signal_id)` wrapped in try/except
- `app/core/config.py` — 6 new settings (`SOURCING_ALPHA`, `_BETA`, `_RECENCY_TAU_HOURS`, `_POOL_WINDOW_HOURS`, `_TOP_K`, `_SHADOW_ENABLED`)
- `app/workers/celery_app.py` — add `app.workers.tasks_sourcing` to `autodiscover_tasks([...])`

---

## Task 1: Alembic migration — `signal_articles` table

**Files:**
- Create: `alembic/versions/021_signal_articles.py`

- [ ] **Step 1: Write the migration**

```python
"""signal_articles: per-(signal × variant) article audit trail.

Revision ID: 021
Revises: 020
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_articles",
        sa.Column(
            "signal_id",
            sa.BigInteger,
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.String(64), nullable=False),
        sa.Column(
            "news_clean_id",
            sa.BigInteger,
            sa.ForeignKey("news_clean.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.SmallInteger, nullable=False),
        sa.Column("score", sa.Numeric(6, 4), nullable=False),
        sa.Column("cosine_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("recency_weight", sa.Numeric(6, 4), nullable=False),
        sa.Column("excerpt", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint(
            "signal_id", "variant", "news_clean_id",
            name="pk_signal_articles",
        ),
    )
    op.create_index(
        "idx_sa_signal_variant",
        "signal_articles",
        ["signal_id", "variant"],
    )
    op.create_index(
        "idx_sa_news_clean",
        "signal_articles",
        ["news_clean_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_sa_news_clean", table_name="signal_articles")
    op.drop_index("idx_sa_signal_variant", table_name="signal_articles")
    op.drop_table("signal_articles")
```

- [ ] **Step 2: Apply the migration**

Run: `docker compose exec -T app alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 020 -> 021, signal_articles`.

- [ ] **Step 3: Verify schema**

Run: `docker compose exec -T db psql -U postgres -d signal -c "\d signal_articles"`
Expected: columns listed; composite PK `(signal_id, variant, news_clean_id)`; two indexes present; two FKs (`signals.id`, `news_clean.id`) both `ON DELETE CASCADE`.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/021_signal_articles.py
git commit -m "feat(sourcing): migration 021 — signal_articles audit table"
```

---

## Task 2: `SignalArticle` SQLAlchemy model + `app/sourcing/` package

**Files:**
- Modify: `app/db/models.py` (append after `SignalPrediction`)
- Create: `app/sourcing/__init__.py`

- [ ] **Step 1: Add the `SignalArticle` ORM class**

Append this to `app/db/models.py`, directly after the `SignalPrediction` class:

```python
# ---------------------------------------------------------------------------
# signal_articles  (audit trail — which articles every variant saw)
# ---------------------------------------------------------------------------
class SignalArticle(Base):
    __tablename__ = "signal_articles"

    signal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("signals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    variant: Mapped[str] = mapped_column(String(64), primary_key=True)
    news_clean_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("news_clean.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    cosine_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    recency_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Verify `BigInteger`, `SmallInteger`, `Numeric`, `Text`, `ForeignKey`, `Optional`, and `String` are already imported in the file — they all are as of chantier #1. If a check fails, add the missing import.

- [ ] **Step 2: Create the `app/sourcing/` package (empty body; re-exports land in Task 5)**

Create `app/sourcing/__init__.py`:

```python
"""Sourcing layer — article ranker, candidate-pool builder, and audit writer.

Re-exports live in this module so callers do ``from app.sourcing import
ArticleRanker`` without reaching into the submodules. The Celery worker
(`app/workers/tasks_sourcing.py`) is intentionally NOT imported here — importing
it would pull in Celery at API-server startup, which we don't want.
"""

from app.sourcing.article_ranker import ArticleRanker, RankedArticle

__all__ = ["ArticleRanker", "RankedArticle"]
```

(Even though `article_ranker.py` doesn't exist yet, this import will break until Task 5. That's intentional — we ship the package skeleton here and let the import land once the ranker is written. If you're running tests before Task 5, just create the file empty until then.)

Actually, safer: ship Task 2's `__init__.py` empty and move the re-exports to Task 5 when `article_ranker.py` exists. Use:

```python
"""Sourcing layer — article ranker, candidate-pool builder, audit writer.

Re-exports are added in Task 5 once ArticleRanker is implemented.
"""
```

- [ ] **Step 3: Smoke**

Run: `docker compose exec -T app python -c "from app.db.models import SignalArticle; print(SignalArticle.__tablename__)"`
Expected: `signal_articles`

Run: `docker compose exec -T app python -c "import app.sourcing; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/db/models.py app/sourcing/__init__.py
git commit -m "feat(sourcing): SignalArticle ORM + sourcing package skeleton"
```

---

## Task 3: Config settings — 6 new `SOURCING_*` knobs

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Add the settings**

In `app/core/config.py`, add a new `# ── Sourcing ──` block near the end of the `Settings` class (grouping with other feature-flag-style settings):

```python
    # ── Sourcing (chantier #2) ────────────────────────────────────────
    sourcing_alpha: float = Field(
        default=0.7,
        description="Weight of cosine similarity in the composite article score.",
    )
    sourcing_beta: float = Field(
        default=0.3,
        description="Weight of recency decay in the composite article score.",
    )
    sourcing_recency_tau_hours: float = Field(
        default=24.0,
        description="Exponential-decay time constant (hours) for article recency.",
    )
    sourcing_pool_window_hours: int = Field(
        default=72,
        description="Hard cutoff for the candidate article pool, in hours.",
    )
    sourcing_top_k: int = Field(
        default=5,
        description="Number of articles re-ranked and fed to the shadow reasoning call.",
    )
    sourcing_shadow_enabled: bool = Field(
        default=True,
        description="Kill switch for the signal_v2_reranked Celery task.",
    )
```

- [ ] **Step 2: Smoke — the settings load and reflect env overrides**

Run:
```bash
docker compose exec -T app python -c "
from app.core.config import get_settings
get_settings.cache_clear()
s = get_settings()
print(s.sourcing_alpha, s.sourcing_beta, s.sourcing_recency_tau_hours,
      s.sourcing_pool_window_hours, s.sourcing_top_k, s.sourcing_shadow_enabled)
"
```
Expected: `0.7 0.3 24.0 72 5 True`.

Then verify an override is picked up:
```bash
docker compose exec -T -e SOURCING_SHADOW_ENABLED=false app python -c "
from app.core.config import get_settings
get_settings.cache_clear()
print(get_settings().sourcing_shadow_enabled)
"
```
Expected: `False`.

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(sourcing): 6 SOURCING_* settings (alpha/beta/tau/window/top_k/shadow_enabled)"
```

---

## Task 4: `RankedArticle` dataclass

**Files:**
- Create: `app/sourcing/article_ranker.py` (just the dataclass for now; the ranker class is Task 5)

- [ ] **Step 1: Write `RankedArticle`**

Create `app/sourcing/article_ranker.py`:

```python
"""Pure article ranker — composite score of cosine similarity + recency decay.

Zero I/O: takes candidates + market embedding + t0, returns a ranked list.
Fully unit-testable. Task 4 ships just the `RankedArticle` dataclass; the
ranker class lands in Task 5.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedArticle:
    """Result of ranking one candidate.

    Immutable so Celery can serialize batches safely. `excerpt` is None at
    ranking time — it's filled later if the LLM returns an excerpt matching
    this news_clean_id. Kept on this dataclass so the persistence layer has
    one value object to write.
    """
    news_clean_id: int
    rank: int               # 1-based; 1 = top
    score: float            # composite in [0, 1]
    cosine: float           # raw cosine, clipped to [0, 1]
    recency_weight: float   # exp decay, [0, 1]
    excerpt: str | None = None
```

- [ ] **Step 2: Smoke**

Run: `docker compose exec -T app python -c "from app.sourcing.article_ranker import RankedArticle; r = RankedArticle(news_clean_id=1, rank=1, score=0.9, cosine=0.8, recency_weight=0.9); print(r)"`
Expected: prints the dataclass repr, no error.

- [ ] **Step 3: Commit**

```bash
git add app/sourcing/article_ranker.py
git commit -m "feat(sourcing): RankedArticle dataclass"
```

---

## Task 5: `ArticleRanker` class (pure) + unit tests

**Files:**
- Modify: `app/sourcing/article_ranker.py`
- Modify: `app/sourcing/__init__.py` (add re-exports now that `ArticleRanker` exists)
- Create: `tests/unit/test_article_ranker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_article_ranker.py`:

```python
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
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_article_ranker.py -v`
Expected: `ImportError: cannot import name 'ArticleRanker'`.

- [ ] **Step 3: Implement the ranker**

Replace `app/sourcing/article_ranker.py` with:

```python
"""Pure article ranker — composite score of cosine similarity + recency decay.

No I/O: takes candidates + market embedding + t0, returns a ranked list.
Deterministic tie-break: newer publish_date wins, then lower news_clean_id.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class RankedArticle:
    news_clean_id: int
    rank: int
    score: float
    cosine: float
    recency_weight: float
    excerpt: str | None = None


def _cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Cosine similarity, clipped to [0, 1].

    Embeddings are *assumed* normalized (pgvector stores them this way after
    the ingestion pipeline). We still normalize defensively — cheaper than
    crashing on a stray un-normalized vector.
    """
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, dot / (na * nb))


def _recency_weight(t0: datetime, publish_date: datetime, tau_hours: float) -> float:
    delta_hours = max(0.0, (t0 - publish_date).total_seconds() / 3600.0)
    return math.exp(-delta_hours / tau_hours)


class ArticleRanker:
    """Composite ranker: score = clip(α·cosine + β·recency_w, 0, 1)."""

    def __init__(self, *, alpha: float, beta: float, tau_hours: float) -> None:
        if tau_hours <= 0:
            raise ValueError("tau_hours must be > 0")
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.tau_hours = float(tau_hours)

    @classmethod
    def from_settings(cls, settings) -> "ArticleRanker":
        return cls(
            alpha=settings.sourcing_alpha,
            beta=settings.sourcing_beta,
            tau_hours=settings.sourcing_recency_tau_hours,
        )

    def rank(
        self,
        pool: Iterable[dict[str, Any]],
        market_embedding: list[float] | None,
        t0: datetime,
        *,
        top_k: int,
    ) -> list[RankedArticle]:
        """Return up to `top_k` articles ranked by composite score.

        Articles without an embedding are dropped. If `market_embedding` is
        None, falls back to pure recency (cosine = 0 for every candidate).
        """
        scored: list[tuple[float, datetime, int, float, float, dict]] = []
        for art in pool:
            emb = art.get("embedding")
            if emb is None:
                continue
            cos = _cosine(emb, market_embedding) if market_embedding is not None else 0.0
            pd = art.get("publish_date")
            if pd is None:
                # Missing publish_date: treat as infinitely old.
                rw = 0.0
            else:
                rw = _recency_weight(t0, pd, self.tau_hours)
            raw = self.alpha * cos + self.beta * rw
            score = max(0.0, min(1.0, raw))
            scored.append((score, pd or datetime.min, int(art["news_clean_id"]), cos, rw, art))

        # Sort: score DESC, publish_date DESC (newer wins tie), news_clean_id ASC (deterministic).
        scored.sort(key=lambda t: (-t[0], -(t[1].timestamp() if t[1] != datetime.min else 0.0), t[2]))

        out: list[RankedArticle] = []
        for rank, (score, _pd, ncid, cos, rw, _art) in enumerate(scored[:top_k], start=1):
            out.append(RankedArticle(
                news_clean_id=ncid,
                rank=rank,
                score=score,
                cosine=cos,
                recency_weight=rw,
                excerpt=None,
            ))
        return out
```

- [ ] **Step 4: Re-export in `app/sourcing/__init__.py`**

Replace the file content with:

```python
"""Sourcing layer — article ranker, candidate-pool builder, audit writer."""

from app.sourcing.article_ranker import ArticleRanker, RankedArticle

__all__ = ["ArticleRanker", "RankedArticle"]
```

- [ ] **Step 5: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_article_ranker.py -v`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add app/sourcing/article_ranker.py app/sourcing/__init__.py tests/unit/test_article_ranker.py
git commit -m "feat(sourcing): ArticleRanker (cosine+recency composite, deterministic tie-break)"
```

---

## Task 6: `pool_builder.fetch_candidate_articles` + integration tests

**Files:**
- Create: `app/sourcing/pool_builder.py`
- Create: `tests/unit/test_sourcing_pool_builder.py`

**Context:** `news_clean.embedding` is 1536-dim pgvector, `news_clean.publish_date` does NOT exist — publish_date lives on the `news` table (joined via `news.id = news_clean.news_id`). Same for `source_name`, `source_tier`, `source_weight`. The query must JOIN `news_clean → news` and filter out NULL embeddings.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_sourcing_pool_builder.py`:

```python
"""Integration-ish unit tests for pool_builder — uses async_db_factory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models import Event, EventNewsLink, News, NewsClean
from app.sourcing.pool_builder import fetch_candidate_articles


T0 = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


async def _seed_article(
    session,
    *,
    clean_id: int,
    news_id: int,
    event_id: int,
    age_hours: float,
    embedding: list[float] | None,
):
    session.add(News(
        id=news_id,
        url=f"https://x/{news_id}",
        title=f"t-{news_id}",
        text="body",
        source_name="src",
        source_tier=1,
        source_weight=0.5,
        publish_date=T0 - timedelta(hours=age_hours),
    ))
    session.add(NewsClean(
        id=clean_id,
        news_id=news_id,
        clean_text=f"clean-{clean_id}",
        embedding=embedding,
    ))
    await session.flush()
    session.add(EventNewsLink(event_id=event_id, clean_id=clean_id))


@pytest.fixture
async def _clean_up(async_db_factory):
    """Wipe seed rows before and after each test."""
    async def _wipe():
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 601))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([1001, 1002, 1003, 1004])))
            await s.execute(delete(News).where(News.id.in_([9001, 9002, 9003, 9004])))
            await s.execute(delete(Event).where(Event.id == 601))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_pool_builder_respects_window_cutoff(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        # 3 articles: 1h, 24h, 100h old. Window=72h should include first two.
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1002, news_id=9002, event_id=601,
                            age_hours=24, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1003, news_id=9003, event_id=601,
                            age_hours=100, embedding=[0.1] * 1536)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    ids = {p["news_clean_id"] for p in pool}
    assert ids == {1001, 1002}


@pytest.mark.asyncio
async def test_pool_builder_only_articles_linked_to_event(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        # Linked: 1001. Unlinked: 1002 (no EventNewsLink row for event 601).
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        # Unlinked article: same insert but without the link
        s.add(News(id=9002, url="https://x/2", title="t", text="b",
                   source_name="src", source_tier=1, source_weight=0.5,
                   publish_date=T0 - timedelta(hours=1)))
        s.add(NewsClean(id=1002, news_id=9002, clean_text="clean", embedding=[0.1] * 1536))
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert {p["news_clean_id"] for p in pool} == {1001}


@pytest.mark.asyncio
async def test_pool_builder_excludes_null_embeddings(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1002, news_id=9002, event_id=601,
                            age_hours=1, embedding=None)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert {p["news_clean_id"] for p in pool} == {1001}


@pytest.mark.asyncio
async def test_pool_builder_returns_required_fields(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=3, embedding=[0.5] * 1536)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert len(pool) == 1
    item = pool[0]
    for k in ("news_clean_id", "embedding", "publish_date", "clean_text",
             "source_name", "source_tier", "source_weight"):
        assert k in item, f"missing key {k!r}"
    assert item["publish_date"] is not None
    assert item["source_tier"] == 1
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_sourcing_pool_builder.py -v`
Expected: `ImportError: no module named 'app.sourcing.pool_builder'`.

- [ ] **Step 3: Implement the pool builder**

Create `app/sourcing/pool_builder.py`:

```python
"""Candidate-article pool for per-signal re-ranking.

Returns all articles linked to an event, published within `[t0 - window, t0]`,
with a non-NULL embedding. The ranker is the consumer; it re-sorts by score.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventNewsLink, News, NewsClean


async def fetch_candidate_articles(
    session: AsyncSession,
    *,
    event_id: int,
    t0: datetime,
    window_hours: int = 72,
) -> list[dict[str, Any]]:
    """Fetch the candidate pool for `(event_id, t0)`.

    Filters:
      - linked to `event_id` via `event_news_links`
      - `news.publish_date` within `[t0 - window_hours, t0]`
      - `news_clean.embedding IS NOT NULL`

    Returns a list of dicts with the fields the ranker expects.
    """
    cutoff_lo = t0 - timedelta(hours=window_hours)

    stmt = (
        select(
            NewsClean.id.label("news_clean_id"),
            NewsClean.embedding,
            News.publish_date,
            NewsClean.clean_text,
            News.source_name,
            News.source_tier,
            News.source_weight,
        )
        .join(News, News.id == NewsClean.news_id)
        .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
        .where(
            EventNewsLink.event_id == event_id,
            News.publish_date.is_not(None),
            News.publish_date >= cutoff_lo,
            News.publish_date <= t0,
            NewsClean.embedding.is_not(None),
        )
        .order_by(News.publish_date.desc())
    )

    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.all()]
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_sourcing_pool_builder.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/sourcing/pool_builder.py tests/unit/test_sourcing_pool_builder.py
git commit -m "feat(sourcing): pool_builder.fetch_candidate_articles (event + 72h window + embedding filter)"
```

---

## Task 7: `prod_trace.record_prod_signal_articles` + unit tests

**Files:**
- Create: `app/sourcing/prod_trace.py`
- Create: `tests/unit/test_sourcing_prod_trace.py`

**Context:** The production signal builder already holds an `articles` list and a `llm["article_excerpts"]` dict. `record_prod_signal_articles` writes one `SignalArticle(variant="signal")` row per article in the order the builder passed them in. Since prod doesn't compute a composite score, the `score` column mirrors a trivial value and `cosine_score` / `recency_weight` are filled from cheap computations for homogeneity (see `score=0.0` fallback below — we only need the row to exist for audit; real scoring is shadow-only).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_sourcing_prod_trace.py`:

```python
"""Unit tests for prod_trace — writes the 'signal' variant audit rows."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import (
    Event,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalArticle,
)
from app.sourcing.prod_trace import record_prod_signal_articles


async def _seed_signal_with_articles(session, *, event_id: int, sig_id: int | None = None):
    session.add(Market(market_id="0xpt", question="q", active=True))
    session.add(Event(id=event_id, event_title="e"))
    await session.flush()
    sig = Signal(
        event_id=event_id, market_id="0xpt", signal_score=80,
        direction="BUY_YES", market_price_at_signal=0.6,
    )
    session.add(sig)
    await session.flush()
    # Two news/news_clean rows for audit
    for (nid, cid) in [(7001, 5001), (7002, 5002)]:
        session.add(News(id=nid, url=f"https://x/{nid}", title="t",
                         text="b", source_name="s", source_tier=1,
                         source_weight=0.5))
        session.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}"))
        session.add(EventNewsLink(event_id=event_id, clean_id=cid))
    await session.flush()
    return sig.id


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            await s.execute(delete(SignalArticle).where(SignalArticle.news_clean_id.in_([5001, 5002])))
            await s.execute(delete(Signal).where(Signal.event_id == 701))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 701))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([5001, 5002])))
            await s.execute(delete(News).where(News.id.in_([7001, 7002])))
            await s.execute(delete(Event).where(Event.id == 701))
            await s.execute(delete(Market).where(Market.market_id == "0xpt"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_record_prod_writes_one_row_per_article(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [
            {"news_clean_id": 5001, "excerpt": None},
            {"news_clean_id": 5002, "excerpt": "quoted phrase"},
        ]
        n = await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        assert n == 2

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalArticle).where(SignalArticle.signal_id == sid)
            )
        ).scalars().all()
    assert len(rows) == 2
    assert {r.variant for r in rows} == {"signal"}
    assert {r.news_clean_id for r in rows} == {5001, 5002}
    # Ranks are 1-based and contiguous
    assert sorted(r.rank for r in rows) == [1, 2]
    # Excerpt preserved when present
    excerpts = {r.news_clean_id: r.excerpt for r in rows}
    assert excerpts[5002] == "quoted phrase"


@pytest.mark.asyncio
async def test_record_prod_is_idempotent(async_db_factory, _clean_up):
    """Second call with same args is a no-op — PK conflict resolved silently."""
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [{"news_clean_id": 5001, "excerpt": None}]
        await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        # second call
        await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalArticle).where(SignalArticle.signal_id == sid)
            )
        ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_record_prod_skips_articles_without_news_clean_id(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [
            {"news_clean_id": 5001, "excerpt": None},
            {"excerpt": "orphan"},  # missing news_clean_id → must be skipped
        ]
        n = await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        assert n == 1
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_sourcing_prod_trace.py -v`
Expected: ImportError on `app.sourcing.prod_trace`.

- [ ] **Step 3: Implement `prod_trace.py`**

Create `app/sourcing/prod_trace.py`:

```python
"""Audit writer for the production variant.

Production does NOT re-rank: it uses the articles the signal builder already
picked. We still need a row in `signal_articles` so "which 5 articles
generated this signal?" becomes one SQL query and so the shadow variant has a
prod comparison to join against.

No composite scoring happens here — `score`, `cosine_score`, `recency_weight`
are filled with 0.0 placeholders. If a future chantier wants to compare
rankings, it can re-score prod rows from the shadow side.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SignalArticle


async def record_prod_signal_articles(
    session: AsyncSession,
    *,
    signal_id: int,
    articles: list[dict[str, Any]],
) -> int:
    """Insert one SignalArticle row per article with variant='signal'.

    Rank is the 1-based index in the input list. Idempotent via ON CONFLICT
    DO NOTHING on the composite PK.

    Returns the count of rows actually inserted (0 when called a second time
    with identical args).
    """
    rows: list[dict[str, Any]] = []
    rank = 0
    for art in articles:
        ncid = art.get("news_clean_id")
        if ncid is None:
            continue
        rank += 1
        rows.append({
            "signal_id": signal_id,
            "variant": "signal",
            "news_clean_id": int(ncid),
            "rank": rank,
            "score": 0.0,
            "cosine_score": 0.0,
            "recency_weight": 0.0,
            "excerpt": art.get("excerpt"),
        })
    if not rows:
        return 0

    stmt = pg_insert(SignalArticle).values(rows).on_conflict_do_nothing(
        index_elements=["signal_id", "variant", "news_clean_id"]
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_sourcing_prod_trace.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/sourcing/prod_trace.py tests/unit/test_sourcing_prod_trace.py
git commit -m "feat(sourcing): prod_trace.record_prod_signal_articles (idempotent audit writer)"
```

---

## Task 8: Wire `record_prod_signal_articles` into `_persist_signal` + prod-audit integration test

**Files:**
- Modify: `app/signal/signal_builder.py::_persist_signal` (the async module-level function ~line 326)
- Create: `tests/integration/test_sourcing_prod_audit.py`

**Context:** The hook lands between the existing `record_baselines` call and the final `await s.commit()`. Same try/except policy — a failure in audit must never block the signal itself.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_sourcing_prod_audit.py`:

```python
"""E2E: _persist_signal writes one signal_articles row per article with variant='signal'."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import (
    Event,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalArticle,
    SignalPrediction,
)


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            # Wipe by market_id — event and signal cascade
            sig_ids = (await s.execute(
                select(Signal.id).where(Signal.market_id == "0xproda")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xproda"))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 801))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([8001, 8002])))
            await s.execute(delete(News).where(News.id.in_([88001, 88002])))
            await s.execute(delete(Event).where(Event.id == 801))
            await s.execute(delete(Market).where(Market.market_id == "0xproda"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_persist_signal_writes_signal_articles_rows(async_db_factory, _clean_up):
    from app.signal.signal_builder import _persist_signal

    async with async_db_factory() as s:
        s.add(Market(market_id="0xproda", question="q", active=True))
        s.add(Event(id=801, event_title="e"))
        await s.flush()
        for (nid, cid) in [(88001, 8001), (88002, 8002)]:
            s.add(News(id=nid, url=f"https://x/{nid}", title="t", text="b",
                       source_name="src", source_tier=1, source_weight=0.5))
            s.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}"))
            s.add(EventNewsLink(event_id=801, clean_id=cid))
        await s.commit()

    assembled = {
        "event_id": 801,
        "market_id": "0xproda",
        "market_price": 0.65,
        "reasoning": "because reasons",
        "llm_model_version": "gpt-4o-test",
        "source_tier_mix": {"tier1": 2},
        "direction_recommendation": "YES",
        "impact_score": 0.8,
        "confidence": 0.7,
        "article_excerpts": [
            {"news_clean_id": 8001, "excerpt": "quote A", "relevance": 0.9},
            {"news_clean_id": 8002, "excerpt": "quote B", "relevance": 0.8},
        ],
    }
    articles = [
        {"news_clean_id": 8001, "direction_hint": "YES", "source_weight": 0.9,
         "excerpt": "quote A"},
        {"news_clean_id": 8002, "direction_hint": "NO", "source_weight": 0.3,
         "excerpt": "quote B"},
    ]
    await _persist_signal(assembled, articles)

    async with async_db_factory() as s:
        sig = (await s.execute(
            select(Signal).where(Signal.market_id == "0xproda")
        )).scalar_one()
        rows = (await s.execute(
            select(SignalArticle).where(SignalArticle.signal_id == sig.id)
        )).scalars().all()
    assert {r.variant for r in rows} == {"signal"}
    assert {r.news_clean_id for r in rows} == {8001, 8002}
    assert sorted(r.rank for r in rows) == [1, 2]
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_prod_audit.py -v`
Expected: fails — no `signal_articles` rows exist, because the hook is not yet installed.

- [ ] **Step 3: Install the hook in `_persist_signal`**

Edit `app/signal/signal_builder.py` — inside `_persist_signal`, right after the existing `record_baselines` try/except and BEFORE `await s.commit()`:

```python
        # --- Sourcing audit (chantier #2) ------------------------------------
        try:
            from app.sourcing.prod_trace import record_prod_signal_articles
            # Prefer the richer `article_excerpts` (which carries the LLM-selected
            # quote) but fall back to the raw `articles` list when the LLM didn't
            # emit excerpts — the audit row must exist regardless.
            audit_input = assembled.get("article_excerpts") or [
                {"news_clean_id": a.get("news_clean_id"), "excerpt": None}
                for a in (articles or [])
                if a.get("news_clean_id") is not None
            ]
            await record_prod_signal_articles(
                s, signal_id=sig.id, articles=audit_input
            )
        except Exception:
            logger.exception(
                "sourcing.record_prod_signal_articles failed signal_id=%s — skipping",
                sig.id,
            )
```

Place this block immediately before `await s.commit()` so the audit rows land in the same transaction as the signal itself.

- [ ] **Step 4: Run integration test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_prod_audit.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run existing signal-hook test — nothing else must break**

Run: `docker compose exec -T app python -m pytest tests/integration/test_signal_predictions_hook.py -v`
Expected: still passes (chantier #1 test unaffected).

- [ ] **Step 6: Commit**

```bash
git add app/signal/signal_builder.py tests/integration/test_sourcing_prod_audit.py
git commit -m "feat(sourcing): wire record_prod_signal_articles into _persist_signal"
```

---

## Task 9: Celery task skeleton — `sourcing_shadow_rerun` (kill-switch + idempotency gate)

**Files:**
- Create: `app/workers/tasks_sourcing.py`
- Create: `tests/integration/test_sourcing_shadow_kill_switch.py`

**Context:** We ship the task in two halves. Task 9 wires the task file, the kill-switch check, and the idempotency gate — enough to prove the gates work without making an LLM call. Task 10 adds the pool-fetch + rank + reasoning-analyzer call + persistence inside the guard.

- [ ] **Step 1: Write the failing test (kill-switch = task must be a no-op)**

Create `tests/integration/test_sourcing_shadow_kill_switch.py`:

```python
"""Kill-switch test: with SOURCING_SHADOW_ENABLED=false the task writes nothing."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import (
    Event, Market, Signal, SignalArticle, SignalPrediction,
)


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            sig_ids = (await s.execute(
                select(Signal.id).where(Signal.market_id == "0xkill")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xkill"))
            await s.execute(delete(Event).where(Event.id == 901))
            await s.execute(delete(Market).where(Market.market_id == "0xkill"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_task_is_noop_when_disabled(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "false")
    get_settings.cache_clear()

    # Seed a signal
    async with async_db_factory() as s:
        s.add(Market(market_id="0xkill", question="q", active=True))
        s.add(Event(id=901, event_title="e"))
        await s.flush()
        sig = Signal(
            event_id=901, market_id="0xkill", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    # Invoke the task synchronously via Celery eager mode
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.apply(args=(sid,))
    finally:
        celery_app.conf.task_always_eager = False

    # Nothing should have been written
    async with async_db_factory() as s:
        preds = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == sid,
                SignalPrediction.variant == "signal_v2_reranked",
            )
        )).scalars().all()
        arts = (await s.execute(
            select(SignalArticle).where(
                SignalArticle.signal_id == sid,
                SignalArticle.variant == "signal_v2_reranked",
            )
        )).scalars().all()
    assert preds == []
    assert arts == []
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_shadow_kill_switch.py -v`
Expected: `ImportError: no module named 'app.workers.tasks_sourcing'`.

- [ ] **Step 3: Implement the task skeleton**

Create `app/workers/tasks_sourcing.py`:

```python
"""Celery task: shadow-rerun the sourcing step for a newly-persisted signal.

Chantier #2. The task is idempotent, rate-limited, and killable via
`SOURCING_SHADOW_ENABLED`. Task 9 ships the skeleton (kill-switch +
idempotency gate); Task 10 adds the pool-fetch + re-rank + LLM-rerun body.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import SignalPrediction
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


SHADOW_VARIANT = "signal_v2_reranked"


@celery_app.task(
    name="app.workers.tasks_sourcing.sourcing_shadow_rerun",
    bind=True,
    rate_limit="30/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def sourcing_shadow_rerun(self, signal_id: int) -> None:
    """Re-rank the article pool for `signal_id` and persist the shadow variant.

    Exits early (silently) on any of: kill-switch off, signal missing,
    idempotency hit, empty article pool. Other errors retry up to 3× with
    exponential backoff (30s, 60s, 120s).
    """
    try:
        return _run_async(_run_shadow(signal_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("sourcing_shadow_rerun failed signal_id=%s: %s", signal_id, exc)
        raise self.retry(exc=exc)


async def _run_shadow(signal_id: int) -> None:
    settings = get_settings()
    if not settings.sourcing_shadow_enabled:
        logger.debug("sourcing_shadow_rerun: killed by flag signal_id=%s", signal_id)
        return

    factory = get_session_factory()
    async with factory() as s:
        existing = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.variant == SHADOW_VARIANT,
            )
        )).scalar_one_or_none()
        if existing is not None:
            logger.debug("sourcing_shadow_rerun: idempotent skip signal_id=%s", signal_id)
            return

        # TASK 10 will add: load Signal/Market → fetch pool → rank → re-call
        # reasoning_analyzer → persist SignalPrediction + SignalArticle rows.
        # For now the skeleton is a no-op beyond the gates.
        return
```

- [ ] **Step 4: Register the task module in Celery autodiscover**

Edit `app/workers/celery_app.py` — add `"app.workers.tasks_sourcing"` to the `autodiscover_tasks([...])` list at the bottom:

```python
celery_app.autodiscover_tasks([
    "app.workers.tasks_ingestion",
    "app.workers.tasks_pipeline",
    "app.workers.tasks_scoring",
    "app.workers.tasks_outcomes",
    "app.workers.tasks_trading",
    "app.workers.tasks_risk",
    "app.workers.tasks_reports",
    "app.workers.tasks_sourcing",  # ← NEW
])
```

Also add a route entry so the task lands on the `scoring` queue (it shares LLM+DB traits with `tasks_scoring`):

```python
celery_app.conf.task_routes = {
    ...
    "app.workers.tasks_sourcing.*": {"queue": "scoring"},
    ...
}
```

- [ ] **Step 5: Run kill-switch test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_shadow_kill_switch.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks_sourcing.py app/workers/celery_app.py tests/integration/test_sourcing_shadow_kill_switch.py
git commit -m "feat(sourcing): shadow_rerun task skeleton (kill-switch + idempotency gate)"
```

---

## Task 10: Celery task body — pool → rank → LLM-rerun → persist + shadow integration test

**Files:**
- Modify: `app/workers/tasks_sourcing.py`
- Create: `tests/integration/test_sourcing_shadow.py`

**Context:** The task stubs a real LLM call behind `reasoning_analyzer`. We don't want integration tests to hit OpenAI, so the test monkeypatches the analyzer factory with a fake that returns a deterministic dict.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_sourcing_shadow.py`:

```python
"""End-to-end shadow test: the task writes the SignalPrediction + 5 SignalArticle rows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import (
    Event, EventNewsLink, Market, News, NewsClean,
    Signal, SignalArticle, SignalPrediction,
)


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            sig_ids = (await s.execute(
                select(Signal.id).where(Signal.market_id == "0xshadow")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xshadow"))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 910))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([6001, 6002, 6003, 6004, 6005])))
            await s.execute(delete(News).where(News.id.in_([66001, 66002, 66003, 66004, 66005])))
            await s.execute(delete(Event).where(Event.id == 910))
            await s.execute(delete(Market).where(Market.market_id == "0xshadow"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


class _FakeAnalyzer:
    model_version = "fake-v2"

    async def analyze(self, **_kwargs):
        return {
            "reasoning": "fake reasoning",
            "direction_recommendation": "YES",
            "impact_score": 0.7,
            "confidence": 0.6,
            "article_excerpts": [
                {"news_clean_id": 6001, "excerpt": "excerpt A", "relevance": 0.9},
            ],
            "source_tier_mix": {"tier1": 1},
        }


@pytest.mark.asyncio
async def test_shadow_rerun_writes_prediction_and_articles(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "true")
    get_settings.cache_clear()

    # Seed: 1 market (with embedding), 1 event, 5 articles linked to event
    # all within 72h window.
    now = datetime.now(timezone.utc)
    async with async_db_factory() as s:
        s.add(Market(
            market_id="0xshadow", question="q", active=True,
            embedding=[0.1] * 1536,
        ))
        s.add(Event(id=910, event_title="e"))
        await s.flush()
        for i, (nid, cid, age) in enumerate([
            (66001, 6001, 1),
            (66002, 6002, 5),
            (66003, 6003, 10),
            (66004, 6004, 30),
            (66005, 6005, 60),
        ]):
            s.add(News(
                id=nid, url=f"https://x/{nid}", title=f"t-{nid}", text="b",
                source_name="src", source_tier=1, source_weight=0.5,
                publish_date=now - timedelta(hours=age),
            ))
            s.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}",
                            embedding=[0.1] * 1536))
            s.add(EventNewsLink(event_id=910, clean_id=cid))
        sig = Signal(
            event_id=910, market_id="0xshadow", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    # Monkeypatch the analyzer factory used inside the task
    import app.workers.tasks_sourcing as ts_mod
    monkeypatch.setattr(ts_mod, "create_reasoning_analyzer", lambda: _FakeAnalyzer())

    # Run the task in eager mode
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.apply(args=(sid,))
    finally:
        celery_app.conf.task_always_eager = False

    async with async_db_factory() as s:
        preds = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == sid,
                SignalPrediction.variant == "signal_v2_reranked",
            )
        )).scalars().all()
        arts = (await s.execute(
            select(SignalArticle).where(
                SignalArticle.signal_id == sid,
                SignalArticle.variant == "signal_v2_reranked",
            )
        )).scalars().all()

    assert len(preds) == 1
    assert preds[0].predicted_direction == "BUY_YES"
    assert float(preds[0].predicted_probability) == pytest.approx(0.7, abs=1e-4)
    assert len(arts) == 5   # top_k default
    assert {a.rank for a in arts} == {1, 2, 3, 4, 5}


@pytest.mark.asyncio
async def test_shadow_rerun_is_idempotent(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "true")
    get_settings.cache_clear()

    now = datetime.now(timezone.utc)
    async with async_db_factory() as s:
        s.add(Market(market_id="0xshadow", question="q", active=True,
                     embedding=[0.1] * 1536))
        s.add(Event(id=910, event_title="e"))
        await s.flush()
        s.add(News(id=66001, url="https://x/1", title="t", text="b",
                   source_name="src", source_tier=1, source_weight=0.5,
                   publish_date=now - timedelta(hours=1)))
        s.add(NewsClean(id=6001, news_id=66001, clean_text="c",
                        embedding=[0.1] * 1536))
        s.add(EventNewsLink(event_id=910, clean_id=6001))
        sig = Signal(
            event_id=910, market_id="0xshadow", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    import app.workers.tasks_sourcing as ts_mod
    monkeypatch.setattr(ts_mod, "create_reasoning_analyzer", lambda: _FakeAnalyzer())

    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.apply(args=(sid,))
        sourcing_shadow_rerun.apply(args=(sid,))  # second run
    finally:
        celery_app.conf.task_always_eager = False

    async with async_db_factory() as s:
        preds = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == sid,
                SignalPrediction.variant == "signal_v2_reranked",
            )
        )).scalars().all()
    # Second run must NOT create a second prediction row.
    assert len(preds) == 1
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_shadow.py -v`
Expected: fails — `_run_shadow` is a no-op stub and no rows exist.

- [ ] **Step 3: Implement the task body**

Replace the `_run_shadow` body in `app/workers/tasks_sourcing.py` so the file becomes:

```python
"""Celery task: shadow-rerun the sourcing step for a newly-persisted signal."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import (
    Market, Signal, SignalArticle, SignalPrediction,
)
from app.llm.reasoning_analyzer import create_reasoning_analyzer
from app.sourcing.article_ranker import ArticleRanker
from app.sourcing.pool_builder import fetch_candidate_articles
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


SHADOW_VARIANT = "signal_v2_reranked"


@celery_app.task(
    name="app.workers.tasks_sourcing.sourcing_shadow_rerun",
    bind=True,
    rate_limit="30/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def sourcing_shadow_rerun(self, signal_id: int) -> None:
    try:
        return _run_async(_run_shadow(signal_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("sourcing_shadow_rerun failed signal_id=%s: %s", signal_id, exc)
        raise self.retry(exc=exc)


def _dir_llm_to_db(d: str | None) -> str | None:
    """Map the analyzer's 'YES'/'NO'/'UNCLEAR' to the DB enum. Returns None on UNCLEAR."""
    if not d:
        return None
    u = d.upper()
    if u == "YES":
        return "BUY_YES"
    if u == "NO":
        return "BUY_NO"
    return None


async def _run_shadow(signal_id: int) -> None:
    settings = get_settings()
    if not settings.sourcing_shadow_enabled:
        logger.debug("sourcing_shadow_rerun: killed by flag signal_id=%s", signal_id)
        return

    factory = get_session_factory()
    async with factory() as s:
        # Idempotency gate
        existing = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.variant == SHADOW_VARIANT,
            )
        )).scalar_one_or_none()
        if existing is not None:
            return

        sig = await s.get(Signal, signal_id)
        if sig is None:
            logger.info("sourcing_shadow_rerun: signal vanished id=%s", signal_id)
            return

        market = await s.get(Market, sig.market_id)
        if market is None:
            logger.info("sourcing_shadow_rerun: market missing id=%s", sig.market_id)
            return

        pool = await fetch_candidate_articles(
            s,
            event_id=sig.event_id,
            t0=sig.created_at,
            window_hours=settings.sourcing_pool_window_hours,
        )
        if not pool:
            logger.debug("sourcing_shadow_rerun: empty pool event_id=%s", sig.event_id)
            return

        ranker = ArticleRanker.from_settings(settings)
        ranked = ranker.rank(
            pool,
            market.embedding,
            sig.created_at,
            top_k=settings.sourcing_top_k,
        )
        if not ranked:
            return

        # Build the dict shape reasoning_analyzer expects.
        by_id = {p["news_clean_id"]: p for p in pool}
        article_dicts = []
        for r in ranked:
            p = by_id[r.news_clean_id]
            article_dicts.append({
                "news_clean_id": r.news_clean_id,
                "title": p.get("clean_text", "")[:120],  # title field absent on clean; truncate body as stand-in
                "source_name": p["source_name"],
                "source_tier": p["source_tier"],
                "publish_date": p["publish_date"].isoformat() if p.get("publish_date") else None,
                "clean_text": p["clean_text"],
            })

        analyzer = create_reasoning_analyzer()
        # Event/market dicts the analyzer expects:
        event = {"title": "", "summary": ""}
        try:
            from app.db.models import Event
            ev = await s.get(Event, sig.event_id) if sig.event_id else None
            if ev is not None:
                event = {"title": ev.event_title, "summary": ev.event_summary or ""}
        except Exception:
            pass

        llm = await analyzer.analyze(
            event_title=event["title"],
            event_summary=event["summary"],
            articles=article_dicts,
            market_question=market.question,
            market_price=float(sig.market_price_at_signal or 0.0),
        )
        if llm is None:
            logger.info("sourcing_shadow_rerun: analyzer returned None signal_id=%s", signal_id)
            return

        # Excerpts per news_clean_id so we can store them on SignalArticle rows
        excerpts_by_id: dict[int, str] = {}
        for exc in (llm.get("article_excerpts") or []):
            ncid = exc.get("news_clean_id")
            if ncid is not None and exc.get("excerpt"):
                excerpts_by_id[int(ncid)] = exc["excerpt"]

        direction = _dir_llm_to_db(llm.get("direction_recommendation"))
        prob = llm.get("impact_score")
        try:
            prob = float(prob) if prob is not None else None
        except (TypeError, ValueError):
            prob = None

        s.add(SignalPrediction(
            signal_id=signal_id,
            variant=SHADOW_VARIANT,
            predicted_direction=direction,
            predicted_probability=prob,
        ))
        for r in ranked:
            s.add(SignalArticle(
                signal_id=signal_id,
                variant=SHADOW_VARIANT,
                news_clean_id=r.news_clean_id,
                rank=r.rank,
                score=r.score,
                cosine_score=r.cosine,
                recency_weight=r.recency_weight,
                excerpt=excerpts_by_id.get(r.news_clean_id),
            ))
        await s.commit()
```

- [ ] **Step 4: Run integration test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_shadow.py -v`
Expected: 2 passed.

- [ ] **Step 5: Re-run kill-switch test — body change must not break it**

Run: `docker compose exec -T app python -m pytest tests/integration/test_sourcing_shadow_kill_switch.py -v`
Expected: still 1 passed.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks_sourcing.py tests/integration/test_sourcing_shadow.py
git commit -m "feat(sourcing): shadow_rerun body — pool → rank → LLM → persist (prediction + 5 articles)"
```

---

## Task 11: Wire `schedule_shadow_variants` → `sourcing_shadow_rerun.delay()`

**Files:**
- Modify: `app/measurement/pipeline.py::schedule_shadow_variants`

**Context:** Chantier #1 left `schedule_shadow_variants` as a `logger.debug` stub. We replace the body with a try/except that enqueues the Celery task. A broken Celery must not kill signal persistence — the try/except is the guard.

- [ ] **Step 1: Replace the stub**

Edit `app/measurement/pipeline.py::schedule_shadow_variants`:

```python
def schedule_shadow_variants(signal_id: int) -> None:
    """Fire-and-forget shadow variant dispatch.

    Chantier #2: enqueues `sourcing_shadow_rerun` on the 'scoring' queue. The
    import is local so module load doesn't pull in Celery at API startup, and
    wrapped in a try/except so a broken broker never prevents a signal from
    committing.
    """
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.delay(signal_id)
    except Exception:
        logger.exception(
            "schedule_shadow_variants: failed to enqueue signal_id=%s — continuing",
            signal_id,
        )
```

- [ ] **Step 2: Add a unit-ish test that the scheduler calls `.delay(...)`**

Append to `tests/unit/test_measurement_pipeline.py`:

```python
def test_schedule_shadow_variants_enqueues_celery_task(monkeypatch):
    """schedule_shadow_variants must call sourcing_shadow_rerun.delay(signal_id)."""
    from app.measurement import pipeline as pmod

    called = {}

    class _FakeTask:
        def delay(self, signal_id):
            called["signal_id"] = signal_id

    # Patch the import site — schedule_shadow_variants does a local import, so
    # we patch the module attribute it imports from.
    import app.workers.tasks_sourcing as ts
    monkeypatch.setattr(ts, "sourcing_shadow_rerun", _FakeTask())

    pmod.schedule_shadow_variants(12345)
    assert called == {"signal_id": 12345}


def test_schedule_shadow_variants_swallows_import_error(monkeypatch, caplog):
    """If Celery is unreachable, the scheduler logs and returns — no raise."""
    from app.measurement import pipeline as pmod

    # Simulate a broker failure by raising from .delay
    class _BrokenTask:
        def delay(self, signal_id):
            raise RuntimeError("broker down")

    import app.workers.tasks_sourcing as ts
    monkeypatch.setattr(ts, "sourcing_shadow_rerun", _BrokenTask())

    # Must not raise
    pmod.schedule_shadow_variants(54321)
```

Replace the pre-existing `test_schedule_shadow_variants_is_a_noop_stub` with the two tests above (the stub test is obsolete now that the body does something).

- [ ] **Step 3: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_pipeline.py -v`
Expected: all tests green (the updated scheduler tests included).

- [ ] **Step 4: Smoke — a signal enqueue shows up in Celery logs (dev)**

Run (in one terminal): `docker compose logs -f worker-scoring 2>&1 | grep sourcing`

Then in another terminal, synthesize a signal (use the pattern from chantier #1's task 15 smoke) — confirm one log line per signal:
`Received task: app.workers.tasks_sourcing.sourcing_shadow_rerun[...]`

You may also verify by listing queued tasks: `docker compose exec -T redis redis-cli LRANGE scoring 0 -1 | head`.

- [ ] **Step 5: Commit**

```bash
git add app/measurement/pipeline.py tests/unit/test_measurement_pipeline.py
git commit -m "feat(sourcing): wire schedule_shadow_variants → sourcing_shadow_rerun.delay"
```

---

## Task 12: Runbook — `docs/runbooks/promote_signal_v2.md`

**Files:**
- Create: `docs/runbooks/promote_signal_v2.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/promote_signal_v2.md`:

```markdown
# Promote `signal_v2_reranked` to production

This is a **manual** gate. Nothing auto-promotes. Run it when the shadow
variant has accumulated enough data to judge it honestly.

## Pre-conditions

1. ≥ 14 calendar days of shadow traffic (i.e. at least 14 days since the first
   `signal_v2_reranked` row landed in `signal_predictions`).
2. `n_resolved ≥ 100` per variant in the current 14-day window — check:
   ```bash
   docker compose exec -T app python -m scripts.report_metrics --window 14d
   ```
   Both `signal` and `signal_v2_reranked` must show `n ≥ 100`.

If either condition is not met: **wait longer**. Small samples will lie.

## The gate

Promotion is allowed **if and only if all three hold**:

| Check                                            | Pass condition                                                     |
|--------------------------------------------------|--------------------------------------------------------------------|
| `wilson_ci95_low("signal_v2_reranked")`          | `> wilson_ci95_high("signal")`                                     |
| `brier("signal_v2_reranked")`                    | `< brier("signal")`                                                |
| `pnl_total("signal_v2_reranked")`                | `> pnl_total("signal")`                                            |

All three numbers come from `/api/admin/metrics/variants?window=14d`. The CLI
report renders them side by side — eyeball or script the comparison.

If **any** check fails: do NOT promote. Options:

- Tune `SOURCING_ALPHA` / `SOURCING_BETA` / `SOURCING_RECENCY_TAU_HOURS`, redeploy, wait another week.
- Widen/narrow `SOURCING_POOL_WINDOW_HOURS`.
- Add per-tier source weighting (next chantier).

## The promotion (code change)

1. In `app/signal/signal_builder.py::build_signal`, replace the existing
   recency-only article selection with the `ArticleRanker`-backed path:

   ```python
   pool = await fetch_candidate_articles(s, event_id=event["id"], t0=now,
                                         window_hours=settings.sourcing_pool_window_hours)
   ranker = ArticleRanker.from_settings(settings)
   ranked = ranker.rank(pool, market_embedding, t0=now, top_k=settings.sourcing_top_k)
   articles = [by_id[r.news_clean_id] for r in ranked]   # same dict shape as today
   ```

2. Remove `app/workers/tasks_sourcing.py` and the autodiscover entry in
   `app/workers/celery_app.py` — the shadow task has no more reason to run.

3. Rename the production variant in `_persist_signal` recording so the
   measurement layer keeps a clean "before/after" split:

   ```python
   # ...in record_baselines, change the variant label for the prod row from
   #   "signal"  →  "signal_v2"    (this is the *next* name, not the shadow)
   # OR (preferred): leave record_baselines alone; rely on the historical
   # divide in resolved_at — rows before the deploy are "signal_v1", after
   # are "signal_v2". No code change needed if the CLI can slice by
   # resolved_at window.
   ```

4. Update `.env` on prod: `SOURCING_SHADOW_ENABLED=false` (redundant after
   step 2 but a belt-and-suspenders safeguard).

5. Deploy. Run `scripts/report_metrics --window 14d` the next day — the new
   variant should start accumulating rows.

## Rollback

If the promoted variant regresses vs the historical baseline after 1 week:

1. Revert the promotion commit (single commit that bundles steps 1–4 above).
2. Redeploy. No DB migration needed — `signal_articles` with `variant='signal'`
   and `variant='signal_v2_reranked'` stay valid historical records.

## Audit a specific signal

To see the five articles any given signal saw under each variant:

```sql
SELECT sa.variant, sa.rank, sa.score, sa.cosine_score, sa.recency_weight,
       nc.clean_text ~ 'fragment' AS matched_text_fragment,
       n.title, n.source_name, n.publish_date
FROM signal_articles sa
JOIN news_clean nc ON nc.id = sa.news_clean_id
JOIN news n ON n.id = nc.news_id
WHERE sa.signal_id = <id>
ORDER BY sa.variant, sa.rank;
```
```

- [ ] **Step 2: Smoke — the file exists and renders**

Run: `docker compose exec -T app python -c "from pathlib import Path; p = Path('docs/runbooks/promote_signal_v2.md'); assert p.exists() and p.stat().st_size > 500; print(f'{p.stat().st_size} bytes')"`
Expected: prints something like `3500 bytes`.

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/promote_signal_v2.md
git commit -m "docs(sourcing): promote_signal_v2 runbook with the 3-check gate"
```

---

## Task 13: Final verification — full test suite + live-DB smoke

**Files:** none.

- [ ] **Step 1: Run the full backend test suite**

Run:
```bash
docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q
```
Expected: all green. The `test_migration_014` ignore is the documented
pre-existing flake.

- [ ] **Step 2: Re-run the chantier #1 + chantier #2 tests together**

Run:
```bash
docker compose exec -T app python -m pytest \
  tests/unit/test_measurement_* \
  tests/unit/test_admin_require_admin.py \
  tests/unit/test_backfill_signal_predictions.py \
  tests/unit/test_article_ranker.py \
  tests/unit/test_sourcing_pool_builder.py \
  tests/unit/test_sourcing_prod_trace.py \
  tests/integration/test_signal_predictions_hook.py \
  tests/integration/test_resolution_hook.py \
  tests/integration/test_admin_metrics_variants.py \
  tests/integration/test_admin_metrics_rolling.py \
  tests/integration/test_sourcing_prod_audit.py \
  tests/integration/test_sourcing_shadow.py \
  tests/integration/test_sourcing_shadow_kill_switch.py \
  -v
```
Expected: every test green.

- [ ] **Step 3: Live-DB smoke — produce one new signal and confirm both paths fire**

Option A — wait for a fresh signal from a beat-scheduled task, then query:

```bash
docker compose exec -T db psql -U postgres -d signal -c "
  SELECT sa.signal_id, sa.variant, COUNT(*) AS n_articles
  FROM signal_articles sa
  WHERE sa.signal_id IN (
    SELECT id FROM signals ORDER BY id DESC LIMIT 3
  )
  GROUP BY sa.signal_id, sa.variant
  ORDER BY sa.signal_id DESC, sa.variant;"
```

Expected (after the shadow task has had ~60s to run): for each recent signal,
TWO rows in the output — one `(signal, 2-5)` and one `(signal_v2_reranked, 5)`.
If only the `signal` row appears, check `docker compose logs worker-scoring`
for task retries or kill-switch messages.

Option B — trigger `_persist_signal` directly (like chantier #1's task 15
smoke) and then wait ~30s before running the query above.

- [ ] **Step 4: Confirm the admin endpoint shows the new variant**

Run (requires an admin JWT — reuse from chantier #1 smoke):
```bash
docker compose exec -T app python -m scripts.report_metrics --window 14d --json \
  --token $ADMIN_TOKEN | jq '.variants | map(.variant)'
```
Expected (may take time once resolutions start landing): the array includes
`"signal_v2_reranked"` alongside the four baselines and `"signal"`.

- [ ] **Step 5: Verify the working tree is clean and count commits**

Run: `git status && git log --oneline main..HEAD`
Expected: working tree clean; ~13 commits (one per task, give or take).

Merge to `main` is **not** part of this plan — leave that to human review
after shadow data has accumulated for a few days.

---

## Rollout checklist (operator — not engineer)

1. Apply migration `021` on production.
2. Deploy new code with `SOURCING_SHADOW_ENABLED=true` (default).
3. Verify Celery worker on the `scoring` queue picks up `sourcing_shadow_rerun` in logs within 5 minutes.
4. Wait ≥ 14 days of shadow traffic.
5. `docker compose exec app python -m scripts.report_metrics --window 14d` — first honest read.
6. If the gate in `docs/runbooks/promote_signal_v2.md` passes, promote. Otherwise tune and wait.

## Known limitations (for chantier follow-ups)

- **No LLM reranker.** If embedding + recency isn't enough, cascade (embedding pre-filter → LLM fine-rank) is a future chantier — design already in the spec's §Non-goals.
- **No per-tier weight in the composite score.** `source_weight` is fetched by the pool builder but unused by the ranker today. Ready to plug in once we have correlation data between source tier and outcome.
- **Market embedding staleness.** If a market's question is edited after creation, the market embedding from signal time may not match the shadow task time. Documented as acceptable drift.
- **No online promotion automation.** The runbook is human-in-the-loop by design. Future chantier may add a `/api/admin/metrics/promote-if-ready` endpoint.
