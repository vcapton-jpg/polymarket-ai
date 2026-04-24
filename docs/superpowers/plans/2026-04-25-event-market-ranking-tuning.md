# Event→Market Ranking Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the event→market hybrid search from hand-picked constants into an empirically-tuned ranker, gated by a human-seeded + LLM-calibrated ground-truth label set (~1000 pairs) and a 48h shadow observation window — all on top of the chantier #3 eval harness.

**Architecture:** Add a v2 ranking formula (`hybrid_search_v2.py`) with two new features (date-proximity decay, bucket-match boost) and 5 tunable weights, routed per-surface via a feature flag (`ranking_variant_event_to_market`). Ground truth is built by a human-seeded CLI (50-500 pairs) then scaled via a calibrated LLM-judge. An offline tuning script (coordinate descent) writes the best config; a Celery shadow task records the opposite-variant top-k for 48h before operators flip the flag via a 3-check runbook. v1 (`hybrid_search.py`) stays bit-exact as a regression shield.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async (`Mapped` / `mapped_column`), Alembic (revision `024`, `down_revision="023"`), pgvector 1536-dim (already in place), Celery + Redis, OpenAI `gpt-4o-mini` (LLM judge, offline only), pytest-asyncio, the chantier #3 harness (`app/eval/{labels,metrics,runner}.py`).

**Spec:** `docs/superpowers/specs/2026-04-25-event-market-ranking-tuning-design.md`. Read it once before starting — §4 (ground truth), §5 (v2 formula), §6 (tuning), §7 (shadow rollout) are the ground truth.

**Depends on (already shipped in chantiers #1, #2, #3):**
- `app/retrieval/hybrid_search.py` + `app/retrieval/vector_retriever.py` + `app/retrieval/bm25_index.py` (v1 path, stays untouched).
- `app/eval/{labels,metrics,runner}.py` — the harness runner, `LabeledPair`-analog (`EvalPair`), bootstrap CI, retrieval@k / nDCG@k.
- `app/processing/embedding_reader.py` — `get_active_embedding` + `active_column_name`; the event→market ranking reads the active **embedding** variant through it, and this chantier adds the analogous ranking-variant flag on top.
- `app/core/config.py::Settings` with `@lru_cache` on `get_settings`. `get_settings.cache_clear()` is used in tests.
- `app/workers/_async_helpers.run_async` for async-in-Celery.
- `app/workers/celery_app.py` — `autodiscover_tasks([...])` + `task_routes`.
- `app/db/models.py::Event,Market` with `bucket`, `last_seen`, `end_date`, `embedding`, `embedding_v2`.

**Branch target:** continue on `pivot/learn-and-trade` (current branch). No new worktree — this chantier is a linear continuation.

---

## File structure (created / modified)

**New files:**
- `alembic/versions/024_add_event_market_ranking_shadow.py` — shadow table migration (task 1)
- `app/retrieval/ranking_variant.py` — `active_ranking_variant()` helper + dispatcher (task 3)
- `app/retrieval/hybrid_search_v2.py` — `date_proximity`, `bucket_match`, `hybrid_search_markets_v2` (tasks 4 + 5)
- `app/eval/labels_event_market.py` — `EventMarketPair` dataclass + `load_event_market_labels` + LLM-judge (tasks 7 + 10 + 11)
- `scripts/label_event_market_seed.py` — human review CLI (tasks 8 + 9)
- `scripts/tune_event_market_ranking.py` — coordinate descent + offline gate (tasks 12 + 13)
- `scripts/analyze_ranking_shadow.py` — shadow observation report (task 16)
- `app/workers/tasks_ranking_shadow.py` — Celery `record_shadow_ranking` (task 14)
- `docs/eval_labels/.gitkeep` (task 8)
- `docs/runbooks/promote_ranking_v2.md` — operator runbook (task 17)
- `tests/unit/test_ranking_variant.py` (task 3)
- `tests/unit/test_hybrid_search_v2.py` (tasks 4 + 5)
- `tests/unit/test_labels_event_market.py` (tasks 7 + 11)
- `tests/unit/test_tune_event_market_ranking.py` (task 13)
- `tests/integration/test_ranking_shadow.py` — Celery eager + shadow-row idempotence (tasks 14 + 15)
- `tests/integration/test_hybrid_search_v2_db.py` — dispatcher routes by flag (task 5)

**Modified files:**
- `app/core/config.py` — add 8 new settings (task 2)
- `app/retrieval/__init__.py` — re-export the dispatcher; keep the v1 symbol available for tests (task 5)
- `app/retrieval/hybrid_search.py` — **untouched** (v1 bit-exact regression shield — do not edit in any task)
- `app/workers/tasks_scoring.py` — insert shadow hook after `candidates_found` (task 15)
- `app/workers/celery_app.py` — `autodiscover_tasks([..., "app.workers.tasks_ranking_shadow"])` and route to the `scoring` queue (task 14)

---

## Task 1: Alembic migration — `event_market_ranking_shadow` table

**Files:**
- Create: `alembic/versions/024_add_event_market_ranking_shadow.py`

- [ ] **Step 1: Write the migration**

```python
"""add event_market_ranking_shadow table.

Revision ID: 024
Revises: 023
Create Date: 2026-04-25

Table records the top-k output of the *opposite* ranking variant (v1 in prod
→ store v2, and vice versa) so operators can compare divergence before
flipping the `ranking_variant_event_to_market` flag. Rows are write-once,
idempotent via the UNIQUE (event_id, variant, rank) constraint.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_market_ranking_shadow",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("rrf_score", sa.Float(), nullable=False),
        sa.Column("cosine_score", sa.Float(), nullable=True),
        sa.Column("entity_matches", sa.Integer(), nullable=True),
        sa.Column("date_proximity", sa.Float(), nullable=True),
        sa.Column("bucket_match", sa.Boolean(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.CheckConstraint("variant IN ('v1','v2')", name="ck_ranking_shadow_variant"),
        sa.UniqueConstraint(
            "event_id", "variant", "rank",
            name="uq_ranking_shadow_event_variant_rank",
        ),
    )
    op.create_index(
        "ix_ranking_shadow_event_variant",
        "event_market_ranking_shadow",
        ["event_id", "variant"],
    )


def downgrade() -> None:
    op.drop_index("ix_ranking_shadow_event_variant", table_name="event_market_ranking_shadow")
    op.drop_table("event_market_ranking_shadow")
```

- [ ] **Step 2: Apply the migration**

Run: `docker compose exec -T app alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 023 -> 024, add event_market_ranking_shadow table.`

- [ ] **Step 3: Verify the table exists**

Run:
```bash
docker compose exec -T postgres psql -U polyedge -d polyedge -c "\d event_market_ranking_shadow"
```
Expected: columns `id, event_id, market_id, variant, rank, rrf_score, cosine_score, entity_matches, date_proximity, bucket_match, computed_at`. Check constraint `ck_ranking_shadow_variant`. Unique constraint `uq_ranking_shadow_event_variant_rank`. Index `ix_ranking_shadow_event_variant`.

- [ ] **Step 4: Add the ORM model to `app/db/models.py`**

Insert after the `EventMarketFeatures` class (line ~370) — keep the "ranking / shadow" artefacts grouped alongside other event/market link tables:

```python
# ---------------------------------------------------------------------------
# event_market_ranking_shadow  (chantier #4 — opposite-variant observation)
# ---------------------------------------------------------------------------
class EventMarketRankingShadow(Base):
    __tablename__ = "event_market_ranking_shadow"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_id: Mapped[str] = mapped_column(Text, nullable=False)
    variant: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    rrf_score: Mapped[float] = mapped_column(Float, nullable=False)
    cosine_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entity_matches: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    date_proximity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bucket_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("variant IN ('v1','v2')", name="ck_ranking_shadow_variant"),
        UniqueConstraint(
            "event_id", "variant", "rank",
            name="uq_ranking_shadow_event_variant_rank",
        ),
    )
```

If `BigInteger`, `ForeignKey`, `Float`, `CheckConstraint`, or `UniqueConstraint` aren't already imported at the top of `app/db/models.py`, add them to the existing `from sqlalchemy import …` line.

- [ ] **Step 5: Verify the ORM model imports cleanly**

Run: `docker compose exec -T app python -c "from app.db.models import EventMarketRankingShadow; print(EventMarketRankingShadow.__tablename__)"`
Expected: `event_market_ranking_shadow`

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/024_add_event_market_ranking_shadow.py app/db/models.py
git commit -m "feat(ranking): migration 024 — event_market_ranking_shadow table"
```

---

## Task 2: Config settings — 7 flags for ranking v2

**Files:**
- Modify: `app/core/config.py` (append to the "Eval harness (chantier #3)" block around line 195)
- Test: `tests/unit/test_ranking_variant.py` (skeleton only in this task — full coverage in task 3)

- [ ] **Step 1: Add the settings**

In `app/core/config.py`, insert **after** the `embeddings_variant_event` field and **before** the `# ── Application ────` section header:

```python
    # ── Ranking v2 (chantier #4) ──────────────────────────────────────
    ranking_variant_event_to_market: str = Field(
        default="v1",
        description="Active ranking variant for event→market retrieval. 'v1' (current) or 'v2' (tuned).",
    )
    ranking_shadow_enabled: bool = Field(
        default=True,
        description="Kill switch for the event_market_ranking_shadow Celery task.",
    )
    ranking_v2_rrf_k: int = Field(
        default=60,
        description="RRF k-constant for hybrid_search_v2.",
    )
    ranking_v2_w_entity: float = Field(
        default=0.5,
        description="Weight of the entity-match bonus in hybrid_search_v2.",
    )
    ranking_v2_w_date: float = Field(
        default=0.0,
        description="Weight of the date-proximity bonus in hybrid_search_v2. Defaults to 0 → v2 ≡ v1.",
    )
    ranking_v2_w_bucket: float = Field(
        default=0.0,
        description="Weight of the bucket-match bonus in hybrid_search_v2. Defaults to 0 → v2 ≡ v1.",
    )
    ranking_v2_tau_days: float = Field(
        default=14.0,
        description="Exponential-decay time constant (days) for date-proximity boost.",
    )
    ranking_v2_min_sim: float = Field(
        default=0.45,
        description="Minimum cosine similarity threshold for v2 vector retrieval.",
    )
```

- [ ] **Step 2: Verify the settings load cleanly**

Run: `docker compose exec -T app python -c "from app.core.config import get_settings; s = get_settings(); print(s.ranking_variant_event_to_market, s.ranking_v2_w_date, s.ranking_v2_tau_days)"`
Expected: `v1 0.0 14.0`

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(ranking): add 7 ranking_v2_* settings (defaults reproduce v1)"
```

---

## Task 3: `ranking_variant.py` — flag helper + dispatcher shell

**Files:**
- Create: `app/retrieval/ranking_variant.py`
- Create: `tests/unit/test_ranking_variant.py`

The dispatcher is added now as a **shell** that only routes to v1 (v2 doesn't exist yet). Task 5 wires up the v2 branch once `hybrid_search_v2` is written. This lets us land the flag helper with full test coverage first, TDD-style.

- [ ] **Step 1: Write the unit tests**

```python
# tests/unit/test_ranking_variant.py
"""Tests for the ranking-variant dispatcher."""
from __future__ import annotations

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_active_ranking_variant_defaults_to_v1():
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v1"


def test_active_ranking_variant_returns_v2(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
    get_settings.cache_clear()
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v2"


def test_active_ranking_variant_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v99")
    get_settings.cache_clear()
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v1"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_v1(monkeypatch):
    """Dispatcher with variant=v1 delegates to hybrid_search.hybrid_search_markets."""
    captured: dict = {}

    async def fake_v1(session, emb, text, **kwargs):
        captured["variant"] = "v1"
        return [{"market_id": "m1", "rrf_score": 0.1, "rank": 1}]

    monkeypatch.setattr(
        "app.retrieval.hybrid_search.hybrid_search_markets", fake_v1
    )

    from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
    out = await hybrid_search_markets_dispatch(None, [0.0] * 1536, "hello")
    assert captured["variant"] == "v1"
    assert out and out[0]["market_id"] == "m1"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_v2_when_flag_set(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
    get_settings.cache_clear()

    captured: dict = {}

    async def fake_v2(session, emb, text, **kwargs):
        captured["variant"] = "v2"
        return [{"market_id": "m2", "rrf_score": 0.2, "rank": 1}]

    # The v2 module will be imported lazily inside the dispatcher; monkeypatch
    # it *after* importing so the symbol exists.
    import app.retrieval.hybrid_search_v2  # noqa: F401
    monkeypatch.setattr(
        "app.retrieval.hybrid_search_v2.hybrid_search_markets_v2", fake_v2
    )

    from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
    out = await hybrid_search_markets_dispatch(None, [0.0] * 1536, "hello")
    assert captured["variant"] == "v2"
    assert out[0]["market_id"] == "m2"
```

- [ ] **Step 2: Run tests — expect failures (module not yet created)**

Run: `docker compose exec -T app python -m pytest tests/unit/test_ranking_variant.py -v`
Expected: 5 failures with `ModuleNotFoundError: No module named 'app.retrieval.ranking_variant'`.

- [ ] **Step 3: Implement `ranking_variant.py`**

Create `app/retrieval/ranking_variant.py`:

```python
"""Feature-flag dispatcher for the event→market hybrid search.

Routes callers to either `hybrid_search.hybrid_search_markets` (v1, frozen)
or `hybrid_search_v2.hybrid_search_markets_v2` (v2, tuned) based on the
`ranking_variant_event_to_market` setting.

Callers should always use `hybrid_search_markets_dispatch(...)` — never
import v1/v2 directly in production code. (Tests may import them for
bit-exact comparison.)
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_VALID_VARIANTS = ("v1", "v2")


def active_ranking_variant() -> str:
    """Return 'v1' or 'v2'. Any other value falls back to 'v1'."""
    v = getattr(get_settings(), "ranking_variant_event_to_market", "v1")
    return v if v in _VALID_VARIANTS else "v1"


async def hybrid_search_markets_dispatch(
    session: AsyncSession,
    event_embedding: list[float],
    event_text: str,
    top_k: Optional[int] = None,
    event_bucket: Optional[str] = None,
    event_entities: Optional[list[str]] = None,
    event_last_seen=None,
) -> list[dict]:
    """Route to v1 or v2 based on the active ranking variant."""
    variant = active_ranking_variant()
    if variant == "v2":
        from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
        return await hybrid_search_markets_v2(
            session, event_embedding, event_text,
            top_k=top_k,
            event_bucket=event_bucket,
            event_entities=event_entities,
            event_last_seen=event_last_seen,
        )
    from app.retrieval.hybrid_search import hybrid_search_markets
    return await hybrid_search_markets(
        session, event_embedding, event_text,
        top_k=top_k,
        event_bucket=event_bucket,
        event_entities=event_entities,
    )
```

`app/retrieval/hybrid_search_v2` does not exist yet; the `test_dispatcher_routes_to_v2_when_flag_set` test imports it to monkeypatch its symbol. Create a **stub** file so the import succeeds:

```python
# app/retrieval/hybrid_search_v2.py
"""Placeholder — real implementation lands in task 5."""

async def hybrid_search_markets_v2(*args, **kwargs):  # pragma: no cover
    raise NotImplementedError("hybrid_search_markets_v2 is implemented in task 5")
```

- [ ] **Step 4: Run tests — expect pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_ranking_variant.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/retrieval/ranking_variant.py app/retrieval/hybrid_search_v2.py tests/unit/test_ranking_variant.py
git commit -m "feat(ranking): ranking_variant dispatcher (routes v1 in prod)"
```

---

## Task 4: `hybrid_search_v2` — pure helper functions `date_proximity` + `bucket_match`

**Files:**
- Modify: `app/retrieval/hybrid_search_v2.py`
- Create: `tests/unit/test_hybrid_search_v2.py`

The v2 formula (spec §5.2) splits cleanly into two pure helpers and the orchestration. We TDD the helpers first — they are side-effect free and carry all the formula's edge cases (end_date in the past, None event bucket, "other" bucket, etc.).

- [ ] **Step 1: Write unit tests for `date_proximity` and `bucket_match`**

```python
# tests/unit/test_hybrid_search_v2.py
"""Tests for hybrid_search_v2 — helper functions + v1-equivalence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


# ═══════════════════ date_proximity ═══════════════════

def test_date_proximity_none_end_date_returns_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    assert date_proximity(market_end_date=None, event_last_seen=_utc(2026, 4, 25), tau_days=14) == 0.0


def test_date_proximity_past_end_date_returns_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 4, 20),
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == 0.0


def test_date_proximity_within_7_days_returns_one():
    """Within the 7-day floor, decay = exp(0) = 1."""
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 5, 1),  # 6 days after event
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == pytest.approx(1.0)


def test_date_proximity_decays_exponentially():
    """21 days out, tau=14 → exp(-(21-7)/14) = exp(-1) ≈ 0.3679."""
    import math
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2026, 5, 16),  # 21 days after event
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got == pytest.approx(math.exp(-1.0), rel=1e-3)


def test_date_proximity_far_future_approaches_zero():
    from app.retrieval.hybrid_search_v2 import date_proximity
    got = date_proximity(
        market_end_date=_utc(2027, 4, 25),  # 365 days out
        event_last_seen=_utc(2026, 4, 25),
        tau_days=14,
    )
    assert got < 1e-10


# ═══════════════════ bucket_match ═══════════════════

def test_bucket_match_same_bucket_returns_one():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="politics", event_bucket="politics") == 1.0


def test_bucket_match_different_bucket_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="sports", event_bucket="politics") == 0.0


def test_bucket_match_event_bucket_none_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="politics", event_bucket=None) == 0.0


def test_bucket_match_event_bucket_other_returns_zero():
    """'other' is not a real bucket — refuse to match on it."""
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket="other", event_bucket="other") == 0.0


def test_bucket_match_market_bucket_none_returns_zero():
    from app.retrieval.hybrid_search_v2 import bucket_match
    assert bucket_match(market_bucket=None, event_bucket="politics") == 0.0
```

- [ ] **Step 2: Run tests — expect failures**

Run: `docker compose exec -T app python -m pytest tests/unit/test_hybrid_search_v2.py -v`
Expected: 10 failures with `ImportError: cannot import name 'date_proximity' …`.

- [ ] **Step 3: Implement the helpers**

Replace the stub in `app/retrieval/hybrid_search_v2.py` with:

```python
"""Hybrid search v2 — v1 + date-proximity + bucket-match.

The main entry point `hybrid_search_markets_v2` is defined in task 5.
This module lands in two steps so the pure helpers can be TDD'd first.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional


def date_proximity(
    market_end_date: Optional[datetime],
    event_last_seen: datetime,
    tau_days: float,
) -> float:
    """Exponential decay past a 7-day floor; 0 if the market is already past.

    Returns 1.0 when the market ends within 7 days of the event, then decays
    as exp(-(days_until - 7) / tau_days). Returns 0.0 when end_date is None
    or already past.
    """
    if market_end_date is None:
        return 0.0
    days_until = (market_end_date - event_last_seen).total_seconds() / 86400.0
    if days_until < 0:
        return 0.0
    if days_until <= 7.0:
        return 1.0
    if tau_days <= 0:
        return 0.0
    return math.exp(-(days_until - 7.0) / tau_days)


def bucket_match(market_bucket: Optional[str], event_bucket: Optional[str]) -> float:
    """1.0 iff both are the same real bucket; 0.0 for None/other/mismatch."""
    if event_bucket is None or event_bucket == "other":
        return 0.0
    if market_bucket is None:
        return 0.0
    return 1.0 if market_bucket == event_bucket else 0.0


async def hybrid_search_markets_v2(*args, **kwargs):  # pragma: no cover
    raise NotImplementedError("hybrid_search_markets_v2 is implemented in task 5")
```

- [ ] **Step 4: Run tests — expect pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_hybrid_search_v2.py -v`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/retrieval/hybrid_search_v2.py tests/unit/test_hybrid_search_v2.py
git commit -m "feat(ranking): date_proximity + bucket_match pure helpers"
```

---

## Task 5: `hybrid_search_v2` — main function + v1-equivalence test + DB integration test

**Files:**
- Modify: `app/retrieval/hybrid_search_v2.py`
- Modify: `tests/unit/test_hybrid_search_v2.py`
- Modify: `app/retrieval/__init__.py`
- Create: `tests/integration/test_hybrid_search_v2_db.py`

- [ ] **Step 1: Extend unit tests with v1-equivalence and formula checks**

Append to `tests/unit/test_hybrid_search_v2.py`:

```python
# ═══════════════════ hybrid_search_markets_v2 ═══════════════════

from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def _fake_vector_rows():
    """Two candidate markets: m1 scores higher cosine, m2 ends sooner."""
    return [
        {
            "market_id": "m1",
            "question": "Will Macron survive 2026?",
            "category": "politics",
            "end_date": _utc(2026, 12, 31),
            "liquidity": 1000, "volume_24h": 100,
            "best_bid": 0.5, "best_ask": 0.52, "spread": 0.02, "last_trade_price": 0.51,
            "market_retrieval_text": "macron survive 2026",
            "cosine_score": 0.80,
            "bucket": "politics",
        },
        {
            "market_id": "m2",
            "question": "Will France pass law X?",
            "category": "politics",
            "end_date": _utc(2026, 5, 1),  # ends soon
            "liquidity": 500, "volume_24h": 50,
            "best_bid": 0.3, "best_ask": 0.33, "spread": 0.03, "last_trade_price": 0.31,
            "market_retrieval_text": "france law x",
            "cosine_score": 0.70,
            "bucket": "politics",
        },
    ]


@pytest.mark.asyncio
async def test_v2_equivalence_when_w_date_and_w_bucket_zero(monkeypatch, _fake_vector_rows):
    """When w_date = w_bucket = 0, v2 must rank identically to v1 on a shared pool."""
    # Both variants see the same vector pool.
    monkeypatch.setattr(
        "app.retrieval.vector_retriever.search_markets_by_embedding",
        AsyncMock(return_value=_fake_vector_rows),
    )
    get_settings_cache_clear = _clear_settings()

    from app.retrieval.hybrid_search import hybrid_search_markets as v1
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2 as v2
    session = MagicMock()
    v1_out = await v1(session, [0.0] * 1536, "macron france 2026",
                     event_bucket="politics", event_entities=["Macron"])
    v2_out = await v2(session, [0.0] * 1536, "macron france 2026",
                     event_bucket="politics", event_entities=["Macron"],
                     event_last_seen=_utc(2026, 4, 25))

    assert [r["market_id"] for r in v1_out] == [r["market_id"] for r in v2_out], (
        f"v1 order {[r['market_id'] for r in v1_out]} != v2 order {[r['market_id'] for r in v2_out]}"
    )


@pytest.mark.asyncio
async def test_v2_date_proximity_flips_tie(monkeypatch, _fake_vector_rows):
    """With equal vector ranks and w_date=1.0, the nearer-end-date market wins."""
    # Force equal cosine so RRF is a pure tiebreak by date.
    rows = [dict(r, cosine_score=0.75) for r in _fake_vector_rows]
    monkeypatch.setattr(
        "app.retrieval.vector_retriever.search_markets_by_embedding",
        AsyncMock(return_value=rows),
    )
    _clear_settings()
    monkeypatch_setenv_w_date_1 = patch.dict(
        "os.environ", {"RANKING_V2_W_DATE": "1.0", "RANKING_V2_W_BUCKET": "0.0"}
    )
    with monkeypatch_setenv_w_date_1:
        from app.core.config import get_settings as gs
        gs.cache_clear()
        from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
        out = await hybrid_search_markets_v2(
            MagicMock(), [0.0] * 1536, "france politics",
            event_bucket="politics", event_entities=["France"],
            event_last_seen=_utc(2026, 4, 25),
        )
    assert out[0]["market_id"] == "m2", "expected the nearer-end-date market (m2) to rank first"


def _clear_settings():
    from app.core.config import get_settings
    get_settings.cache_clear()
```

- [ ] **Step 2: Run tests — expect failures**

Run: `docker compose exec -T app python -m pytest tests/unit/test_hybrid_search_v2.py -v`
Expected: the 10 previous tests pass, the 2 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Implement `hybrid_search_markets_v2`**

Replace the stub in `app/retrieval/hybrid_search_v2.py` (keep the helpers above it intact):

```python
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.retrieval.bm25_index import BM25Index
from app.retrieval.vector_retriever import search_markets_by_embedding

logger = logging.getLogger(__name__)


def _count_entity_matches(question: str, entities: list[str]) -> int:
    if not question or not entities:
        return 0
    q_lower = question.lower()
    matches = 0
    for ent in entities:
        if len(ent) < 2:
            continue
        if re.search(r"\b" + re.escape(ent.lower()) + r"\b", q_lower):
            matches += 1
    return matches


async def hybrid_search_markets_v2(
    session: AsyncSession,
    event_embedding: list[float],
    event_text: str,
    top_k: Optional[int] = None,
    event_bucket: Optional[str] = None,
    event_entities: Optional[list[str]] = None,
    event_last_seen: Optional[datetime] = None,
) -> list[dict]:
    """Run hybrid search v2:
      RRF(vec, bm25) + w_entity*entity_matches
                     + w_date*date_proximity
                     + w_bucket*bucket_match
    """
    settings = get_settings()
    k = top_k or settings.top_k_markets
    rrf_k = settings.ranking_v2_rrf_k
    w_entity = settings.ranking_v2_w_entity
    w_date = settings.ranking_v2_w_date
    w_bucket = settings.ranking_v2_w_bucket
    tau_days = settings.ranking_v2_tau_days

    vector_results = await search_markets_by_embedding(
        session, event_embedding, limit=k * 3,
    )
    if not vector_results:
        logger.info("hybrid_search_v2: empty vector pool")
        return []

    bm25 = BM25Index()
    bm25.build_index(vector_results, text_field="market_retrieval_text")
    bm25_results = bm25.search(event_text, limit=k * 3)

    vec_rank = {r["market_id"]: i for i, r in enumerate(vector_results)}
    bm25_rank: dict[str, int] = {}
    bm25_score_map: dict[str, float] = {}
    for r in bm25_results:
        mid = r.get("market_id")
        if mid:
            bm25_rank[mid] = r.get("bm25_rank", len(bm25_results)) - 1
            bm25_score_map[mid] = r.get("bm25_score", 0.0)

    all_ids = set(vec_rank.keys()) | set(bm25_rank.keys())
    market_map = {r["market_id"]: r for r in vector_results}
    entities = event_entities or []

    fused: list[dict] = []
    for mid in all_ids:
        vr = vec_rank.get(mid, k * 3)
        br = bm25_rank.get(mid, k * 3)
        rrf_score = (1.0 / (rrf_k + vr + 1)) + (1.0 / (rrf_k + br + 1))

        entry = market_map.get(mid, {}).copy()
        entry["market_id"] = mid
        entry["bm25_score"] = bm25_score_map.get(mid, 0.0)

        question = entry.get("question") or ""
        n_ent = _count_entity_matches(question, entities)
        if n_ent > 0:
            rrf_score += n_ent * w_entity
            entry["entity_matches"] = n_ent

        # date proximity — requires event_last_seen to be meaningful
        if event_last_seen is not None and w_date > 0:
            from app.retrieval.hybrid_search_v2 import date_proximity
            dp = date_proximity(entry.get("end_date"), event_last_seen, tau_days)
            if dp > 0:
                rrf_score += dp * w_date
                entry["date_proximity"] = dp

        # bucket match
        if w_bucket > 0:
            from app.retrieval.hybrid_search_v2 import bucket_match
            mkt_bucket = entry.get("bucket")
            bm = bucket_match(mkt_bucket, event_bucket)
            if bm > 0:
                rrf_score += bm * w_bucket
                entry["bucket_match"] = True

        entry["rrf_score"] = round(rrf_score, 6)
        fused.append(entry)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    for i, entry in enumerate(fused[:k]):
        entry["rank"] = i + 1

    logger.info("hybrid_search_v2: %d candidates → top %d", len(fused), k)
    return fused[:k]
```

Note: `vector_retriever.search_markets_by_embedding` does not currently select `bucket`. Task 5 step 4 fixes that.

- [ ] **Step 4: Add `bucket` to the raw-SQL vector retriever**

In `app/retrieval/vector_retriever.py`, find the SELECT inside `search_markets_by_embedding` and add `bucket,` alongside the existing columns; add it to the returned dict. Exact patch:

```python
# app/retrieval/vector_retriever.py — inside the `text(f"""SELECT …""")` block
# ADD `bucket,` between `category,` and `end_date,`:
                    category,
                    bucket,
                    end_date,
```

and in the dict-comprehension build-up:

```python
        return [
            {
                "market_id": r[0],
                "question": r[1],
                "category": r[2],
                "bucket": r[3],
                "end_date": r[4],
                "liquidity": r[5],
                "volume_24h": r[6],
                "best_bid": r[7],
                "best_ask": r[8],
                "spread": r[9],
                "last_trade_price": r[10],
                "market_retrieval_text": r[11],
                "cosine_score": float(r[12]) if r[12] else 0.0,
            }
            for r in rows
        ]
```

The v1 `hybrid_search.py` does not read `bucket` from the row dict today, so this change is additive and does not alter v1 behaviour.

- [ ] **Step 5: Expose the dispatcher from `app/retrieval/__init__.py`**

Overwrite `app/retrieval/__init__.py` with:

```python
"""Retrieval package. Prefer `hybrid_search_markets` (the dispatcher) over
importing v1 / v2 directly."""

from app.retrieval.ranking_variant import hybrid_search_markets_dispatch as hybrid_search_markets

__all__ = ["hybrid_search_markets"]
```

(If `__init__.py` already exists with content, prepend these lines and keep existing exports intact.)

- [ ] **Step 6: Write the integration test**

```python
# tests/integration/test_hybrid_search_v2_db.py
"""End-to-end: dispatcher routes v1 and v2 against a real DB."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import Market


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dispatcher_routes_by_flag(async_db_factory, monkeypatch):
    """Same input, different variants → both return a list of dicts with rank."""
    # Seed 3 markets.
    async with async_db_factory() as s:
        for i, mid in enumerate(("m_alpha", "m_beta", "m_gamma")):
            s.add(Market(
                market_id=mid, question=f"Will {mid} win?",
                category="politics", bucket="politics",
                end_date=datetime(2026, 5, 15 + i, tzinfo=timezone.utc),
                active=True, closed=False, accepting_orders=True,
                embedding=[0.1] * 1536,
                market_retrieval_text=f"test text {mid}",
            ))
        await s.commit()

    try:
        from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
        async with async_db_factory() as s:
            # v1 path
            monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v1")
            get_settings.cache_clear()
            r1 = await hybrid_search_markets_dispatch(
                s, [0.1] * 1536, "will win", top_k=3,
                event_bucket="politics", event_entities=["alpha"],
                event_last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            )
            assert r1 and all("rank" in row for row in r1)

            # v2 path
            monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
            get_settings.cache_clear()
            r2 = await hybrid_search_markets_dispatch(
                s, [0.1] * 1536, "will win", top_k=3,
                event_bucket="politics", event_entities=["alpha"],
                event_last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            )
            assert r2 and all("rank" in row for row in r2)
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Market).where(Market.market_id.in_(
                ("m_alpha", "m_beta", "m_gamma")
            )))
            await s.commit()
```

- [ ] **Step 7: Run all new tests**

Run: `docker compose exec -T app python -m pytest tests/unit/test_hybrid_search_v2.py tests/integration/test_hybrid_search_v2_db.py -v`
Expected: 12 unit + 1 integration = 13 passed.

- [ ] **Step 8: Commit**

```bash
git add app/retrieval/hybrid_search_v2.py app/retrieval/vector_retriever.py app/retrieval/__init__.py tests/unit/test_hybrid_search_v2.py tests/integration/test_hybrid_search_v2_db.py
git commit -m "feat(ranking): hybrid_search_markets_v2 + dispatcher wiring"
```

---

## Task 6: Route the prod call-site through the dispatcher

**Files:**
- Modify: `app/workers/tasks_scoring.py:55` (the `from … import hybrid_search_markets` line)

No behaviour change: `ranking_variant_event_to_market` defaults to `v1`, so production still executes v1. This task only swaps the **import source** so the flag can later flip behaviour without code changes.

- [ ] **Step 1: Update the import in `tasks_scoring.py`**

Replace line 55:

```python
    from app.retrieval.hybrid_search import hybrid_search_markets
```

with:

```python
    from app.retrieval import hybrid_search_markets  # dispatcher (v1 by default)
```

Also update the call at line 116 to pass the event timestamp (needed by v2; ignored by v1):

```python
        candidates = await hybrid_search_markets(
            session, embedding, event_text,
            event_bucket=event.bucket,
            event_entities=event.key_entities,
            event_last_seen=event.last_seen,
        )
```

The v1 implementation accepts arbitrary `**kwargs`… **actually it does not** (the v1 signature in `hybrid_search.py` has no `**kwargs` catch). Adjust the dispatcher **to strip v1-unknown kwargs before delegating**:

Edit `app/retrieval/ranking_variant.py::hybrid_search_markets_dispatch`:

```python
    if variant == "v2":
        from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
        return await hybrid_search_markets_v2(
            session, event_embedding, event_text,
            top_k=top_k,
            event_bucket=event_bucket,
            event_entities=event_entities,
            event_last_seen=event_last_seen,
        )
    from app.retrieval.hybrid_search import hybrid_search_markets
    return await hybrid_search_markets(
        session, event_embedding, event_text,
        top_k=top_k,
        event_bucket=event_bucket,
        event_entities=event_entities,
        # Note: v1 ignores event_last_seen; we drop it here.
    )
```

(The signature of v1's `hybrid_search_markets` is `(session, event_embedding, event_text, top_k=None, event_bucket=None, event_entities=None)` — see `app/retrieval/hybrid_search.py:32`. Keep the drop explicit in the dispatcher, not the caller.)

- [ ] **Step 2: Run the full regression suite**

Run: `docker compose exec -T app python -m pytest tests/ -x -q`
Expected: all previously-green tests remain green (~239 + the 13 new ones from tasks 3-5 = 252 passed).

- [ ] **Step 3: Commit**

```bash
git add app/workers/tasks_scoring.py app/retrieval/ranking_variant.py
git commit -m "refactor(ranking): route tasks_scoring through the dispatcher"
```

---

## Task 7: `labels_event_market.py` — dataclass + JSONL loader

**Files:**
- Create: `app/eval/labels_event_market.py`
- Create: `tests/unit/test_labels_event_market.py`
- Create: `docs/eval_labels/.gitkeep`

This task ships only the dataclass + pure-file-IO loader. The LLM-judge runner comes in task 10; the seed CLI uses the same format (task 8 writes, this task reads).

- [ ] **Step 1: Write unit tests**

```python
# tests/unit/test_labels_event_market.py
"""Tests for labels_event_market loader + adapter."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def _write_jsonl(lines: list[dict]) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for line in lines:
        f.write(json.dumps(line) + "\n")
    f.flush()
    return Path(f.name)


def test_load_event_market_labels_parses_strong_and_weak():
    from app.eval.labels_event_market import load_event_market_labels
    path = _write_jsonl([
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match", "source": "human"},
        {"event_id": 1, "market_id": "m2", "verdict": "weak_match", "source": "human"},
        {"event_id": 1, "market_id": "m3", "verdict": "not_related", "source": "human"},
        {"event_id": 2, "market_id": "m1", "verdict": "strong_match", "source": "llm_calibrated"},
    ])
    pairs = load_event_market_labels(path)
    # Pair for event 1 has 2 relevant (strong + weak), not including not_related.
    by_eid = {p.query_id: p for p in pairs}
    assert by_eid[1].relevant_ids == frozenset({"m1", "m2"})
    assert by_eid[1].surface == "event_to_market"
    assert by_eid[1].gains == {"m1": 1.0, "m2": 0.5}
    assert by_eid[2].relevant_ids == frozenset({"m1"})
    assert by_eid[2].gains == {"m1": 1.0}


def test_load_event_market_labels_skips_malformed_lines():
    from app.eval.labels_event_market import load_event_market_labels
    path = _write_jsonl([
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match", "source": "human"},
    ])
    # Append a malformed line manually.
    with path.open("a") as f:
        f.write("not json at all\n")
    pairs = load_event_market_labels(path)
    assert len(pairs) == 1


def test_load_event_market_labels_missing_file_returns_empty():
    from app.eval.labels_event_market import load_event_market_labels
    pairs = load_event_market_labels(Path("/tmp/does_not_exist_chantier4.jsonl"))
    assert pairs == []


def test_weak_match_gain_is_half():
    """Documented convention: weak = 0.5, strong = 1.0."""
    from app.eval.labels_event_market import WEAK_MATCH_GAIN, STRONG_MATCH_GAIN
    assert WEAK_MATCH_GAIN == 0.5
    assert STRONG_MATCH_GAIN == 1.0
```

- [ ] **Step 2: Run tests — expect failures**

Run: `docker compose exec -T app python -m pytest tests/unit/test_labels_event_market.py -v`
Expected: 4 failures with `ModuleNotFoundError: No module named 'app.eval.labels_event_market'`.

- [ ] **Step 3: Implement the loader**

```python
# app/eval/labels_event_market.py
"""Ground-truth labels for the event→market retrieval surface (chantier #4).

Two-stage pipeline:
  1. Human seed CLI (scripts/label_event_market_seed.py) writes a JSONL file
     where each line is {"event_id", "market_id", "verdict", "source": "human"}.
  2. LLM-judge runner (this module, task 10) writes additional lines with
     "source": "llm_calibrated".

Readers of the merged file get a list of `EventMarketPair` objects compatible
with the chantier #3 runner via the `.query_id` / `.relevant_ids` / `.surface`
attributes. `gains` is extra metadata used by graded-nDCG computation (task 13).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

STRONG_MATCH_GAIN: float = 1.0
WEAK_MATCH_GAIN: float = 0.5


@dataclass(frozen=True)
class EventMarketPair:
    query_id: int
    relevant_ids: frozenset[str]
    gains: dict[str, float]      # market_id → gain (0.5 or 1.0)
    source: str                  # "human" | "llm_calibrated"
    surface: str = "event_to_market"


def _verdict_to_gain(verdict: str) -> float | None:
    if verdict == "strong_match":
        return STRONG_MATCH_GAIN
    if verdict == "weak_match":
        return WEAK_MATCH_GAIN
    return None  # not_related or unknown → skip


def load_event_market_labels(path: Path) -> list[EventMarketPair]:
    """Parse a JSONL file of labelled event→market pairs.

    Malformed lines are skipped with a warning. Missing files return [].
    Lines with the same `event_id` are merged into a single EventMarketPair;
    `source` is the *noblest* among lines (human > llm_calibrated).
    """
    if not path.exists():
        logger.info("load_event_market_labels: file not found %s", path)
        return []

    # event_id → {market_id: (gain, source)}
    accum: dict[int, dict[str, tuple[float, str]]] = {}

    nobility = {"human": 2, "llm_calibrated": 1}

    with path.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("load_event_market_labels: skip malformed line %d", lineno)
                continue
            try:
                eid = int(row["event_id"])
                mid = str(row["market_id"])
                verdict = str(row["verdict"])
                src = str(row.get("source", "human"))
            except (KeyError, TypeError, ValueError):
                logger.warning("load_event_market_labels: skip line %d (missing fields)", lineno)
                continue
            gain = _verdict_to_gain(verdict)
            if gain is None:
                continue
            src_level = nobility.get(src, 0)
            bucket = accum.setdefault(eid, {})
            existing = bucket.get(mid)
            if existing is None or nobility.get(existing[1], 0) < src_level:
                bucket[mid] = (gain, src)

    pairs: list[EventMarketPair] = []
    for eid, market_map in accum.items():
        # Source for the pair = noblest source of any positive market
        max_src = max(market_map.values(), key=lambda t: nobility.get(t[1], 0))[1]
        pairs.append(EventMarketPair(
            query_id=eid,
            relevant_ids=frozenset(market_map.keys()),
            gains={mid: g for mid, (g, _src) in market_map.items()},
            source=max_src,
        ))
    return pairs
```

- [ ] **Step 4: Create the eval_labels directory placeholder**

Run: `mkdir -p docs/eval_labels && touch docs/eval_labels/.gitkeep`

- [ ] **Step 5: Run tests — expect pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_labels_event_market.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add app/eval/labels_event_market.py tests/unit/test_labels_event_market.py docs/eval_labels/.gitkeep
git commit -m "feat(eval): labels_event_market — dataclass + JSONL loader"
```

---

## Task 8: Human seed CLI — candidate generation

**Files:**
- Create: `scripts/label_event_market_seed.py` (first half — candidate sampler only)

This task ships the candidate-sampling half. The interactive review loop lands in task 9 to keep the two concerns separable and testable.

- [ ] **Step 1: Write the candidate sampler script**

```python
# scripts/label_event_market_seed.py
"""Human-review CLI for event→market ground-truth labels (chantier #4).

Two phases:
  1. sample — emit 500 (event_id, market_id) candidate pairs, stratified by
     bucket + rank bucket, to a staging JSONL.
  2. review — interactive terminal loop to accept/reject/edit each pair.

Usage:
    python -m scripts.label_event_market_seed sample --out docs/eval_labels/seed_candidates.jsonl
    python -m scripts.label_event_market_seed review \\
        --candidates docs/eval_labels/seed_candidates.jsonl \\
        --out docs/eval_labels/event_market_seed_2026-04-25.jsonl

The review phase is implemented in task 9. This task ships only `sample`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event, Market

logger = logging.getLogger(__name__)


BUCKETS = ("politics", "crypto", "sports", "tech", "other")
N_EVENTS_PER_BUCKET = 20
# From each event × top-20, we sample:
#   rank 1-3:   pick 1 per event  → ~ N_EVENTS (5×20 = 100)
#   rank 4-10:  pick 1 per event  → ~ 100
#   rank 11-20: pick 1 per event  → ~ 100
#   hors-top-20: pick 2 random markets in same bucket, not in top-20
#                                 → ~ 200
# Totals to ~500 candidates.
RANDOM_SEED = 42


async def _sample_events(session, bucket: str, n: int) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.bucket == bucket)
        .where(Event.embedding.isnot(None))
        .order_by(Event.last_seen.desc())
        .limit(n * 3)  # over-sample to allow filtering below
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows[:n]


async def _top20_for_event(session, event: Event) -> list[dict]:
    """Call the prod dispatcher (v1) to get top-20 candidates. We import
    here — not at module top — to avoid pulling Celery at script-parse time."""
    from app.retrieval import hybrid_search_markets
    emb = event.embedding
    if emb is None:
        return []
    text = event.event_retrieval_text or event.event_title
    return await hybrid_search_markets(
        session, list(emb), text, top_k=20,
        event_bucket=event.bucket, event_entities=event.key_entities,
        event_last_seen=event.last_seen,
    )


async def _random_out_of_top20(session, bucket: str, excluded: set[str], n: int) -> list[str]:
    stmt = (
        select(Market.market_id)
        .where(Market.bucket == bucket)
        .where(Market.active.is_(True))
        .where(Market.closed.is_(False))
    )
    rows = [r[0] for r in (await session.execute(stmt)).all() if r[0] not in excluded]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(rows)
    return rows[:n]


async def _cmd_sample(out_path: Path) -> int:
    factory = get_session_factory()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w") as f:
        async with factory() as session:
            for bucket in BUCKETS:
                events = await _sample_events(session, bucket, N_EVENTS_PER_BUCKET)
                if not events:
                    logger.warning("sample: bucket=%s has 0 events, skipping", bucket)
                    continue
                for ev in events:
                    candidates = await _top20_for_event(session, ev)
                    if not candidates:
                        continue
                    top20_ids = {c["market_id"] for c in candidates}
                    # Stratified pick from top-20.
                    slices = (
                        [c for c in candidates if 1 <= c.get("rank", 999) <= 3],
                        [c for c in candidates if 4 <= c.get("rank", 999) <= 10],
                        [c for c in candidates if 11 <= c.get("rank", 999) <= 20],
                    )
                    for sl in slices:
                        if sl:
                            pick = sl[0]
                            f.write(json.dumps({
                                "event_id": ev.id,
                                "market_id": pick["market_id"],
                                "event_title": ev.event_title,
                                "event_bucket": ev.bucket,
                                "market_question": pick.get("question"),
                                "rank_in_v1": pick.get("rank"),
                                "cosine_score": pick.get("cosine_score"),
                                "rrf_score": pick.get("rrf_score"),
                                "end_date": (
                                    pick.get("end_date").isoformat()
                                    if pick.get("end_date") else None
                                ),
                                "stratum": "top20",
                            }) + "\n")
                            written += 1
                    # Hors-top-20 random picks.
                    extras = await _random_out_of_top20(session, bucket, top20_ids, n=2)
                    for mid in extras:
                        mkt = (await session.execute(
                            select(Market).where(Market.market_id == mid)
                        )).scalar_one_or_none()
                        if mkt is None:
                            continue
                        f.write(json.dumps({
                            "event_id": ev.id,
                            "market_id": mid,
                            "event_title": ev.event_title,
                            "event_bucket": ev.bucket,
                            "market_question": mkt.question,
                            "rank_in_v1": None,
                            "cosine_score": None,
                            "rrf_score": None,
                            "end_date": mkt.end_date.isoformat() if mkt.end_date else None,
                            "stratum": "hors_top20",
                        }) + "\n")
                        written += 1
    logger.info("sample: wrote %d candidates → %s", written, out_path)
    return written


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="label_event_market_seed")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("review")
    r.add_argument("--candidates", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "sample":
        n = asyncio.run(_cmd_sample(args.out))
        print(f"wrote {n} candidates to {args.out}")
        return 0
    if args.cmd == "review":
        print("review command is implemented in task 9")
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-check the script parses and `sample` emits something**

The sample phase hits the live DB, so on a fresh / empty dev DB it will print 0. That's fine for this step — we only verify the import chain and CLI wiring work.

Run: `docker compose exec -T app python -m scripts.label_event_market_seed --help`
Expected: `usage: label_event_market_seed [-h] {sample,review} ...`

Run: `docker compose exec -T app python -m scripts.label_event_market_seed sample --out /tmp/seed_candidates.jsonl`
Expected: exit code 0, a line like `wrote N candidates to /tmp/seed_candidates.jsonl` (N may be 0 if DB is empty).

- [ ] **Step 3: Commit**

```bash
git add scripts/label_event_market_seed.py
git commit -m "feat(ranking): label_event_market_seed — sample phase"
```

---

## Task 9: Human seed CLI — review phase

**Files:**
- Modify: `scripts/label_event_market_seed.py` (add `_cmd_review`)

- [ ] **Step 1: Add the review command**

Replace the `if args.cmd == "review": print("review command is implemented in task 9") …` branch with a real call. Append this function above `_parse_args`:

```python
VALID_VERDICTS = {
    "s": "strong_match",
    "w": "weak_match",
    "n": "not_related",
}


def _cmd_review(candidates_path: Path, out_path: Path) -> int:
    """Interactive loop: read candidates JSONL, ask the user for each, write
    a labels JSONL idempotently. Resume-safe: if `out_path` already contains
    labels for a (event_id, market_id) pair, skip that candidate."""
    if not candidates_path.exists():
        print(f"error: candidates file not found: {candidates_path}")
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    already: set[tuple[int, str]] = set()
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    already.add((int(row["event_id"]), str(row["market_id"])))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    print(f"resuming — {len(already)} pairs already labelled in {out_path}")

    with candidates_path.open() as src, out_path.open("a") as dst:
        todo = [json.loads(line) for line in src if line.strip()]
        total = len(todo)
        done = 0
        skipped = 0
        for i, cand in enumerate(todo, start=1):
            key = (int(cand["event_id"]), str(cand["market_id"]))
            if key in already:
                skipped += 1
                continue
            prompt = (
                f"[{i}/{total}] event: {cand.get('event_title')!r} (bucket={cand.get('event_bucket')})\n"
                f"         market: {cand.get('market_question')!r}\n"
                f"         cosine={cand.get('cosine_score')}, rank={cand.get('rank_in_v1')}, "
                f"stratum={cand.get('stratum')}, end_date={cand.get('end_date')}\n"
                "(s)trong / (w)eak / (n)ot_related / (k)skip / (q)uit&save > "
            )
            try:
                ans = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\naborted — partial progress saved.")
                break
            if ans == "q":
                break
            if ans == "k":
                continue
            verdict = VALID_VERDICTS.get(ans)
            if verdict is None:
                print(f"  unknown input {ans!r}, skipping")
                continue
            dst.write(json.dumps({
                "event_id": key[0],
                "market_id": key[1],
                "verdict": verdict,
                "source": "human",
            }) + "\n")
            dst.flush()
            done += 1
        print(f"done — labelled {done}, skipped {skipped}, remaining {total - done - skipped - len(already)}")
    return 0
```

Then wire it up in `main`:

```python
    if args.cmd == "review":
        return _cmd_review(args.candidates, args.out)
```

- [ ] **Step 2: Smoke-test with a tiny fake candidates file (piped input)**

Run:
```bash
cat > /tmp/fake_cands.jsonl <<EOF
{"event_id": 1, "market_id": "m1", "event_title": "T1", "event_bucket": "politics", "market_question": "Q1"}
{"event_id": 1, "market_id": "m2", "event_title": "T1", "event_bucket": "politics", "market_question": "Q2"}
EOF
printf "s\nn\n" | docker compose exec -T app python -m scripts.label_event_market_seed review --candidates /tmp/fake_cands.jsonl --out /tmp/fake_labels.jsonl
cat /tmp/fake_labels.jsonl
```
Expected: two lines in `/tmp/fake_labels.jsonl`, verdicts `strong_match` then `not_related`.

- [ ] **Step 3: Smoke-test resume — second run with same out file labels nothing**

Run: `printf "s\n" | docker compose exec -T app python -m scripts.label_event_market_seed review --candidates /tmp/fake_cands.jsonl --out /tmp/fake_labels.jsonl`
Expected: message `resuming — 2 pairs already labelled in /tmp/fake_labels.jsonl` and no new rows appended.

- [ ] **Step 4: Commit**

```bash
git add scripts/label_event_market_seed.py
git commit -m "feat(ranking): label_event_market_seed — review phase (resume-safe)"
```

---

## Task 10: LLM-judge — calibrated batch prompt + agreement check

**Files:**
- Modify: `app/eval/labels_event_market.py` (add `judge_pairs_llm` + `compute_agreement`)
- Modify: `tests/unit/test_labels_event_market.py` (add tests)

- [ ] **Step 1: Write the unit tests**

Append to `tests/unit/test_labels_event_market.py`:

```python
# ═══════════ LLM-judge ═══════════

@pytest.mark.asyncio
async def test_judge_pairs_llm_uses_injected_callable(tmp_path):
    """The judge delegates LLM calls to an injectable callable, for test isolation."""
    from app.eval.labels_event_market import judge_pairs_llm
    captured: list[dict] = []

    async def fake_call(prompt: str) -> list[dict]:
        captured.append({"prompt_len": len(prompt)})
        return [
            {"market_id": "m1", "verdict": "strong_match", "reason": "exact topic"},
            {"market_id": "m2", "verdict": "not_related", "reason": "different topic"},
        ]

    out = await judge_pairs_llm(
        event={
            "event_id": 1,
            "title": "Test event",
            "summary": "",
            "bucket": "politics",
            "entities": ["A"],
        },
        markets=[
            {"market_id": "m1", "question": "Q1", "category": "politics", "end_date": None},
            {"market_id": "m2", "question": "Q2", "category": "sports", "end_date": None},
        ],
        few_shot=[],
        call_fn=fake_call,
        cache_path=tmp_path / "cache.json",
    )
    assert {r["market_id"]: r["verdict"] for r in out} == {
        "m1": "strong_match", "m2": "not_related",
    }
    assert len(captured) == 1  # batched — 1 LLM call for 2 markets


@pytest.mark.asyncio
async def test_judge_pairs_llm_cache_hit_skips_call(tmp_path):
    """A cache hit on the (event_id, market_ids) key bypasses call_fn."""
    from app.eval.labels_event_market import judge_pairs_llm
    cache_path = tmp_path / "cache.json"
    # Prime cache.
    cache_path.write_text(json.dumps({
        "1::m1,m2": [
            {"market_id": "m1", "verdict": "weak_match"},
            {"market_id": "m2", "verdict": "not_related"},
        ]
    }))

    async def fake_call(prompt: str):
        raise AssertionError("should not call LLM on cache hit")

    out = await judge_pairs_llm(
        event={"event_id": 1, "title": "t", "summary": "", "bucket": "politics", "entities": []},
        markets=[
            {"market_id": "m1", "question": "Q1", "category": "politics", "end_date": None},
            {"market_id": "m2", "question": "Q2", "category": "sports", "end_date": None},
        ],
        few_shot=[],
        call_fn=fake_call,
        cache_path=cache_path,
    )
    assert out[0]["verdict"] == "weak_match"


def test_compute_agreement_perfect_match():
    from app.eval.labels_event_market import compute_agreement
    human = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    llm = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    assert compute_agreement(human=human, llm=llm) == 1.0


def test_compute_agreement_partial():
    from app.eval.labels_event_market import compute_agreement
    human = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "weak_match"},
        {"event_id": 1, "market_id": "m3", "verdict": "not_related"},
    ]
    llm = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "not_related"},  # miss
        {"event_id": 1, "market_id": "m3", "verdict": "not_related"},
    ]
    assert compute_agreement(human=human, llm=llm) == pytest.approx(2 / 3)


def test_compute_agreement_missing_llm_row_counts_as_disagreement():
    from app.eval.labels_event_market import compute_agreement
    human = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "strong_match"},
    ]
    llm = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    # 1 of 2 agree.
    assert compute_agreement(human=human, llm=llm) == pytest.approx(0.5)
```

- [ ] **Step 2: Run tests — expect failures**

Run: `docker compose exec -T app python -m pytest tests/unit/test_labels_event_market.py -v`
Expected: 5 new tests fail with `ImportError: cannot import name 'judge_pairs_llm'`.

- [ ] **Step 3: Implement `judge_pairs_llm` + `compute_agreement`**

Append to `app/eval/labels_event_market.py`:

```python
# ══════════════════════════════════════════════════════════════════════
# LLM-judge runner (chantier #4 task 10)
# ══════════════════════════════════════════════════════════════════════
import hashlib
from typing import Awaitable, Callable

JUDGE_MODEL = "gpt-4o-mini"
# Rough: one batched call = ~1200 input + 400 output tokens on gpt-4o-mini
# → ~$0.00024 per call at current prices. Used only for the local budget check.
_APPROX_COST_PER_BATCH_USD = 0.0003


def _judge_cache_key(event_id: int, market_ids: list[str]) -> str:
    mids = ",".join(sorted(market_ids))
    return f"{event_id}::{mids}"


def _build_judge_prompt(
    event: dict, markets: list[dict], few_shot: list[dict]
) -> str:
    """Prompt the LLM to return a strict JSON array."""
    lines = [
        "You judge relevance between a news event and a set of prediction markets.",
        "For each market, output one of: strong_match, weak_match, not_related.",
        "",
        "Definitions:",
        "  strong_match: the market directly bets on this event's core claim.",
        "  weak_match:  the market is in the same topic but does not directly resolve on the event.",
        "  not_related: the market has no meaningful topical overlap.",
        "",
    ]
    if few_shot:
        lines.append("# Examples")
        for ex in few_shot:
            lines.append(f"event: {ex['event_title']}")
            lines.append(f"market: {ex['market_question']}")
            lines.append(f"verdict: {ex['verdict']}")
            lines.append("")
    lines.append("# Now judge the following.")
    lines.append(f"event_id: {event['event_id']}")
    lines.append(f"event_title: {event['title']}")
    lines.append(f"event_bucket: {event.get('bucket')}")
    lines.append(f"event_entities: {event.get('entities', [])}")
    if event.get("summary"):
        lines.append(f"event_summary: {event['summary'][:800]}")
    lines.append("")
    lines.append("markets:")
    for m in markets:
        lines.append(
            f"  - market_id: {m['market_id']}"
            f" | question: {m.get('question')}"
            f" | category: {m.get('category')}"
            f" | end_date: {m.get('end_date')}"
        )
    lines.append("")
    lines.append(
        'Return a JSON array with one object per market: '
        '[{"market_id": ..., "verdict": ..., "reason": ...}, ...]. '
        "No surrounding prose."
    )
    return "\n".join(lines)


async def judge_pairs_llm(
    *,
    event: dict,
    markets: list[dict],
    few_shot: list[dict],
    call_fn: Callable[[str], Awaitable[list[dict]]],
    cache_path: Path,
) -> list[dict]:
    """Judge each (event, market) pair. Batched: one LLM call per event.

    `call_fn` takes a prompt string and returns the parsed JSON array. Tests
    inject a fake; production uses `openai_judge_call` below.

    Cache: keyed by (event_id, sorted market_ids). Cache file survives runs.
    """
    cache: dict[str, list[dict]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            logger.warning("judge cache corrupt at %s, starting fresh", cache_path)
            cache = {}

    market_ids = [m["market_id"] for m in markets]
    key = _judge_cache_key(int(event["event_id"]), market_ids)
    if key in cache:
        return cache[key]

    prompt = _build_judge_prompt(event, markets, few_shot)
    raw = await call_fn(prompt)

    # Keep only fields we document.
    normalized = [
        {"market_id": r.get("market_id"), "verdict": r.get("verdict"), "reason": r.get("reason", "")}
        for r in raw if r.get("market_id") in set(market_ids)
    ]
    cache[key] = normalized
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))
    return normalized


async def openai_judge_call(prompt: str) -> list[dict]:
    """Production call_fn for judge_pairs_llm. Uses OpenAI structured output."""
    from openai import AsyncOpenAI
    from app.core.config import get_settings
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM judge returned non-JSON: %s", raw[:200])
        return []
    # The response_format=json_object forces a dict; we wrap either a bare
    # list or {"judgments": [...]}. Accept both.
    if isinstance(parsed, dict) and "judgments" in parsed:
        return list(parsed["judgments"])
    if isinstance(parsed, list):
        return parsed
    return []


def compute_agreement(*, human: list[dict], llm: list[dict]) -> float:
    """Fraction of (event_id, market_id) pairs where human and LLM verdicts match.

    Pairs present in human but missing from llm count as disagreements.
    Pairs present in llm but missing from human are ignored.
    """
    if not human:
        return 0.0
    llm_map = {(int(r["event_id"]), str(r["market_id"])): r["verdict"] for r in llm}
    agree = 0
    for h in human:
        key = (int(h["event_id"]), str(h["market_id"]))
        if llm_map.get(key) == h["verdict"]:
            agree += 1
    return agree / len(human)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_labels_event_market.py -v`
Expected: `9 passed` (4 from task 7 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add app/eval/labels_event_market.py tests/unit/test_labels_event_market.py
git commit -m "feat(eval): LLM-judge batch prompt + agreement for event→market"
```

---

## Task 11: Scaling CLI — run LLM-judge against fresh events

**Files:**
- Modify: `scripts/label_event_market_seed.py` (add `scale` subcommand)

- [ ] **Step 1: Add the `scale` subcommand**

Add a new subparser in `_parse_args`:

```python
    sc = sub.add_parser("scale")
    sc.add_argument("--seed", required=True, type=Path,
                    help="Human seed JSONL (used for few-shot).")
    sc.add_argument("--n-events", type=int, default=100,
                    help="Number of fresh events to judge (excludes events in --seed).")
    sc.add_argument("--markets-per-event", type=int, default=10)
    sc.add_argument("--out", required=True, type=Path)
    sc.add_argument("--cache", type=Path, default=Path(".eval_cache/llm_judge_event_market.json"))
    sc.add_argument("--budget-usd", type=float, default=10.0)
```

Add the handler above `_parse_args`:

```python
async def _cmd_scale(
    seed_path: Path, n_events: int, markets_per_event: int,
    out_path: Path, cache_path: Path, budget_usd: float,
) -> int:
    """Run the LLM-judge on `n_events` fresh events (not in seed). Each event
    is judged against its top-`markets_per_event` + a random sample from
    hors-top-k — same stratification as task 8."""
    from app.eval.labels_event_market import (
        judge_pairs_llm, openai_judge_call, _APPROX_COST_PER_BATCH_USD,
    )
    seed_events: set[int] = set()
    if seed_path.exists():
        with seed_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    seed_events.add(int(json.loads(line)["event_id"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    few_shot = _few_shot_from_seed(seed_path)

    factory = get_session_factory()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    batches = 0
    async with factory() as session:
        picked: list[Event] = []
        for bucket in BUCKETS:
            evs = await _sample_events(session, bucket, n_events // len(BUCKETS) + 1)
            for ev in evs:
                if ev.id in seed_events:
                    continue
                picked.append(ev)
                if len(picked) >= n_events:
                    break
            if len(picked) >= n_events:
                break

        with out_path.open("a") as out_f:
            for ev in picked:
                # Estimate cost before calling.
                if batches * _APPROX_COST_PER_BATCH_USD > budget_usd:
                    logger.info("scale: budget exhausted after %d batches", batches)
                    break
                cands = await _top20_for_event(session, ev)
                if not cands:
                    continue
                mkts = cands[:markets_per_event]
                event_dict = {
                    "event_id": ev.id,
                    "title": ev.event_title,
                    "summary": ev.event_summary or "",
                    "bucket": ev.bucket,
                    "entities": list(ev.key_entities or []),
                }
                market_dicts = [{
                    "market_id": c["market_id"],
                    "question": c.get("question"),
                    "category": c.get("category"),
                    "end_date": (
                        c.get("end_date").isoformat()
                        if c.get("end_date") is not None else None
                    ),
                } for c in mkts]
                verdicts = await judge_pairs_llm(
                    event=event_dict,
                    markets=market_dicts,
                    few_shot=few_shot,
                    call_fn=openai_judge_call,
                    cache_path=cache_path,
                )
                batches += 1
                for v in verdicts:
                    out_f.write(json.dumps({
                        "event_id": ev.id,
                        "market_id": v["market_id"],
                        "verdict": v["verdict"],
                        "source": "llm_calibrated",
                    }) + "\n")
                    written += 1
                out_f.flush()
    logger.info("scale: wrote %d verdicts across %d events", written, batches)
    return written


def _few_shot_from_seed(seed_path: Path) -> list[dict]:
    """Return up to 9 few-shot examples (3 per verdict) from the seed file,
    spanning at least 3 buckets when possible. Returns [] if seed is empty."""
    if not seed_path.exists():
        return []
    rows: list[dict] = []
    with seed_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            # The seed file stores verdict; we need event_title + market_question.
            # If the seed rows lack those (task 9 writes only event_id+market_id),
            # we cannot build few-shot this way — punt to empty.
            if "event_title" not in row or "market_question" not in row:
                continue
            rows.append(row)
    by_verdict: dict[str, list[dict]] = {}
    for r in rows:
        by_verdict.setdefault(r["verdict"], []).append(r)
    few: list[dict] = []
    for verdict in ("strong_match", "weak_match", "not_related"):
        few.extend(by_verdict.get(verdict, [])[:3])
    return few[:9]
```

Hook it into `main`:

```python
    if args.cmd == "scale":
        n = asyncio.run(_cmd_scale(
            args.seed, args.n_events, args.markets_per_event,
            args.out, args.cache, args.budget_usd,
        ))
        print(f"wrote {n} labels to {args.out}")
        return 0
```

Because the seed CLI (task 9) currently writes only `{event_id, market_id, verdict, source}` — without `event_title` / `market_question` — `_few_shot_from_seed` will return `[]` on a real run. That is **intentional** for the first cut: the operator runs the scale with few_shot=[] and the agreement check (task 10) catches quality issues. If agreement < 80%, the runbook instructs the operator to enrich the seed file manually with `event_title` and `market_question` fields, then re-run.

Document this behaviour explicitly in a comment at the top of `_cmd_scale`:

```python
    """Run the LLM-judge on `n_events` fresh events (not in seed). […]
    NOTE: few-shot calibration requires the seed file to contain
    `event_title` + `market_question` fields. Task 9 writes only the
    minimum (event_id, market_id, verdict). If the operator wants
    calibrated few-shot, they need to enrich seed rows before running
    `scale`. Empty few-shot is a valid starting point; the agreement
    check (task 10) guards against quality regression.
    """
```

- [ ] **Step 2: Smoke-check the CLI parses**

Run: `docker compose exec -T app python -m scripts.label_event_market_seed scale --help`
Expected: usage line with `--seed`, `--n-events`, `--markets-per-event`, `--out`, `--cache`, `--budget-usd`.

- [ ] **Step 3: Commit**

```bash
git add scripts/label_event_market_seed.py
git commit -m "feat(ranking): label_event_market_seed scale subcommand (LLM-judge batch)"
```

---

## Task 12: Tune CLI — coordinate descent (offline tuning)

**Files:**
- Create: `scripts/tune_event_market_ranking.py`
- Create: `tests/unit/test_tune_event_market_ranking.py`

- [ ] **Step 1: Write the unit tests (pure function coverage)**

```python
# tests/unit/test_tune_event_market_ranking.py
"""Tests for the coordinate-descent tuner."""
from __future__ import annotations

import pytest


def test_coordinate_descent_finds_global_optimum_on_unimodal_synth():
    from scripts.tune_event_market_ranking import coordinate_descent

    def score(cfg: dict) -> float:
        # Unimodal bowl: optimum at (w_entity=0.5, w_date=0.5).
        return -((cfg["w_entity"] - 0.5) ** 2 + (cfg["w_date"] - 0.5) ** 2)

    grid = {
        "w_entity": [0.1, 0.3, 0.5, 0.8, 1.2],
        "w_date":   [0.0, 0.2, 0.5, 1.0],
    }
    start = {"w_entity": 0.1, "w_date": 0.0}
    best = coordinate_descent(score, grid, start, passes=2)
    assert best["w_entity"] == 0.5
    assert best["w_date"] == 0.5


def test_coordinate_descent_idempotent_once_converged():
    from scripts.tune_event_market_ranking import coordinate_descent

    def score(cfg: dict) -> float:
        return -abs(cfg["x"] - 5)

    grid = {"x": [1, 3, 5, 7, 9]}
    best = coordinate_descent(score, grid, {"x": 1}, passes=3)
    assert best["x"] == 5


def test_coordinate_descent_respects_order_for_ties(monkeypatch):
    """When multiple values tie, keep the first in range order (deterministic)."""
    from scripts.tune_event_market_ranking import coordinate_descent
    grid = {"x": [1, 2, 3]}
    best = coordinate_descent(lambda cfg: 0.0, grid, {"x": 1}, passes=1)
    assert best["x"] == 1


def test_offline_gate_rejects_regression_on_any_bucket():
    from scripts.tune_event_market_ranking import evaluate_offline_gate
    v1 = {
        "overall": {"retrieval@5": {"mean": 0.40, "ci_low": 0.35, "ci_high": 0.45}},
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.50}}},
    }
    # v2 improves overall but politics regresses > 5%.
    v2 = {
        "overall": {"retrieval@5": {"mean": 0.55, "ci_low": 0.50, "ci_high": 0.60}},
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.40}}},
    }
    out = evaluate_offline_gate(v1, v2, max_bucket_regression=0.05)
    assert out["status"] == "failed"
    assert "politics" in out["reason"]


def test_offline_gate_accepts_strict_ci_improvement():
    from scripts.tune_event_market_ranking import evaluate_offline_gate
    v1 = {
        "overall": {
            "retrieval@5": {"mean": 0.40, "ci_low": 0.35, "ci_high": 0.45},
            "ndcg@10":     {"mean": 0.50},
        },
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.40}}},
    }
    v2 = {
        "overall": {
            "retrieval@5": {"mean": 0.55, "ci_low": 0.50, "ci_high": 0.60},
            "ndcg@10":     {"mean": 0.55},
        },
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.42}}},
    }
    out = evaluate_offline_gate(v1, v2, max_bucket_regression=0.05)
    assert out["status"] == "passed"
```

- [ ] **Step 2: Run — expect failures**

Run: `docker compose exec -T app python -m pytest tests/unit/test_tune_event_market_ranking.py -v`
Expected: 5 failures with `ModuleNotFoundError: No module named 'scripts.tune_event_market_ranking'`.

- [ ] **Step 3: Implement the tuner**

```python
# scripts/tune_event_market_ranking.py
"""Offline tuner for hybrid_search_v2 — coordinate descent + offline gate.

Usage:
    python -m scripts.tune_event_market_ranking \\
        --labels docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl \\
        --out docs/eval_baselines/ranking_event_market_best_2026-04-25.json

Evaluation is deterministic: each config is scored by running the chantier #3
harness `runner.run_eval` on the provided labels, using the ranking variant
specified by the config — **not** via env flip (to avoid race conditions).
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select

from app.db.database import get_session_factory

logger = logging.getLogger(__name__)


# Grid search ranges (spec §6.1 Section 3).
RANGES: dict[str, list] = {
    "w_entity":  [0.1, 0.3, 0.5, 0.8, 1.2],
    "w_date":    [0.0, 0.2, 0.5, 1.0],
    "w_bucket":  [0.0, 0.1, 0.3, 0.5],
    "tau_days":  [7.0, 14.0, 30.0, 60.0],
    "min_sim":   [0.35, 0.45, 0.55],
    "rrf_k":     [30, 60, 90, 120],
}

V1_CONFIG: dict = {
    "w_entity": 0.5, "w_date": 0.0, "w_bucket": 0.0,
    "tau_days": 14.0, "min_sim": 0.45, "rrf_k": 60,
}

# Order of coordinate descent passes (interactions captured via 2 passes).
COORD_ORDER = ("w_entity", "w_date", "w_bucket", "tau_days", "min_sim", "rrf_k")

MAX_BUCKET_REGRESSION = 0.05


def coordinate_descent(
    score_fn: Callable[[dict], float],
    grid: dict[str, list],
    start: dict,
    *,
    passes: int = 2,
) -> dict:
    """Sweep each parameter in COORD_ORDER passes times, keeping the best."""
    best = dict(start)
    best_score = score_fn(best)
    for _pass in range(passes):
        for param, values in grid.items():
            for v in values:
                candidate = dict(best)
                candidate[param] = v
                s = score_fn(candidate)
                if s > best_score:
                    best_score = s
                    best = candidate
    return best


def evaluate_offline_gate(
    v1_report: dict, v2_report: dict, *, max_bucket_regression: float,
) -> dict:
    """Three conditions (spec §6.3):
      1. retrieval@5 v2 ci_low > v1 ci_high (strict disjoint)
      2. nDCG@10 v2 mean > v1 mean
      3. no bucket regresses > max_bucket_regression on retrieval@5
    """
    v1_ret5 = v1_report["overall"].get("retrieval@5", {})
    v2_ret5 = v2_report["overall"].get("retrieval@5", {})
    if v2_ret5.get("ci_low", 0.0) <= v1_ret5.get("ci_high", 0.0):
        return {
            "status": "failed",
            "reason": (
                f"retrieval@5 CI overlap: v2 ci_low={v2_ret5.get('ci_low')} "
                f"<= v1 ci_high={v1_ret5.get('ci_high')}"
            ),
        }
    v1_nd10 = v1_report["overall"].get("ndcg@10", {}).get("mean", 0.0)
    v2_nd10 = v2_report["overall"].get("ndcg@10", {}).get("mean", 0.0)
    if v2_nd10 <= v1_nd10:
        return {
            "status": "failed",
            "reason": f"nDCG@10 did not improve: v2={v2_nd10} <= v1={v1_nd10}",
        }
    for bucket, stats in v2_report.get("per_bucket", {}).items():
        v1_bucket = v1_report.get("per_bucket", {}).get(bucket, {})
        v1_mean = v1_bucket.get("retrieval@5", {}).get("mean", 0.0)
        v2_mean = stats.get("retrieval@5", {}).get("mean", 0.0)
        if v1_mean - v2_mean > max_bucket_regression:
            return {
                "status": "failed",
                "reason": (
                    f"bucket {bucket!r} regressed: v1={v1_mean} -> v2={v2_mean} "
                    f"(delta {v1_mean - v2_mean:.3f} > max {max_bucket_regression:.3f})"
                ),
            }
    return {"status": "passed"}


async def _score_config_async(cfg: dict, labels_path: Path) -> dict:
    """Run the harness with a specific config, return aggregated report."""
    from app.eval.labels_event_market import load_event_market_labels
    from app.eval.metrics import aggregate, ndcg_at_k, retrieval_at_k
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
    # Bypass the env flag — call v2 directly with an override config.
    pairs = load_event_market_labels(labels_path)
    if not pairs:
        return {"overall": {}, "per_bucket": {}, "n_pairs": 0}

    factory = get_session_factory()
    per_pair: list[dict] = []
    async with factory() as session:
        for p in pairs:
            from app.db.models import Event
            ev = (
                await session.execute(select(Event).where(Event.id == p.query_id))
            ).scalar_one_or_none()
            if ev is None or ev.embedding is None:
                continue
            ranked = await _run_v2_with_override(session, ev, cfg)
            if not ranked:
                continue
            ranked_ids = [r["market_id"] for r in ranked]
            per_pair.append({
                "retrieval@5": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=5),
                "ndcg@10":     ndcg_at_k(set(p.relevant_ids), ranked_ids, k=10),
                "bucket":      ev.bucket or "other",
            })

    overall = aggregate(per_pair, strata=("bucket",))
    per_bucket = overall.pop("per_source", {})  # aggregate re-uses this key name
    return {
        "overall": overall,
        "per_bucket": per_bucket,
        "n_pairs": len(per_pair),
    }


async def _run_v2_with_override(session, event, cfg: dict) -> list[dict]:
    """Call hybrid_search_markets_v2 with ad-hoc override weights.

    We monkeypatch the settings within the coroutine by setting module-level
    thread-local state — simpler is to patch get_settings() via lru_cache
    invalidation + env vars. We mutate the in-process Settings object
    directly because this script runs single-threaded.
    """
    from app.core.config import get_settings
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
    s = get_settings()
    prev = {k: getattr(s, f"ranking_v2_{k}") for k in cfg}
    try:
        for k, v in cfg.items():
            object.__setattr__(s, f"ranking_v2_{k}", v)
        return await hybrid_search_markets_v2(
            session, list(event.embedding),
            event.event_retrieval_text or event.event_title,
            top_k=10,
            event_bucket=event.bucket,
            event_entities=event.key_entities,
            event_last_seen=event.last_seen,
        )
    finally:
        for k, v in prev.items():
            object.__setattr__(s, f"ranking_v2_{k}", v)


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


async def _run(labels_path: Path, out_path: Path, resume: bool) -> int:
    # Score v1 baseline.
    logger.info("scoring v1 baseline")
    v1_report = await _score_config_async(V1_CONFIG, labels_path)

    # Coordinate descent.
    loop = asyncio.get_event_loop()

    def sync_score(cfg: dict) -> float:
        """Run async _score_config_async, return overall retrieval@5 mean."""
        rep = loop.run_until_complete(_score_config_async(cfg, labels_path))
        ret5 = rep["overall"].get("retrieval@5", {}).get("mean", 0.0)
        ndcg10 = rep["overall"].get("ndcg@10", {}).get("mean", 0.0)
        # Primary: retrieval@5; tiebreak: nDCG@10.
        return ret5 * 1000 + ndcg10

    # NOTE: coordinate_descent is sync — for simplicity we run it in the
    # already-started loop via a small adapter. In practice the outer
    # `asyncio.run` wraps this call; inside, we can't call run_until_complete
    # on the same loop. We therefore invoke it synchronously by materialising
    # scores eagerly.
    eager_cache: dict[tuple, float] = {}

    def sync_score_v2(cfg: dict) -> float:
        key = tuple(sorted(cfg.items()))
        if key in eager_cache:
            return eager_cache[key]
        # Schedule as a new task on a fresh loop (single-threaded OK here).
        rep = asyncio.new_event_loop().run_until_complete(
            _score_config_async(cfg, labels_path)
        )
        ret5 = rep["overall"].get("retrieval@5", {}).get("mean", 0.0)
        ndcg10 = rep["overall"].get("ndcg@10", {}).get("mean", 0.0)
        eager_cache[key] = ret5 * 1000 + ndcg10
        return eager_cache[key]

    logger.info("starting coordinate descent")
    best = coordinate_descent(sync_score_v2, RANGES, dict(V1_CONFIG), passes=2)
    logger.info("best config: %s", best)

    v2_report = await _score_config_async(best, labels_path)
    gate = evaluate_offline_gate(v1_report, v2_report, max_bucket_regression=MAX_BUCKET_REGRESSION)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "labels_path": str(labels_path),
        "v1_config": V1_CONFIG,
        "v2_config": best,
        "v1_report": v1_report,
        "v2_report": v2_report,
        "gate": gate,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({
        "gate_status": gate["status"],
        "best_config": best,
        "out_path": str(out_path),
    }, indent=2))
    return 0 if gate["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="tune_event_market_ranking")
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(_run(args.labels, args.out, args.resume))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the unit tests — expect pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_tune_event_market_ranking.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/tune_event_market_ranking.py tests/unit/test_tune_event_market_ranking.py
git commit -m "feat(ranking): tune_event_market_ranking — coordinate descent + offline gate"
```

---

## Task 13: Celery shadow task — `record_shadow_ranking`

**Files:**
- Create: `app/workers/tasks_ranking_shadow.py`
- Modify: `app/workers/celery_app.py`
- Create: `tests/integration/test_ranking_shadow.py` (skeleton + Celery-eager test)

- [ ] **Step 1: Register the task module in `celery_app.py`**

In `app/workers/celery_app.py`:
- Add `"app.workers.tasks_ranking_shadow.*": {"queue": "scoring"}` to `task_routes` (around line 49, next to the embeddings_backfill route).
- Add `"app.workers.tasks_ranking_shadow"` to `autodiscover_tasks([...])` (around line 156).

- [ ] **Step 2: Write the task**

```python
# app/workers/tasks_ranking_shadow.py
"""Celery task: compute the opposite-variant top-k for an event and record it.

Idempotent via the UNIQUE (event_id, variant, rank) constraint — retries are
safe. Kill-switched via `settings.ranking_shadow_enabled`.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Event, EventMarketRankingShadow
from app.retrieval.ranking_variant import active_ranking_variant
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks_ranking_shadow.record_shadow_ranking",
    bind=True,
    rate_limit="120/m",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def record_shadow_ranking(self, *, event_id: int) -> dict:
    """Compute and store the opposite-variant top-k ranking for `event_id`."""
    settings = get_settings()
    if not settings.ranking_shadow_enabled:
        return {"status": "disabled", "event_id": event_id}
    try:
        return _run_async(_do(event_id))
    except Exception as exc:
        logger.exception("record_shadow_ranking failed event_id=%s", event_id)
        raise self.retry(exc=exc)


async def _do(event_id: int) -> dict:
    prod_variant = active_ranking_variant()
    opposite = "v2" if prod_variant == "v1" else "v1"

    factory = get_session_factory()
    async with factory() as session:
        ev = (
            await session.execute(select(Event).where(Event.id == event_id))
        ).scalar_one_or_none()
        if ev is None or ev.embedding is None:
            return {"status": "skipped_no_embedding", "event_id": event_id}

        text = ev.event_retrieval_text or ev.event_title

        if opposite == "v2":
            from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
            results = await hybrid_search_markets_v2(
                session, list(ev.embedding), text,
                top_k=5,
                event_bucket=ev.bucket,
                event_entities=ev.key_entities,
                event_last_seen=ev.last_seen,
            )
        else:
            from app.retrieval.hybrid_search import hybrid_search_markets
            results = await hybrid_search_markets(
                session, list(ev.embedding), text,
                top_k=5,
                event_bucket=ev.bucket,
                event_entities=ev.key_entities,
            )

        rows_inserted = 0
        for r in results:
            stmt = pg_insert(EventMarketRankingShadow).values(
                event_id=event_id,
                market_id=r["market_id"],
                variant=opposite,
                rank=r.get("rank"),
                rrf_score=r.get("rrf_score") or 0.0,
                cosine_score=r.get("cosine_score"),
                entity_matches=r.get("entity_matches"),
                date_proximity=r.get("date_proximity"),
                bucket_match=r.get("bucket_match"),
            ).on_conflict_do_nothing(constraint="uq_ranking_shadow_event_variant_rank")
            res = await session.execute(stmt)
            rows_inserted += int(res.rowcount or 0)
        await session.commit()

    return {
        "status": "ok",
        "event_id": event_id,
        "shadow_variant": opposite,
        "rows_inserted": rows_inserted,
        "top_k_size": len(results),
    }
```

- [ ] **Step 3: Write the integration test**

```python
# tests/integration/test_ranking_shadow.py
"""Integration: record_shadow_ranking writes top-k rows idempotently."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import Event, Market, EventMarketRankingShadow


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _apply_task_in_thread(fn, **kwargs):
    """Run a celery task in a fresh thread to avoid event-loop collision
    with pytest-asyncio. Same pattern as tests/integration/test_sourcing_shadow.py."""
    import concurrent.futures

    def _run():
        return fn.apply(kwargs=kwargs).get(disable_sync_subtasks=False, timeout=30)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result(timeout=60)


@pytest.mark.asyncio
async def test_record_shadow_ranking_writes_rows(async_db_factory, monkeypatch):
    from app.workers.tasks_ranking_shadow import record_shadow_ranking

    eid = 900_123_001  # high-range to avoid collision on shared dev DB
    async with async_db_factory() as s:
        s.add(Event(
            id=eid,
            event_title="t-shadow-1",
            event_summary="summary",
            bucket="politics",
            last_seen=datetime(2026, 4, 25, tzinfo=timezone.utc),
            embedding=[0.1] * 1536,
            event_retrieval_text="t-shadow-1 summary",
        ))
        for mid in ("shadow_m1", "shadow_m2"):
            s.add(Market(
                market_id=mid, question=f"Q-{mid}",
                category="politics", bucket="politics",
                end_date=datetime(2026, 5, 15, tzinfo=timezone.utc),
                active=True, closed=False, accepting_orders=True,
                embedding=[0.1] * 1536,
                market_retrieval_text=f"retrieval {mid}",
            ))
        await s.commit()

    try:
        # First run: writes rows.
        result = _apply_task_in_thread(record_shadow_ranking, event_id=eid)
        assert result["status"] == "ok"
        assert result["rows_inserted"] >= 1

        # Second run: same call, no new rows (UNIQUE + ON CONFLICT DO NOTHING).
        result2 = _apply_task_in_thread(record_shadow_ranking, event_id=eid)
        assert result2["status"] == "ok"
        assert result2["rows_inserted"] == 0

        async with async_db_factory() as s:
            rows = (await s.execute(
                select(EventMarketRankingShadow).where(EventMarketRankingShadow.event_id == eid)
            )).scalars().all()
            assert rows and all(r.variant in ("v1", "v2") for r in rows)
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventMarketRankingShadow).where(EventMarketRankingShadow.event_id == eid))
            await s.execute(delete(Event).where(Event.id == eid))
            await s.execute(delete(Market).where(Market.market_id.in_(("shadow_m1", "shadow_m2"))))
            await s.commit()


@pytest.mark.asyncio
async def test_record_shadow_ranking_disabled_by_flag(async_db_factory, monkeypatch):
    from app.workers.tasks_ranking_shadow import record_shadow_ranking
    monkeypatch.setenv("RANKING_SHADOW_ENABLED", "false")
    get_settings.cache_clear()

    result = _apply_task_in_thread(record_shadow_ranking, event_id=12345)
    assert result == {"status": "disabled", "event_id": 12345}
```

- [ ] **Step 4: Run the integration test**

Run: `docker compose exec -T app python -m pytest tests/integration/test_ranking_shadow.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks_ranking_shadow.py app/workers/celery_app.py tests/integration/test_ranking_shadow.py
git commit -m "feat(ranking): record_shadow_ranking Celery task (idempotent, kill-switchable)"
```

---

## Task 14: Shadow hook in `tasks_scoring.py`

**Files:**
- Modify: `app/workers/tasks_scoring.py` (after the `candidates_found` status set at line ~152)

- [ ] **Step 1: Add the hook**

Insert in `app/workers/tasks_scoring.py`, directly after `event.processing_status = "candidates_found"` and the subsequent `await session.flush()` (line ~153), but **before** the LLM analysis step:

```python
        # ── chantier #4: fire-and-forget shadow ranking ──────────────────
        if settings.ranking_shadow_enabled:
            try:
                from app.workers.tasks_ranking_shadow import record_shadow_ranking
                record_shadow_ranking.delay(event_id=event_id)
            except Exception:
                logger.debug(
                    "ranking shadow enqueue failed event_id=%s — continuing",
                    event_id,
                )
```

This mirrors the chantier #1 `schedule_shadow_variants` pattern: local import (avoids pulling Celery at API startup), broad except (the production path must never break because the shadow broker is down), and `logger.debug` (not `warning`) because the retries are the task's own responsibility.

- [ ] **Step 2: Run the full regression suite**

Run: `docker compose exec -T app python -m pytest tests/ -x -q`
Expected: all tests still pass. The shadow task enqueues lazily, so unit tests that mock out Celery still behave unchanged.

- [ ] **Step 3: Smoke-test the enqueue path**

Run: `docker compose exec -T app python -c "
import asyncio
from app.db.database import get_session_factory
from app.db.models import Event
from sqlalchemy import select

async def main():
    async with get_session_factory()() as s:
        row = (await s.execute(select(Event).limit(1))).scalar_one_or_none()
        print('sample event:', row.id if row else 'NONE')

asyncio.run(main())
"`

Then manually trigger the shadow task for that id (if one exists) via:

```bash
docker compose exec -T app python -c "
from app.workers.tasks_ranking_shadow import record_shadow_ranking
result = record_shadow_ranking.apply(kwargs={'event_id': <ID>}).get()
print(result)
"
```
Expected: `{'status': 'ok', ...}` or `{'status': 'skipped_no_embedding', ...}` if the event has no embedding.

- [ ] **Step 4: Commit**

```bash
git add app/workers/tasks_scoring.py
git commit -m "feat(ranking): enqueue shadow ranking from scoring path (kill-switchable)"
```

---

## Task 15: Shadow analysis CLI — divergence + per-bucket + signal-delta

**Files:**
- Create: `scripts/analyze_ranking_shadow.py`

- [ ] **Step 1: Write the analyser**

```python
# scripts/analyze_ranking_shadow.py
"""Offline report over event_market_ranking_shadow rows (chantier #4).

Metrics:
  - total events with shadow coverage
  - divergence_rate_top1  — % events where rank-1 market differs between v1 and v2
  - divergence_top5_lt3    — % events where |top5_v1 ∩ top5_v2| < 3
  - per-bucket divergence
  - signal_delta_projection — for events that produced a prod signal, what
    would the v2 top-1 have surfaced? same / different market / neither.

Usage:
    python -m scripts.analyze_ranking_shadow --since 48h --out reports/shadow_2026-04-27.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, and_

from app.db.database import get_session_factory
from app.db.models import Event, EventMarketRankingShadow, Signal

logger = logging.getLogger(__name__)


async def _run(since: timedelta, out_path: Path) -> int:
    since_ts = datetime.now(timezone.utc) - since
    factory = get_session_factory()
    async with factory() as session:
        # Fetch shadow rows and their matching prod ranks.
        shadow_rows = (await session.execute(
            select(EventMarketRankingShadow)
            .where(EventMarketRankingShadow.computed_at >= since_ts)
        )).scalars().all()
        if not shadow_rows:
            logger.info("no shadow rows since %s", since_ts)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps({"n_events": 0}, indent=2))
            return 0

        # Index shadow by (event_id, variant, rank).
        by_ev_variant: dict[int, dict[str, list[EventMarketRankingShadow]]] = {}
        for r in shadow_rows:
            by_ev_variant.setdefault(r.event_id, {}).setdefault(r.variant, []).append(r)

        # For the prod side, we need the prod top-5 at the time this event was
        # scored — that lives in `event_market_candidates` (v1 behaviour).
        # Here we use it implicitly: the shadow variant is the *opposite* of
        # prod, so per-event we have exactly one variant's shadow rows. To
        # compare, we need the prod ranking. Query `EventMarketCandidate`.
        from app.db.models import EventMarketCandidate
        prod_candidates = (await session.execute(
            select(EventMarketCandidate)
            .where(EventMarketCandidate.event_id.in_(by_ev_variant.keys()))
            .order_by(EventMarketCandidate.event_id, EventMarketCandidate.rank)
        )).scalars().all()
        prod_by_ev: dict[int, list[EventMarketCandidate]] = {}
        for c in prod_candidates:
            prod_by_ev.setdefault(c.event_id, []).append(c)

        # Events (for bucket stratification).
        events = (await session.execute(
            select(Event).where(Event.id.in_(by_ev_variant.keys()))
        )).scalars().all()
        event_bucket = {e.id: (e.bucket or "other") for e in events}

        # Prod signals — for signal-delta projection.
        signals = (await session.execute(
            select(Signal).where(Signal.event_id.in_(by_ev_variant.keys()))
        )).scalars().all()
        signal_market_by_ev: dict[int, str] = {s.event_id: s.market_id for s in signals}

    # Aggregate metrics.
    n_events = 0
    n_top1_diff = 0
    n_top5_low_overlap = 0
    bucket_stats: dict[str, dict[str, int]] = {}
    signal_delta = {"same": 0, "different": 0, "n_signals": 0}

    for eid, variants in by_ev_variant.items():
        # One shadow variant per event — pick it.
        shadow_variant, shadow_rows_e = next(iter(variants.items()))
        shadow_top = sorted(shadow_rows_e, key=lambda x: x.rank)
        prod_top = sorted(prod_by_ev.get(eid, []), key=lambda x: (x.rank or 99))
        if not prod_top:
            continue
        n_events += 1
        bucket = event_bucket.get(eid, "other")
        bucket_stats.setdefault(bucket, {"n": 0, "top1_diff": 0})
        bucket_stats[bucket]["n"] += 1

        shadow_top1 = shadow_top[0].market_id if shadow_top else None
        prod_top1 = prod_top[0].market_id if prod_top else None
        if shadow_top1 != prod_top1:
            n_top1_diff += 1
            bucket_stats[bucket]["top1_diff"] += 1

        shadow_top5 = {r.market_id for r in shadow_top[:5]}
        prod_top5 = {c.market_id for c in prod_top[:5]}
        if len(shadow_top5 & prod_top5) < 3:
            n_top5_low_overlap += 1

        if eid in signal_market_by_ev:
            signal_delta["n_signals"] += 1
            if signal_market_by_ev[eid] == shadow_top1:
                signal_delta["same"] += 1
            else:
                signal_delta["different"] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since_ts.isoformat(),
        "n_events": n_events,
        "divergence_rate_top1": n_top1_diff / n_events if n_events else 0.0,
        "divergence_top5_lt3": n_top5_low_overlap / n_events if n_events else 0.0,
        "per_bucket": {
            b: {
                "n": st["n"],
                "top1_diff_rate": st["top1_diff"] / st["n"] if st["n"] else 0.0,
            }
            for b, st in bucket_stats.items()
        },
        "signal_delta_projection": signal_delta,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


def _parse_since(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    raise argparse.ArgumentTypeError("since must end in 'h' or 'd' (e.g. 48h, 7d)")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="analyze_ranking_shadow")
    p.add_argument("--since", type=_parse_since, default=timedelta(hours=48))
    p.add_argument("--out", type=Path, default=Path("docs/eval_baselines/ranking_shadow_report.json"))
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(_run(args.since, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-check the CLI parses**

Run: `docker compose exec -T app python -m scripts.analyze_ranking_shadow --help`
Expected: usage line with `--since` and `--out`.

Run (empty DB OK): `docker compose exec -T app python -m scripts.analyze_ranking_shadow --since 24h --out /tmp/shadow_smoke.json`
Expected: file written with `{"n_events": 0, ...}` or a real aggregate if shadow rows already exist.

- [ ] **Step 3: Commit**

```bash
git add scripts/analyze_ranking_shadow.py
git commit -m "feat(ranking): analyze_ranking_shadow — divergence + per-bucket + signal delta"
```

---

## Task 16: Operator runbook

**Files:**
- Create: `docs/runbooks/promote_ranking_v2.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Promote event→market ranking v2 — Operator Runbook

**What:** Flip `ranking_variant_event_to_market` from `v1` to `v2` after the
offline gate and the 48 h shadow observation both pass.

**Who:** On-call engineer with prod env access + someone to eyeball the
dashboard during the first 72 h.

**Rollback:** single env flip, < 1 min.

---

## 1. Pre-conditions

- [ ] Chantier #4 code shipped on `main` (migration 024 applied in prod).
- [ ] Ground-truth labels present at
      `docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl`
      (≥ 1000 pairs: 500 human seed + 500 LLM-calibrated).
- [ ] Shadow observation has collected ≥ 200 events over ≥ 48 h.
- [ ] You have the v2 weights from
      `docs/eval_baselines/ranking_event_market_best_2026-04-25.json`
      (the `v2_config` block).

If any pre-condition is missing: **stop**. This runbook cannot be followed
safely without them.

## 2. Offline gate — MUST pass

Run:

```bash
docker compose exec -T app python -m scripts.tune_event_market_ranking \
    --labels docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl \
    --out   docs/eval_baselines/ranking_event_market_best_2026-04-25.json
```

Success output:

```json
{
  "gate_status": "passed",
  "best_config": { "w_entity": ..., "w_date": ..., ... },
  "out_path": "..."
}
```

If `gate_status == "failed"`, **do not flip**. Open
`ranking_event_market_best_2026-04-25.json`, read the `gate.reason` field, and
treat as a hard stop for this iteration.

## 3. Shadow gate — MUST pass

Run:

```bash
docker compose exec -T app python -m scripts.analyze_ranking_shadow \
    --since 48h \
    --out   docs/eval_baselines/ranking_shadow_$(date +%Y-%m-%d).json
```

Read the JSON. The three conditions:

1. `n_events >= 200` — else wait for more coverage.
2. `0.10 <= divergence_rate_top1 <= 0.50` — below 10 % means v1 and v2 agree
   too often (flip will change almost nothing); above 50 % means the two
   rankers are misaligned and something is wrong.
3. For every bucket in `per_bucket`, `top1_diff_rate < 0.80`.
4. If `signal_delta_projection.n_signals > 0`, `different / n_signals < 0.30`
   — v2 must not silently kill more than 30 % of prod signals.

If any condition fails: **do not flip**.

## 4. Write the tuned weights to config

Update `app/core/config.py` defaults (or the deployment env) with the
values from `best_config`:

```python
    ranking_v2_rrf_k: int = Field(default=<rrf_k>)
    ranking_v2_w_entity: float = Field(default=<w_entity>)
    ranking_v2_w_date: float = Field(default=<w_date>)
    ranking_v2_w_bucket: float = Field(default=<w_bucket>)
    ranking_v2_tau_days: float = Field(default=<tau_days>)
    ranking_v2_min_sim: float = Field(default=<min_sim>)
```

Commit + deploy **before** flipping the variant flag — this way, if the flip
has an issue, the weights were already validated.

## 5. Flip the variant flag

Option A — env var (fastest):
```bash
# In production env: set
RANKING_VARIANT_EVENT_TO_MARKET=v2
# Restart the API + scoring workers.
```

Option B — config commit:
```bash
# In app/core/config.py, change the default:
ranking_variant_event_to_market: str = Field(default="v2", ...)
```

## 6. Immediate post-flip verification (first 10 min)

- [ ] `docker compose logs -f worker` — no new errors from
      `hybrid_search_v2` or `record_shadow_ranking`.
- [ ] Hit `/api/admin/metrics/variants` — confirm new signals are being
      tagged with v2 in the production variant registry.
- [ ] Pull the top-5 markets for a fresh event via `/api/events/:id/markets`
      — sanity-check the ordering is plausible.

## 7. Monitoring — first 7 days

- Brier score and simulated P&L on the production variant must stay within
  10 % of the pre-flip 7-day window. Baseline metrics are in
  `/api/admin/metrics/variants` (chantier #1).
- Any 7-day regression > 10 % triggers a manual rollback decision (no auto).

## 8. Rollback

**Shadow rows only**:
```bash
RANKING_SHADOW_ENABLED=false
# Restart — stops opposite-variant compute. Prod ranking unchanged.
```

**Full rollback to v1**:
```bash
RANKING_VARIANT_EVENT_TO_MARKET=v1
# Restart — prod returns to v1 instantly. Takes < 1 min.
```

Neither step requires a DB migration to undo.

## 9. Post-mortem template

If the flip regressed:
1. Record which metric (Brier / P&L / retrieval / user-reported) triggered
   the rollback.
2. Note the `v2_config` that was live.
3. Open a follow-up issue with label `chantier-4` to revisit the tuning.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/promote_ranking_v2.md
git commit -m "docs(ranking): promote_ranking_v2 runbook (offline + shadow + 3-check gate)"
```

---

## Task 17: Final verification — full test suite + green-commit sentinel

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `docker compose exec -T app python -m pytest tests/ -q`
Expected: all tests pass. Exact count = chantier #3 green (239) + ~18 new unit + ~3 new integration = **~260 passed**.

If any test fails:
- If it's a pre-existing failure, fix it inline (it probably drifted between chantiers — not acceptable to ship with a red branch).
- If it's a new test, bug-hunt it in the subagent that wrote it.
- Do **not** mark task 17 complete until the suite is fully green.

- [ ] **Step 2: Targeted chantier-4 rerun (documents green-ness)**

Run:
```bash
docker compose exec -T app python -m pytest \
    tests/unit/test_ranking_variant.py \
    tests/unit/test_hybrid_search_v2.py \
    tests/unit/test_labels_event_market.py \
    tests/unit/test_tune_event_market_ranking.py \
    tests/integration/test_hybrid_search_v2_db.py \
    tests/integration/test_ranking_shadow.py \
    -v
```
Expected: 5 + 12 + 9 + 5 + 1 + 2 = **34 passed**.

- [ ] **Step 3: Verify the migration roundtrip**

Run:
```bash
docker compose exec -T app alembic current
# → 024 (head)
docker compose exec -T app alembic downgrade 023
docker compose exec -T app alembic upgrade head
# Verify the table + indexes return.
docker compose exec -T postgres psql -U polyedge -d polyedge \
    -c "SELECT COUNT(*) FROM event_market_ranking_shadow"
```
Expected: all commands succeed; final count query returns `0` on an empty DB.

- [ ] **Step 4: Verify the flag still defaults to v1 in prod**

Run:
```bash
docker compose exec -T app python -c "from app.core.config import get_settings; s = get_settings(); print(s.ranking_variant_event_to_market, s.ranking_shadow_enabled)"
```
Expected: `v1 True` — confirms no config has drifted.

- [ ] **Step 5: Final commit sentinel**

This task does not commit new code; it ends the chantier by standing
behind the tree as a whole. Announce "Chantier #4 shipped: <N> commits,
<K> tests green, flag remains v1 — ready for labelling run + shadow
observation."
```
