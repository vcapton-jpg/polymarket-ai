# Measurement Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a measurement layer that records 4 deterministic baselines for every signal and reports per-variant winrate (with Wilson CI95), Brier score, and simulated P&L — so future chantiers can tell whether a change is an improvement.

**Architecture:** New `signal_predictions` table (one row per signal × variant, `UNIQUE(signal_id, variant)`). Baselines computed in-band inside the signal persistence transaction (deterministic, <15ms). On market resolution, a single batched UPDATE refreshes all variants of the signal. Reporting via two admin REST endpoints + a CLI wrapper.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async (`Mapped`/`mapped_column`), Alembic (revision `020`, `down_revision="019"`), pytest-asyncio, existing `GammaClient`. Admin gate via `ADMIN_EMAILS` env allowlist (no new `role` column — YAGNI).

**Spec:** `docs/specs/2026-04-23-measurement-foundations-design.md`. Read it once before starting — every numeric formula in this plan comes from it.

**Branch target:** `measurement/foundations` off `main` (worktree; create before task 1).

---

## File structure (created / modified)

**New files:**
- `alembic/versions/020_signal_predictions.py` — migration
- `app/measurement/__init__.py` — exports + registers the 4 baselines at import time
- `app/measurement/variant_registry.py` — `VariantRegistry`, `VariantPrediction`, `get_registry()`
- `app/measurement/scoring_context.py` — `ScoringContext`, `ArticleImpact` dataclasses
- `app/measurement/baselines.py` — 4 pure baseline functions
- `app/measurement/pipeline.py` — `record_baselines()`, `schedule_shadow_variants()` stub, `record_prediction_resolution()`
- `app/measurement/metrics.py` — pure math: `wilson_ci95()`, `brier_score()`, `simulated_pnl_eur()`, aggregation helpers
- `app/api/routes/admin_metrics.py` — two admin endpoints
- `app/api/schemas/admin_metrics.py` — pydantic response schemas
- `app/api/deps/admin.py` — `require_admin` dependency
- `scripts/backfill_signal_predictions.py` — idempotent backfill
- `scripts/report_metrics.py` — CLI wrapper
- `tests/unit/test_measurement_baselines.py`
- `tests/unit/test_measurement_registry.py`
- `tests/unit/test_measurement_metrics.py`
- `tests/unit/test_measurement_pipeline.py`
- `tests/unit/test_admin_require_admin.py`
- `tests/unit/test_backfill_signal_predictions.py`
- `tests/integration/test_signal_predictions_hook.py`
- `tests/integration/test_resolution_hook.py`
- `tests/integration/test_admin_metrics_variants.py`
- `tests/integration/test_admin_metrics_rolling.py`

**Modified files:**
- `app/db/models.py` — add `SignalPrediction` model
- `app/signal/signal_builder.py:371` — hook `record_baselines` before final commit
- `app/workers/tasks_outcomes.py:~251` — hook `record_prediction_resolution` in the resolution loop
- `app/core/config.py` — add `admin_emails: str` setting
- `app/api/main.py` — register `admin_metrics` router

---

## Task 1: Alembic migration — `signal_predictions` table

**Files:**
- Create: `alembic/versions/020_signal_predictions.py`

- [ ] **Step 1: Write the migration**

```python
"""signal_predictions: per-signal per-variant predictions + resolved metrics.

Revision ID: 020
Revises: 019
Create Date: 2026-04-23
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_predictions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "signal_id",
            sa.BigInteger,
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.Text, nullable=False),
        sa.Column("predicted_direction", sa.Text, nullable=True),  # BUY_YES | BUY_NO | NULL
        sa.Column("predicted_probability", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("direction_correct", sa.Boolean, nullable=True),
        sa.Column("brier_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("simulated_pnl_eur", sa.Numeric(8, 2), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("signal_id", "variant", name="uq_signal_predictions_signal_variant"),
    )
    op.create_index(
        "idx_sp_variant_resolved",
        "signal_predictions",
        ["variant", "resolved_at"],
        postgresql_where=sa.text("resolved_at IS NOT NULL"),
    )
    op.create_index("idx_sp_signal", "signal_predictions", ["signal_id"])


def downgrade() -> None:
    op.drop_index("idx_sp_signal", table_name="signal_predictions")
    op.drop_index("idx_sp_variant_resolved", table_name="signal_predictions")
    op.drop_table("signal_predictions")
```

- [ ] **Step 2: Apply the migration**

Run: `docker compose exec -T app alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 019 -> 020, signal_predictions`.

- [ ] **Step 3: Verify schema**

Run: `docker compose exec -T db psql -U postgres -d signal -c "\d signal_predictions"`
Expected: columns listed, unique constraint `uq_signal_predictions_signal_variant` present, two indexes present.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/020_signal_predictions.py
git commit -m "feat(measurement): migration 020 — signal_predictions table"
```

---

## Task 2: `SignalPrediction` SQLAlchemy model

**Files:**
- Modify: `app/db/models.py` (add after `SignalOutcome`, around line 425)
- Test: `tests/unit/test_measurement_pipeline.py` (not yet — model is exercised transitively in Task 6; this task just adds the mapping)

- [ ] **Step 1: Add the model**

Append this class right after `SignalOutcome` in `app/db/models.py`:

```python
# ---------------------------------------------------------------------------
# signal_predictions  (one row per signal × variant — measurement layer)
# ---------------------------------------------------------------------------
class SignalPrediction(Base):
    __tablename__ = "signal_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False
    )
    variant: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    predicted_probability: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    direction_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    brier_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    simulated_pnl_eur: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("signal_id", "variant", name="uq_signal_predictions_signal_variant"),
    )
```

Ensure `BigInteger`, `UniqueConstraint` are in the top-level imports from `sqlalchemy` (they are already imported in the file — verify by searching).

- [ ] **Step 2: Smoke — import model in a Python shell**

Run: `docker compose exec -T app python -c "from app.db.models import SignalPrediction; print(SignalPrediction.__tablename__)"`
Expected: `signal_predictions`

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat(measurement): add SignalPrediction ORM model"
```

---

## Task 3: `ScoringContext` + `VariantPrediction` dataclasses

**Files:**
- Create: `app/measurement/__init__.py` (empty for now — baselines register in Task 5)
- Create: `app/measurement/scoring_context.py`
- Create: `app/measurement/variant_registry.py` (just the `VariantPrediction` dataclass in this task; registry class arrives in Task 4)

- [ ] **Step 1: Write `scoring_context.py`**

```python
"""Immutable scoring context passed to every baseline function.

Baselines must not hit the DB — all data they need lives here. This guarantees
deterministic, fast (<1ms) execution and makes unit testing trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleImpact:
    """One news source's contribution to news_sentiment baseline."""
    direction: str          # 'YES' | 'NO' | 'NEUTRAL'
    source_weight: float    # [0, 1]


@dataclass(frozen=True)
class ScoringContext:
    signal_id: int
    market_id: str
    event_id: int | None
    market_price: float                     # P(YES) at signal time, [0, 1]
    market_price_24h_ago: float | None      # P(YES) 24h ago, or None if unknown
    article_impacts: tuple[ArticleImpact, ...]
    t0: datetime                            # signal creation time (UTC)
```

- [ ] **Step 2: Write `variant_registry.py` (just `VariantPrediction` — add the registry class in Task 4)**

```python
"""Variant registry — enumeration only. Execution lives in pipeline.py.

A 'variant' is a named predictor: the production signal, the 4 baselines, and
(future chantiers) shadow LLM / retrieval variants. Each variant produces a
VariantPrediction from a ScoringContext.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariantPrediction:
    """A direction + probability emitted by a single variant.

    Both fields may be None when the variant lacks data (e.g. momentum with no
    24h price history). A None row is still inserted — presence is coverage
    proof; aggregation queries filter it out.
    """
    direction: str | None       # 'BUY_YES' | 'BUY_NO' | None
    probability: float | None   # P(YES) in [0, 1] or None
```

- [ ] **Step 3: Create empty `__init__.py`**

```python
"""Measurement layer — baselines, variants, metrics.

Baseline registration happens in Task 5 (app/measurement/__init__.py is the
import-time hook that registers them). For now the module is empty.
"""
```

- [ ] **Step 4: Smoke**

Run: `docker compose exec -T app python -c "from app.measurement.scoring_context import ScoringContext, ArticleImpact; from app.measurement.variant_registry import VariantPrediction; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add app/measurement/
git commit -m "feat(measurement): ScoringContext, ArticleImpact, VariantPrediction"
```

---

## Task 4: `VariantRegistry` class + `get_registry()` singleton

**Files:**
- Modify: `app/measurement/variant_registry.py`
- Create: `tests/unit/test_measurement_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_measurement_registry.py`:

```python
import pytest

from app.measurement.variant_registry import (
    VariantPrediction,
    VariantRegistry,
    get_registry,
)


def _noop(_ctx):
    return VariantPrediction(direction=None, probability=None)


def test_register_baseline_and_enumerate():
    reg = VariantRegistry()
    reg.register_baseline("baseline_x", _noop)
    assert list(reg.baselines().keys()) == ["baseline_x"]
    assert reg.baselines()["baseline_x"] is _noop


def test_register_baseline_is_idempotent_duplicate_name_raises():
    reg = VariantRegistry()
    reg.register_baseline("baseline_x", _noop)
    with pytest.raises(ValueError, match="already registered"):
        reg.register_baseline("baseline_x", _noop)


def test_register_shadow_separate_from_baselines():
    reg = VariantRegistry()
    reg.register_baseline("b", _noop)
    reg.register_shadow("s", _noop)
    assert "b" not in reg.shadows()
    assert "s" not in reg.baselines()


def test_get_registry_returns_singleton():
    assert get_registry() is get_registry()
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_registry.py -v`
Expected: `ImportError` or `AttributeError` on `VariantRegistry` / `get_registry`.

- [ ] **Step 3: Implement the registry**

Append to `app/measurement/variant_registry.py`:

```python
from typing import Callable, Protocol


class BaselineFn(Protocol):
    def __call__(self, ctx) -> VariantPrediction: ...  # noqa: D401


class VariantRegistry:
    """Registers baseline and shadow variants by name.

    Baselines are in-band, deterministic, fast — run inside the signal
    transaction. Shadows are async, possibly expensive, run via Celery. The
    registry stores them separately so pipeline.py can dispatch correctly.
    """

    def __init__(self) -> None:
        self._baselines: dict[str, BaselineFn] = {}
        self._shadows: dict[str, BaselineFn] = {}

    def register_baseline(self, name: str, fn: "BaselineFn") -> None:
        if name in self._baselines:
            raise ValueError(f"Baseline {name!r} already registered")
        self._baselines[name] = fn

    def register_shadow(self, name: str, fn: "BaselineFn") -> None:
        if name in self._shadows:
            raise ValueError(f"Shadow {name!r} already registered")
        self._shadows[name] = fn

    def baselines(self) -> dict[str, "BaselineFn"]:
        return dict(self._baselines)

    def shadows(self) -> dict[str, "BaselineFn"]:
        return dict(self._shadows)


_registry = VariantRegistry()


def get_registry() -> VariantRegistry:
    """Module-level singleton used by the signal builder + Celery workers."""
    return _registry
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_registry.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/measurement/variant_registry.py tests/unit/test_measurement_registry.py
git commit -m "feat(measurement): VariantRegistry with register_baseline/shadow + singleton"
```

---

## Task 5: Four baseline functions + import-time registration

**Files:**
- Create: `app/measurement/baselines.py`
- Modify: `app/measurement/__init__.py`
- Create: `tests/unit/test_measurement_baselines.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_measurement_baselines.py`:

```python
from datetime import datetime, timezone

import pytest

from app.measurement.baselines import (
    baseline_market_price,
    baseline_momentum,
    baseline_news_sentiment,
    baseline_random,
)
from app.measurement.scoring_context import ArticleImpact, ScoringContext


def _ctx(signal_id: int = 1, price: float = 0.6,
         price_24h: float | None = None,
         articles: tuple[ArticleImpact, ...] = ()) -> ScoringContext:
    return ScoringContext(
        signal_id=signal_id,
        market_id="0xdeadbeef",
        event_id=1,
        market_price=price,
        market_price_24h_ago=price_24h,
        article_impacts=articles,
        t0=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )


# ── random ──────────────────────────────────────────────────────────
def test_baseline_random_deterministic_for_same_signal_id():
    a = baseline_random(_ctx(signal_id=42))
    b = baseline_random(_ctx(signal_id=42))
    assert a == b


def test_baseline_random_probability_always_half():
    for sid in [1, 7, 99, 12345]:
        assert baseline_random(_ctx(signal_id=sid)).probability == 0.5


def test_baseline_random_direction_varies_by_signal_id():
    directions = {baseline_random(_ctx(signal_id=i)).direction for i in range(50)}
    assert directions == {"BUY_YES", "BUY_NO"}


# ── market_price ─────────────────────────────────────────────────────
@pytest.mark.parametrize("price,expected_dir", [
    (0.0, "BUY_NO"),
    (0.49, "BUY_NO"),
    (0.5, "BUY_NO"),     # tie-break: > 0.5 is YES
    (0.51, "BUY_YES"),
    (1.0, "BUY_YES"),
])
def test_baseline_market_price_direction(price, expected_dir):
    p = baseline_market_price(_ctx(price=price))
    assert p.direction == expected_dir
    assert p.probability == price


# ── momentum ─────────────────────────────────────────────────────────
def test_baseline_momentum_returns_none_when_history_missing():
    p = baseline_momentum(_ctx(price=0.7, price_24h=None))
    assert p.direction is None
    assert p.probability is None


def test_baseline_momentum_positive_return_buys_yes():
    p = baseline_momentum(_ctx(price=0.7, price_24h=0.5))
    assert p.direction == "BUY_YES"
    assert p.probability == pytest.approx(0.5 + 0.5 * 0.2, abs=1e-6)


def test_baseline_momentum_negative_return_buys_no():
    p = baseline_momentum(_ctx(price=0.3, price_24h=0.5))
    assert p.direction == "BUY_NO"
    assert p.probability == pytest.approx(0.5 + 0.5 * (-0.2), abs=1e-6)


def test_baseline_momentum_clips_extreme_return():
    p = baseline_momentum(_ctx(price=1.0, price_24h=0.0))
    # 0.5 + 0.5 * 1.0 = 1.0, clipped to 0.99
    assert p.probability == pytest.approx(0.99, abs=1e-6)


# ── news_sentiment ───────────────────────────────────────────────────
def test_baseline_news_sentiment_empty_articles_none():
    p = baseline_news_sentiment(_ctx(articles=()))
    assert p.direction is None and p.probability is None


def test_baseline_news_sentiment_weighted_majority_yes():
    arts = (
        ArticleImpact(direction="YES", source_weight=0.9),
        ArticleImpact(direction="NO", source_weight=0.2),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    assert p.direction == "BUY_YES"
    assert p.probability is not None and p.probability > 0.5


def test_baseline_news_sentiment_neutral_articles_ignored():
    arts = (
        ArticleImpact(direction="NEUTRAL", source_weight=0.9),
        ArticleImpact(direction="NEUTRAL", source_weight=0.7),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    # all-neutral → sentiment = 0 → probability = sigmoid(0) = 0.5
    assert p.probability == pytest.approx(0.5, abs=1e-6)


def test_baseline_news_sentiment_weighted_majority_no():
    arts = (
        ArticleImpact(direction="NO", source_weight=0.8),
        ArticleImpact(direction="YES", source_weight=0.1),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    assert p.direction == "BUY_NO"
    assert p.probability is not None and p.probability < 0.5
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_baselines.py -v`
Expected: ImportError on `app.measurement.baselines`.

- [ ] **Step 3: Implement `app/measurement/baselines.py`**

```python
"""Four deterministic, zero-LLM baseline predictors.

Every baseline takes a ScoringContext and returns a VariantPrediction. Must be
pure (no DB, no network, no wall-clock dependency beyond ctx.t0).
"""

from __future__ import annotations

import math
import random as _random

from app.measurement.scoring_context import ScoringContext
from app.measurement.variant_registry import VariantPrediction


def baseline_random(ctx: ScoringContext) -> VariantPrediction:
    """Coin flip keyed by signal_id. Deterministic across runs."""
    rng = _random.Random(ctx.signal_id)
    direction = "BUY_YES" if rng.random() < 0.5 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=0.5)


def baseline_market_price(ctx: ScoringContext) -> VariantPrediction:
    """Follow the market: BUY_YES if price > 0.5, else BUY_NO. Prob = market price."""
    direction = "BUY_YES" if ctx.market_price > 0.5 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=ctx.market_price)


def baseline_momentum(ctx: ScoringContext) -> VariantPrediction:
    """24h momentum. None if we lack a 24h-ago price."""
    if ctx.market_price_24h_ago is None:
        return VariantPrediction(direction=None, probability=None)
    return_24h = ctx.market_price - ctx.market_price_24h_ago  # in [-1, 1]
    direction = "BUY_YES" if return_24h > 0 else "BUY_NO"
    prob = max(0.01, min(0.99, 0.5 + 0.5 * return_24h))
    return VariantPrediction(direction=direction, probability=prob)


def baseline_news_sentiment(ctx: ScoringContext) -> VariantPrediction:
    """Weighted sentiment of attached articles. None if no articles."""
    if not ctx.article_impacts:
        return VariantPrediction(direction=None, probability=None)

    def _sign(d: str) -> float:
        if d == "YES":
            return 1.0
        if d == "NO":
            return -1.0
        return 0.0

    weighted = sum(_sign(a.direction) * a.source_weight for a in ctx.article_impacts)
    total_weight = sum(a.source_weight for a in ctx.article_impacts)
    if total_weight == 0:
        return VariantPrediction(direction=None, probability=None)

    sentiment = weighted / total_weight                     # in [-1, 1]
    prob = 1.0 / (1.0 + math.exp(-2.0 * sentiment))         # sigmoid spread
    direction = "BUY_YES" if sentiment > 0 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=prob)
```

- [ ] **Step 4: Register baselines at import time**

Replace `app/measurement/__init__.py` with:

```python
"""Measurement layer — baselines, variants, metrics.

Importing this module registers the four built-in baselines with the global
VariantRegistry singleton. The signal builder and backfill script rely on
that side-effect — keep this import order stable.
"""

from app.measurement.baselines import (
    baseline_market_price,
    baseline_momentum,
    baseline_news_sentiment,
    baseline_random,
)
from app.measurement.variant_registry import get_registry

_r = get_registry()

# Idempotency: re-import is a no-op (register_baseline raises on duplicate),
# so swallow the error if someone re-imports in a long-running worker.
for _name, _fn in [
    ("baseline_random", baseline_random),
    ("baseline_market_price", baseline_market_price),
    ("baseline_momentum", baseline_momentum),
    ("baseline_news_sentiment", baseline_news_sentiment),
]:
    if _name not in _r.baselines():
        _r.register_baseline(_name, _fn)
```

- [ ] **Step 5: Run baseline tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_baselines.py tests/unit/test_measurement_registry.py -v`
Expected: 15 passed (12 baseline + 4 registry, one of them may count differently — confirm all green).

- [ ] **Step 6: Smoke — registration happens on import**

Run: `docker compose exec -T app python -c "import app.measurement; from app.measurement.variant_registry import get_registry; print(sorted(get_registry().baselines().keys()))"`
Expected: `['baseline_market_price', 'baseline_momentum', 'baseline_news_sentiment', 'baseline_random']`

- [ ] **Step 7: Commit**

```bash
git add app/measurement/baselines.py app/measurement/__init__.py tests/unit/test_measurement_baselines.py
git commit -m "feat(measurement): 4 baselines (random, market_price, momentum, news_sentiment) + auto-register"
```

---

## Task 6: `pipeline.record_baselines` + `schedule_shadow_variants` stub

**Files:**
- Create: `app/measurement/pipeline.py`
- Create: `tests/unit/test_measurement_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_measurement_pipeline.py`:

```python
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.models import Event, Market, Signal, SignalPrediction
from app.measurement.pipeline import record_baselines, schedule_shadow_variants
from app.measurement.scoring_context import ArticleImpact, ScoringContext
from app.measurement.variant_registry import VariantPrediction, VariantRegistry


async def _seed_signal(session) -> int:
    session.add(Market(market_id="0xtestmkt", question="q", active=True))
    session.add(Event(id=1, title="e", status="active"))
    await session.flush()
    sig = Signal(event_id=1, market_id="0xtestmkt", signal_score=80,
                 direction="BUY_YES", market_price_at_signal=0.6)
    session.add(sig)
    await session.flush()
    return sig.id


def _ctx(signal_id: int) -> ScoringContext:
    return ScoringContext(
        signal_id=signal_id, market_id="0xtestmkt", event_id=1,
        market_price=0.6, market_price_24h_ago=0.5,
        article_impacts=(ArticleImpact(direction="YES", source_weight=0.8),),
        t0=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_record_baselines_inserts_signal_plus_all_baselines(
    async_db_factory,
):
    async with async_db_factory() as s:
        sid = await _seed_signal(s)
        reg = VariantRegistry()
        reg.register_baseline("b_fake", lambda c: VariantPrediction("BUY_YES", 0.7))

        # the "signal" variant is the production signal itself; pipeline pulls
        # direction + impact_strength from the Signal row.
        n = await record_baselines(s, signal_id=sid, ctx=_ctx(sid), registry=reg)
        await s.commit()

        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sid)
            )
        ).scalars().all()
        variants = {r.variant for r in rows}
        assert variants == {"signal", "b_fake"}
        assert n == 2


@pytest.mark.asyncio
async def test_record_baselines_inserts_rows_even_when_baseline_returns_none(
    async_db_factory,
):
    async with async_db_factory() as s:
        sid = await _seed_signal(s)
        reg = VariantRegistry()
        reg.register_baseline("b_missing", lambda c: VariantPrediction(None, None))
        await record_baselines(s, signal_id=sid, ctx=_ctx(sid), registry=reg)
        await s.commit()

        row = (
            await s.execute(
                select(SignalPrediction).where(
                    SignalPrediction.signal_id == sid,
                    SignalPrediction.variant == "b_missing",
                )
            )
        ).scalar_one()
        assert row.predicted_direction is None
        assert row.predicted_probability is None


@pytest.mark.asyncio
async def test_record_baselines_is_idempotent_per_signal_variant(async_db_factory):
    """Second call with same signal+variant is a no-op — unique constraint catches it."""
    async with async_db_factory() as s:
        sid = await _seed_signal(s)
        reg = VariantRegistry()
        reg.register_baseline("b_x", lambda c: VariantPrediction("BUY_YES", 0.7))
        await record_baselines(s, signal_id=sid, ctx=_ctx(sid), registry=reg)
        await s.commit()

        # second call: pipeline must detect conflict and not raise
        await record_baselines(s, signal_id=sid, ctx=_ctx(sid), registry=reg)
        await s.commit()

        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sid)
            )
        ).scalars().all()
        # 1 'signal' + 1 'b_x', no duplicates
        assert len(rows) == 2


def test_schedule_shadow_variants_is_a_noop_stub():
    """Task 6 ships the hook; chantier #3 fills the shadow registry."""
    # Must not raise, must not require a signal to exist.
    schedule_shadow_variants(999_999)
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_pipeline.py -v`
Expected: ImportError on `app.measurement.pipeline`.

- [ ] **Step 3: Implement `pipeline.py`**

```python
"""Measurement pipeline — glue between signal persistence, baselines, and DB.

`record_baselines` runs inside the signal transaction (same session). It
inserts one row per registered baseline plus one 'signal' row for the
production prediction. Uses ON CONFLICT DO NOTHING so a retry during backfill
is safe.

`record_prediction_resolution` is the counterpart called from the outcomes
worker when a market resolves.

`schedule_shadow_variants` is a stub — chantiers #3/#4 will register shadow
variants that run async via Celery.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Signal, SignalPrediction
from app.measurement.scoring_context import ScoringContext
from app.measurement.variant_registry import VariantRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_baselines(
    session: "AsyncSession",
    *,
    signal_id: int,
    ctx: ScoringContext,
    registry: VariantRegistry,
) -> int:
    """Insert one row for the 'signal' variant + one per registered baseline.

    Caller is responsible for committing. Conflicts on (signal_id, variant)
    are swallowed silently — backfill retries are idempotent.
    """
    # production 'signal' row — use the Signal's own direction + score as the
    # implied probability. We store signal_strength/100 as prob; if null, fall
    # back to 0.5.
    sig = (
        await session.execute(select(Signal).where(Signal.id == signal_id))
    ).scalar_one()
    signal_prob = (
        float(sig.signal_strength) / 100.0
        if sig.signal_strength is not None
        else 0.5
    )

    rows = [
        {
            "signal_id": signal_id,
            "variant": "signal",
            "predicted_direction": sig.direction,
            "predicted_probability": signal_prob,
        }
    ]
    for name, fn in registry.baselines().items():
        pred = fn(ctx)
        rows.append(
            {
                "signal_id": signal_id,
                "variant": name,
                "predicted_direction": pred.direction,
                "predicted_probability": pred.probability,
            }
        )

    stmt = pg_insert(SignalPrediction).values(rows).on_conflict_do_nothing(
        index_elements=["signal_id", "variant"]
    )
    result = await session.execute(stmt)
    # result.rowcount is accurate on PG even with ON CONFLICT DO NOTHING
    return int(result.rowcount or 0)


def schedule_shadow_variants(signal_id: int) -> None:
    """Fire-and-forget shadow variant dispatch. Stub until chantier #3."""
    logger.debug("schedule_shadow_variants(signal_id=%s) — no shadows registered", signal_id)
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_pipeline.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/measurement/pipeline.py tests/unit/test_measurement_pipeline.py
git commit -m "feat(measurement): record_baselines with ON CONFLICT + shadow stub"
```

---

## Task 7: Metric helpers — Wilson CI95, Brier, P&L, aggregators

**Files:**
- Create: `app/measurement/metrics.py`
- Create: `tests/unit/test_measurement_metrics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_measurement_metrics.py`:

```python
import pytest

from app.measurement.metrics import (
    brier_from_outcome,
    simulated_pnl_eur,
    wilson_ci95,
)


# ── Wilson CI95 ──────────────────────────────────────────────────────
def test_wilson_ci95_center_when_full_agreement():
    lo, hi = wilson_ci95(n=100, k=50)
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61


def test_wilson_ci95_k_zero():
    lo, hi = wilson_ci95(n=10, k=0)
    assert lo == pytest.approx(0.0, abs=1e-6)
    assert 0 < hi < 0.31


def test_wilson_ci95_k_equals_n():
    lo, hi = wilson_ci95(n=10, k=10)
    assert hi == pytest.approx(1.0, abs=1e-6)
    assert 0.69 < lo < 1.0


def test_wilson_ci95_n_zero_returns_zero_one():
    lo, hi = wilson_ci95(n=0, k=0)
    assert lo == 0.0 and hi == 1.0


def test_wilson_ci95_small_sample_matches_known_fixture():
    # n=24, k=11 → published Wilson CI95 ≈ (0.268, 0.661)
    lo, hi = wilson_ci95(n=24, k=11)
    assert lo == pytest.approx(0.268, abs=0.005)
    assert hi == pytest.approx(0.661, abs=0.005)


# ── Brier ────────────────────────────────────────────────────────────
def test_brier_yes_won_high_confidence():
    # said P(YES) = 0.85, YES won → brier = (0.85 - 1)^2 = 0.0225
    assert brier_from_outcome(probability=0.85, resolved_binary=1) == pytest.approx(0.0225)


def test_brier_no_won_high_confidence():
    # said P(YES) = 0.1, NO won → brier = (0.1 - 0)^2 = 0.01
    assert brier_from_outcome(probability=0.1, resolved_binary=0) == pytest.approx(0.01)


def test_brier_none_when_ambiguous():
    assert brier_from_outcome(probability=0.5, resolved_binary=None) is None


# ── P&L ──────────────────────────────────────────────────────────────
def test_pnl_buy_yes_winning():
    # stake 10€, BUY_YES at 0.6, resolved at 1.0 → 10 * (1.0 - 0.6) = 4€
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=1.0
    ) == pytest.approx(4.0)


def test_pnl_buy_yes_losing():
    # stake 10€, BUY_YES at 0.6, resolved at 0.0 → 10 * (0 - 0.6) = -6€
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=0.0
    ) == pytest.approx(-6.0)


def test_pnl_buy_no_winning():
    # BUY_NO at 0.3, resolved at 0 → 10 * (0.3 - 0) = 3€
    assert simulated_pnl_eur(
        direction="BUY_NO", probability=0.3, price_resolved=0.0
    ) == pytest.approx(3.0)


def test_pnl_partial_resolution_captured():
    # BUY_YES at 0.6, resolved at 0.7 → 10 * (0.7 - 0.6) = 1€
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=0.7
    ) == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_metrics.py -v`
Expected: ImportError on `app.measurement.metrics`.

- [ ] **Step 3: Implement `metrics.py`**

```python
"""Pure math helpers used by the resolution hook + admin aggregation endpoint.

No SQL here — these operate on already-fetched numbers. Keeps the statistics
testable in isolation and identical whether called from the API, the CLI, or
the Celery worker.
"""

from __future__ import annotations

import math


# Z-score for 95% two-sided confidence (1.959963984540054)
_Z95 = 1.959963984540054


def wilson_ci95(n: int, k: int) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n at 95% confidence.

    Stable for small n (unlike the normal approximation). Edge cases:
    - n = 0 → (0.0, 1.0) (no information)
    - k = 0 → lower bound is exactly 0
    - k = n → upper bound is exactly 1
    """
    if n <= 0:
        return (0.0, 1.0)
    p_hat = k / n
    z2 = _Z95 * _Z95
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    margin = (_Z95 / denom) * math.sqrt(
        (p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def brier_from_outcome(probability: float, resolved_binary: int | None) -> float | None:
    """Brier = (prob - outcome)^2. Returns None for ambiguous resolutions.

    We only compute Brier on binary resolutions (>=0.95 → 1, <=0.05 → 0). Mid-
    range resolutions don't map to a binary label, so Brier is undefined. See
    spec §"Metric definitions — which outcomes count".
    """
    if resolved_binary is None:
        return None
    return (probability - resolved_binary) ** 2


def simulated_pnl_eur(
    *, direction: str, probability: float, price_resolved: float, stake_eur: float = 10.0
) -> float:
    """Synthetic P&L with stake 10€, zero fees, zero slippage.

    For BUY_YES: pnl = stake * (price_resolved - probability)
    For BUY_NO:  pnl = stake * (probability - price_resolved)

    Uses the RAW resolved price (float, not binary) so partial resolutions at
    e.g. 0.70 still produce a signed P&L number.
    """
    if direction == "BUY_YES":
        return stake_eur * (price_resolved - probability)
    # BUY_NO
    return stake_eur * (probability - price_resolved)
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_metrics.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add app/measurement/metrics.py tests/unit/test_measurement_metrics.py
git commit -m "feat(measurement): Wilson CI95, Brier, simulated P&L helpers"
```

---

## Task 8: Hook `record_baselines` into `_persist_signal`

**Files:**
- Modify: `app/signal/signal_builder.py` (the async module-level `_persist_signal`, lines ~326–371)
- Create: `tests/integration/test_signal_predictions_hook.py`

**Context:** the actual hook point is not `SignalBuilder.build_signal()` but the module-level `_persist_signal` in `app/signal/signal_builder.py`. It opens a session, adds the `Signal`, updates `EventNewsLink`, and commits. Our hook runs after `s.add(sig)` + `s.flush()` (so `sig.id` is populated), before the final `s.commit()`.

- [ ] **Step 1: Build a `ScoringContext.from_signal(...)` helper**

Append to `app/measurement/scoring_context.py`:

```python
from typing import Any


async def build_scoring_context(
    *,
    signal_id: int,
    market_id: str,
    event_id: int | None,
    market_price: float,
    articles: list[dict[str, Any]] | None,
    t0: datetime,
    market_price_24h_ago: float | None = None,
) -> "ScoringContext":
    """Assemble a ScoringContext from whatever the signal builder has on hand.

    `market_price_24h_ago` is an explicit input — chantier #1 ships with None
    (graceful degradation; momentum becomes a no-op). A future chantier can
    wire it to Polymarket /prices-history without touching the scoring flow.

    `articles` is the list of raw article dicts the builder already holds.
    Only items with a direction hint + source_weight participate in
    news_sentiment; the rest are ignored.
    """
    impacts: list[ArticleImpact] = []
    for art in (articles or []):
        d = (art.get("direction_hint") or art.get("direction") or "NEUTRAL").upper()
        if d not in ("YES", "NO", "NEUTRAL"):
            d = "NEUTRAL"
        w_raw = art.get("source_weight")
        try:
            w = float(w_raw) if w_raw is not None else 0.5
        except (TypeError, ValueError):
            w = 0.5
        impacts.append(ArticleImpact(direction=d, source_weight=w))

    return ScoringContext(
        signal_id=signal_id,
        market_id=market_id,
        event_id=event_id,
        market_price=market_price,
        market_price_24h_ago=market_price_24h_ago,
        article_impacts=tuple(impacts),
        t0=t0,
    )
```

- [ ] **Step 2: Write the failing integration test**

Create `tests/integration/test_signal_predictions_hook.py`:

```python
"""E2E: _persist_signal writes the 4 baseline + 1 signal rows inside the
same transaction."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.mark.asyncio
async def test_persist_signal_writes_all_variant_rows(async_db_factory):
    from app.signal.signal_builder import _persist_signal

    async with async_db_factory() as s:
        s.add(Market(market_id="0xintg", question="q", active=True))
        s.add(Event(id=101, title="e", status="active"))
        await s.commit()

    assembled = {
        "event_id": 101,
        "market_id": "0xintg",
        "market_price": 0.65,
        "reasoning": "because reasons",
        "llm_model_version": "gpt-4o-test",
        "source_tier_mix": {"tier1": 2},
        "direction_recommendation": "YES",
        "impact_score": 0.8,
        "confidence": 0.7,
        "article_excerpts": [],
    }
    articles = [
        {"news_clean_id": 1, "direction_hint": "YES", "source_weight": 0.9},
    ]
    await _persist_signal(assembled, articles)

    async with async_db_factory() as s:
        sig = (
            await s.execute(select(Signal).where(Signal.market_id == "0xintg"))
        ).scalar_one()
        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sig.id)
            )
        ).scalars().all()
        variants = {r.variant for r in rows}
        assert variants == {
            "signal",
            "baseline_random",
            "baseline_market_price",
            "baseline_momentum",
            "baseline_news_sentiment",
        }
        # Market-price baseline probability mirrors the market price passed in
        mp = next(r for r in rows if r.variant == "baseline_market_price")
        assert float(mp.predicted_probability) == pytest.approx(0.65, abs=1e-4)
        # Momentum is expected None (no 24h price in ctx)
        mom = next(r for r in rows if r.variant == "baseline_momentum")
        assert mom.predicted_direction is None
        assert mom.predicted_probability is None
```

- [ ] **Step 3: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_signal_predictions_hook.py -v`
Expected: fails — no baseline rows exist because hook not yet installed.

- [ ] **Step 4: Install the hook**

Edit `app/signal/signal_builder.py::_persist_signal` (around line 345-371). Replace the final block:

```python
    session_factory = get_session_factory()
    async with session_factory() as s:
        sig = Signal(
            event_id=assembled["event_id"],
            market_id=assembled["market_id"],
            signal_score=float(assembled.get("impact_score") or 0.0) * 100.0,
            direction=db_direction,
            market_price_at_signal=assembled.get("market_price"),
            reasoning=assembled["reasoning"],
            llm_model_version=assembled["llm_model_version"],
            source_tier_mix=assembled["source_tier_mix"],
        )
        s.add(sig)
        for exc in assembled["article_excerpts"]:
            result = await s.execute(
                update(EventNewsLink)
                .where(
                    EventNewsLink.event_id == assembled["event_id"],
                    EventNewsLink.clean_id == exc["news_clean_id"],
                )
                .values(key_excerpt=exc["excerpt"], relevance_score=exc["relevance"])
            )
            if result.rowcount == 0:
                logger.warning(
                    "persist_signal: no EventNewsLink matched event_id=%s clean_id=%s — excerpt dropped",
                    assembled["event_id"], exc["news_clean_id"],
                )
        await s.commit()
```

with:

```python
    import app.measurement  # noqa: F401  (side-effect: registers baselines)
    from datetime import datetime, timezone
    from app.measurement.pipeline import record_baselines, schedule_shadow_variants
    from app.measurement.scoring_context import build_scoring_context
    from app.measurement.variant_registry import get_registry

    session_factory = get_session_factory()
    async with session_factory() as s:
        sig = Signal(
            event_id=assembled["event_id"],
            market_id=assembled["market_id"],
            signal_score=float(assembled.get("impact_score") or 0.0) * 100.0,
            direction=db_direction,
            market_price_at_signal=assembled.get("market_price"),
            reasoning=assembled["reasoning"],
            llm_model_version=assembled["llm_model_version"],
            source_tier_mix=assembled["source_tier_mix"],
        )
        s.add(sig)
        await s.flush()  # populate sig.id for the measurement FK

        for exc in assembled["article_excerpts"]:
            result = await s.execute(
                update(EventNewsLink)
                .where(
                    EventNewsLink.event_id == assembled["event_id"],
                    EventNewsLink.clean_id == exc["news_clean_id"],
                )
                .values(key_excerpt=exc["excerpt"], relevance_score=exc["relevance"])
            )
            if result.rowcount == 0:
                logger.warning(
                    "persist_signal: no EventNewsLink matched event_id=%s clean_id=%s — excerpt dropped",
                    assembled["event_id"], exc["news_clean_id"],
                )

        ctx = await build_scoring_context(
            signal_id=sig.id,
            market_id=sig.market_id,
            event_id=sig.event_id,
            market_price=float(sig.market_price_at_signal or 0.0),
            articles=articles,
            t0=datetime.now(timezone.utc),
            market_price_24h_ago=None,  # wired by a future chantier
        )
        try:
            await record_baselines(
                s, signal_id=sig.id, ctx=ctx, registry=get_registry()
            )
        except Exception:
            logger.exception(
                "measurement.record_baselines failed signal_id=%s — skipping; signal itself will still commit",
                sig.id,
            )
        await s.commit()

    schedule_shadow_variants(sig.id)  # stub for chantier #3
```

- [ ] **Step 5: Run integration test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_signal_predictions_hook.py -v`
Expected: 1 passed.

- [ ] **Step 6: Run full measurement test suite**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_* tests/integration/test_signal_predictions_hook.py -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add app/signal/signal_builder.py app/measurement/scoring_context.py tests/integration/test_signal_predictions_hook.py
git commit -m "feat(measurement): hook record_baselines into _persist_signal"
```

---

## Task 9: Resolution hook in `check_resolved_markets`

**Files:**
- Modify: `app/workers/tasks_outcomes.py` (line ~245–264, the per-signal resolution block)
- Modify: `app/measurement/pipeline.py` (add `record_prediction_resolution`)
- Create: `tests/integration/test_resolution_hook.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_resolution_hook.py`:

```python
"""E2E: when a market resolves, all non-null variant rows for its signals
get their direction_correct / brier / P&L / resolved_at filled in."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.mark.asyncio
async def test_record_resolution_fills_all_variants(async_db_factory):
    from app.measurement.pipeline import record_prediction_resolution

    async with async_db_factory() as s:
        s.add(Market(market_id="0xres", question="q", active=True))
        s.add(Event(id=201, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=201, market_id="0xres", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6, signal_strength=70.0,
        )
        s.add(sig)
        await s.flush()

        s.add(SignalPrediction(
            signal_id=sig.id, variant="signal",
            predicted_direction="BUY_YES", predicted_probability=0.7,
        ))
        s.add(SignalPrediction(
            signal_id=sig.id, variant="baseline_random",
            predicted_direction="BUY_NO", predicted_probability=0.5,
        ))
        s.add(SignalPrediction(
            signal_id=sig.id, variant="baseline_momentum",
            predicted_direction=None, predicted_probability=None,
        ))
        await s.commit()
        sid = sig.id

    # Market resolved at 1.0 (YES won, clean binary)
    async with async_db_factory() as s:
        await record_prediction_resolution(s, signal_id=sid, price_resolved=1.0)
        await s.commit()

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sid)
            )
        ).scalars().all()
        by = {r.variant: r for r in rows}

        # 'signal' said BUY_YES at 0.7, resolved 1.0
        assert by["signal"].direction_correct is True
        assert float(by["signal"].brier_score) == pytest.approx((0.7 - 1.0) ** 2, abs=1e-4)
        assert float(by["signal"].simulated_pnl_eur) == pytest.approx(3.0, abs=1e-2)
        assert by["signal"].resolved_at is not None

        # baseline_random said BUY_NO at 0.5, resolved 1.0 → wrong
        assert by["baseline_random"].direction_correct is False

        # baseline_momentum had NULL direction → skipped
        assert by["baseline_momentum"].direction_correct is None
        assert by["baseline_momentum"].resolved_at is None


@pytest.mark.asyncio
async def test_record_resolution_brier_null_on_ambiguous(async_db_factory):
    from app.measurement.pipeline import record_prediction_resolution

    async with async_db_factory() as s:
        s.add(Market(market_id="0xamb", question="q", active=True))
        s.add(Event(id=202, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=202, market_id="0xamb", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.flush()
        s.add(SignalPrediction(
            signal_id=sig.id, variant="signal",
            predicted_direction="BUY_YES", predicted_probability=0.7,
        ))
        await s.commit()
        sid = sig.id

    # Resolves at 0.7 — ambiguous (between 0.05 and 0.95)
    async with async_db_factory() as s:
        await record_prediction_resolution(s, signal_id=sid, price_resolved=0.7)
        await s.commit()

    async with async_db_factory() as s:
        row = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sid)
            )
        ).scalar_one()
        assert row.brier_score is None
        # P&L still computed from raw price: 10 * (0.7 - 0.7) = 0
        assert float(row.simulated_pnl_eur) == pytest.approx(0.0, abs=1e-2)
        assert row.resolved_at is not None
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_resolution_hook.py -v`
Expected: ImportError on `record_prediction_resolution`.

- [ ] **Step 3: Implement `record_prediction_resolution` in `pipeline.py`**

Append to `app/measurement/pipeline.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import update


def _binary_from_resolved(price_resolved: float) -> int | None:
    if price_resolved >= 0.95:
        return 1
    if price_resolved <= 0.05:
        return 0
    return None


async def record_prediction_resolution(
    session: "AsyncSession",
    *,
    signal_id: int,
    price_resolved: float,
) -> int:
    """Fill direction_correct + brier + P&L + resolved_at for every variant
    of this signal that has a non-null direction and is still unresolved.

    Returns the count of rows updated. Idempotent (the WHERE clause skips rows
    that already have resolved_at set).
    """
    resolved_binary = _binary_from_resolved(price_resolved)
    expected_direction = "BUY_YES" if price_resolved >= 0.5 else "BUY_NO"
    now = datetime.now(timezone.utc)

    rows = (
        await session.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.predicted_direction.is_not(None),
                SignalPrediction.resolved_at.is_(None),
            )
        )
    ).scalars().all()

    count = 0
    for r in rows:
        prob = float(r.predicted_probability) if r.predicted_probability is not None else 0.5
        r.direction_correct = (r.predicted_direction == expected_direction)
        r.brier_score = (
            None if resolved_binary is None else (prob - resolved_binary) ** 2
        )
        if r.predicted_direction == "BUY_YES":
            r.simulated_pnl_eur = 10.0 * (price_resolved - prob)
        else:  # BUY_NO
            r.simulated_pnl_eur = 10.0 * (prob - price_resolved)
        r.resolved_at = now
        count += 1
    return count
```

- [ ] **Step 4: Run test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_resolution_hook.py -v`
Expected: 2 passed.

- [ ] **Step 5: Wire the hook into `check_resolved_markets`**

In `app/workers/tasks_outcomes.py`, inside `_check_resolved_async`, right after `outcome.outcome_label = ...` block (around line 262, before `resolved += 1`), insert:

```python
                # Measurement: refresh all variant rows for this signal.
                try:
                    from app.measurement.pipeline import record_prediction_resolution
                    await record_prediction_resolution(
                        session, signal_id=signal.id, price_resolved=float(final_price)
                    )
                except Exception:
                    logger.exception(
                        "measurement.record_prediction_resolution failed signal_id=%s — skipping",
                        signal.id,
                    )
```

- [ ] **Step 6: Re-run integration + unit tests**

Run: `docker compose exec -T app python -m pytest tests/integration/test_resolution_hook.py tests/unit/test_measurement_* -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add app/measurement/pipeline.py app/workers/tasks_outcomes.py tests/integration/test_resolution_hook.py
git commit -m "feat(measurement): resolution hook — refresh variant rows when market closes"
```

---

## Task 10: Admin gate — `require_admin` dependency via `ADMIN_EMAILS`

**Files:**
- Modify: `app/core/config.py` (add `admin_emails` setting)
- Create: `app/api/deps/__init__.py` (empty)
- Create: `app/api/deps/admin.py`
- Create: `tests/unit/test_admin_require_admin.py`

**Context:** `UserProfile` has no `role` column. We use an env-var allowlist — simple, reversible, no migration. `ADMIN_EMAILS=a@b.com,c@d.com` in `.env` promotes those accounts.

- [ ] **Step 1: Add `admin_emails` to Settings**

Edit `app/core/config.py`, near the `# ── Auth / Security ──` block (around line 42):

```python
    # Comma-separated list of emails allowed to hit /api/admin/* endpoints.
    # Not a role column — temporary until we need >1 permission tier.
    admin_emails: str = Field(default="")
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_admin_require_admin.py`:

```python
import pytest
from fastapi import HTTPException

from app.api.deps.admin import _parse_admin_emails, _is_admin_email


def test_parse_admin_emails_splits_and_lowercases():
    assert _parse_admin_emails("A@x.com, b@y.com,, C@z.com") == {
        "a@x.com",
        "b@y.com",
        "c@z.com",
    }


def test_parse_admin_emails_empty_string():
    assert _parse_admin_emails("") == set()


def test_is_admin_email_matches_case_insensitively():
    assert _is_admin_email("Admin@Example.com", "admin@example.com,other@x.com") is True


def test_is_admin_email_rejects_non_member():
    assert _is_admin_email("nope@x.com", "a@x.com,b@y.com") is False


def test_is_admin_email_handles_none_email():
    assert _is_admin_email(None, "a@x.com") is False
```

- [ ] **Step 3: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_admin_require_admin.py -v`
Expected: ImportError on `app.api.deps.admin`.

- [ ] **Step 4: Implement `require_admin`**

Create `app/api/deps/__init__.py` (empty file with `"""API dependency helpers."""` docstring).

Create `app/api/deps/admin.py`:

```python
"""Admin gate.

`require_admin` is a FastAPI dependency that rejects non-admin callers with
403. Admins are identified by the `ADMIN_EMAILS` env var — a comma-separated
allowlist. This is intentionally low-tech: we have no role column yet, and
adding one for a single permission tier is YAGNI. Migrate to a role table
if/when we grow a second tier.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.models import UserProfile


def _parse_admin_emails(raw: str) -> set[str]:
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def _is_admin_email(email: str | None, raw_list: str) -> bool:
    if not email:
        return False
    return email.strip().lower() in _parse_admin_emails(raw_list)


async def require_admin(
    user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    settings = get_settings()
    if not _is_admin_email(user.email, settings.admin_emails):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

- [ ] **Step 5: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_admin_require_admin.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py app/api/deps/ tests/unit/test_admin_require_admin.py
git commit -m "feat(admin): ADMIN_EMAILS allowlist + require_admin dependency"
```

---

## Task 11: Admin API — `/api/admin/metrics/variants`

**Files:**
- Create: `app/api/schemas/admin_metrics.py`
- Create: `app/api/routes/admin_metrics.py`
- Modify: `app/api/main.py` (register router)
- Modify: `tests/integration/conftest.py` (extend `auth_headers_for_user` to accept an `email` kwarg)
- Create: `tests/integration/test_admin_metrics_variants.py`

**Pre-task — extend the fixture**

`tests/integration/conftest.py::auth_headers_for_user._factory` currently generates a random email via `uuid.uuid4()`. The admin tests need to control the email so it matches `ADMIN_EMAILS`. Edit the factory signature to accept an optional `email` kwarg:

```python
    async def _factory(email: str | None = None) -> tuple[int, dict[str, str]]:
        if email is None:
            email = f"trade-test-{uuid.uuid4().hex[:10]}@example.com"
        safe_addr = "0x" + uuid.uuid4().hex[:40].ljust(40, "a")
        # ... rest unchanged
```

**Pre-task — handle `get_settings()` lru_cache**

`app.core.config.get_settings` is `@lru_cache`d. Setting `ADMIN_EMAILS` via `monkeypatch.setenv` has no effect unless we clear the cache. In every admin integration test that mutates env, call `get_settings.cache_clear()` after `monkeypatch.setenv`, and again at teardown. The test code below already does this.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_admin_metrics_variants.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.config import get_settings
from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.fixture
def _clear_settings_cache():
    """Required around any test that mutates ADMIN_EMAILS via monkeypatch."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_variants_endpoint_rejects_non_admin(auth_headers_for_user):
    _uid, headers = await auth_headers_for_user(email="plain@x.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/admin/metrics/variants?window=30d", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_variants_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/admin/metrics/variants?window=30d")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_variants_endpoint_returns_aggregates(
    async_db_factory, auth_headers_for_user, monkeypatch, _clear_settings_cache
):
    """Seed 10 resolved predictions across 2 variants, verify winrate + Wilson CI."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin@x.com")
    get_settings.cache_clear()  # re-read env

    _uid, headers = await auth_headers_for_user(email="admin@x.com")

    # Seed: 1 market, 10 signals, each with 'signal' and 'baseline_market_price'
    # variants. 'signal' wins 7/10; 'baseline' wins 5/10. All resolved cleanly.
    now = datetime.now(timezone.utc)
    async with async_db_factory() as s:
        s.add(Market(market_id="0xadm", question="q", active=True))
        s.add(Event(id=301, title="e", status="active"))
        await s.flush()
        for i in range(10):
            sig = Signal(
                event_id=301, market_id="0xadm", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
            )
            s.add(sig)
            await s.flush()
            s.add(SignalPrediction(
                signal_id=sig.id, variant="signal",
                predicted_direction="BUY_YES", predicted_probability=0.7,
                direction_correct=(i < 7), brier_score=(0.3 if i < 7 else 0.49),
                simulated_pnl_eur=(3.0 if i < 7 else -6.0),
                resolved_at=now - timedelta(days=1),
            ))
            s.add(SignalPrediction(
                signal_id=sig.id, variant="baseline_market_price",
                predicted_direction="BUY_YES", predicted_probability=0.6,
                direction_correct=(i < 5), brier_score=(0.16 if i < 5 else 0.36),
                simulated_pnl_eur=(4.0 if i < 5 else -6.0),
                resolved_at=now - timedelta(days=1),
            ))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/admin/metrics/variants?window=30d", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window"] == "30d"
    variants = {v["variant"]: v for v in body["variants"]}
    assert "signal" in variants
    assert "baseline_market_price" in variants

    sig_v = variants["signal"]
    assert sig_v["n"] == 10
    assert sig_v["winrate"] == pytest.approx(0.7, abs=1e-4)
    assert 0.0 <= sig_v["winrate_ci95_low"] <= sig_v["winrate"] <= sig_v["winrate_ci95_high"] <= 1.0
    assert sig_v["pnl_total_eur"] == pytest.approx(7 * 3.0 + 3 * -6.0, abs=1e-2)
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_admin_metrics_variants.py -v`
Expected: 404 or ImportError — router not registered.

- [ ] **Step 3: Create response schemas**

Create `app/api/schemas/admin_metrics.py`:

```python
"""Pydantic response schemas for /api/admin/metrics/*."""

from __future__ import annotations

from pydantic import BaseModel


class VariantAggregate(BaseModel):
    variant: str
    n: int                        # resolved rows with non-null direction
    n_coverage: int               # all rows including NULL direction (coverage)
    winrate: float | None
    winrate_ci95_low: float | None
    winrate_ci95_high: float | None
    brier: float | None
    brier_n: int                  # count of rows where brier was defined (binary only)
    pnl_per_trade_eur: float | None
    pnl_total_eur: float | None


class VariantsResponse(BaseModel):
    window: str
    as_of: str
    variants: list[VariantAggregate]


class RollingPoint(BaseModel):
    date: str
    variant: str
    n_cumulative: int
    winrate_cumulative: float | None


class RollingResponse(BaseModel):
    window: str
    step: str
    series: list[RollingPoint]
```

- [ ] **Step 4: Implement the route**

Create `app/api/routes/admin_metrics.py`:

```python
"""Admin metrics — aggregated read endpoints over signal_predictions.

These endpoints power the CLI (`scripts/report_metrics.py`) and, later, an
admin FE page. Read-only, expensive aggregations are server-side so the client
stays dumb.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps.admin import require_admin
from app.api.schemas.admin_metrics import VariantAggregate, VariantsResponse
from app.db.database import get_session_factory
from app.db.models import SignalPrediction
from app.measurement.metrics import wilson_ci95

router = APIRouter(prefix="/admin/metrics", tags=["admin-metrics"])


def _window_to_cutoff(window: str, now: datetime) -> datetime:
    """'30d' → now - 30 days. Accept plain digits + 'd' suffix only (YAGNI)."""
    if not window.endswith("d"):
        raise ValueError(f"unsupported window: {window!r}")
    try:
        days = int(window[:-1])
    except ValueError as e:
        raise ValueError(f"unsupported window: {window!r}") from e
    return now - timedelta(days=days)


@router.get("/variants", response_model=VariantsResponse)
async def get_variants(
    window: str = Query("30d"),
    _admin=Depends(require_admin),
) -> VariantsResponse:
    now = datetime.now(timezone.utc)
    cutoff = _window_to_cutoff(window, now)

    factory = get_session_factory()
    async with factory() as s:
        # One query per variant over rows in [cutoff, now].
        variants_stmt = (
            select(SignalPrediction.variant)
            .where(SignalPrediction.created_at >= cutoff)
            .group_by(SignalPrediction.variant)
        )
        names = [r[0] for r in (await s.execute(variants_stmt)).all()]

        out: list[VariantAggregate] = []
        for name in names:
            rows = (
                await s.execute(
                    select(
                        SignalPrediction.direction_correct,
                        SignalPrediction.brier_score,
                        SignalPrediction.simulated_pnl_eur,
                        SignalPrediction.predicted_direction,
                        SignalPrediction.resolved_at,
                    ).where(
                        SignalPrediction.variant == name,
                        SignalPrediction.created_at >= cutoff,
                    )
                )
            ).all()

            n_coverage = len(rows)
            resolved = [r for r in rows if r.resolved_at is not None and r.predicted_direction is not None]
            n = len(resolved)
            if n == 0:
                out.append(VariantAggregate(
                    variant=name, n=0, n_coverage=n_coverage,
                    winrate=None, winrate_ci95_low=None, winrate_ci95_high=None,
                    brier=None, brier_n=0,
                    pnl_per_trade_eur=None, pnl_total_eur=None,
                ))
                continue

            wins = sum(1 for r in resolved if r.direction_correct)
            winrate = wins / n
            lo, hi = wilson_ci95(n=n, k=wins)

            briers = [float(r.brier_score) for r in resolved if r.brier_score is not None]
            pnls = [float(r.simulated_pnl_eur) for r in resolved if r.simulated_pnl_eur is not None]

            out.append(VariantAggregate(
                variant=name, n=n, n_coverage=n_coverage,
                winrate=winrate, winrate_ci95_low=lo, winrate_ci95_high=hi,
                brier=(mean(briers) if briers else None),
                brier_n=len(briers),
                pnl_per_trade_eur=(mean(pnls) if pnls else None),
                pnl_total_eur=(sum(pnls) if pnls else None),
            ))

        # Deterministic order: production 'signal' first, then baselines alphabetical.
        out.sort(key=lambda v: (0 if v.variant == "signal" else 1, v.variant))

        return VariantsResponse(
            window=window,
            as_of=now.isoformat(),
            variants=out,
        )
```

- [ ] **Step 5: Register router in `app/api/main.py`**

Find the other `include_router` calls and add:

```python
from app.api.routes.admin_metrics import router as admin_metrics_router
app.include_router(admin_metrics_router, prefix="/api")
```

- [ ] **Step 6: Update `auth_headers_for_user` fixture if needed**

Verify `tests/conftest.py::auth_headers_for_user` accepts an `email` kwarg — if not, extend it. (Check first.)

Run: `docker compose exec -T app python -m pytest tests/integration/test_admin_metrics_variants.py::test_variants_endpoint_requires_auth -v`
Expected: 1 passed (this test doesn't need the email kwarg).

Then the admin test:

Run: `docker compose exec -T app python -m pytest tests/integration/test_admin_metrics_variants.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add app/api/routes/admin_metrics.py app/api/schemas/admin_metrics.py app/api/main.py tests/integration/test_admin_metrics_variants.py
git commit -m "feat(admin-metrics): GET /api/admin/metrics/variants with Wilson CI"
```

---

## Task 12: Admin API — `/api/admin/metrics/variants/rolling`

**Files:**
- Modify: `app/api/routes/admin_metrics.py`
- Create: `tests/integration/test_admin_metrics_rolling.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_admin_metrics_rolling.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.config import get_settings
from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rolling_returns_per_day_series(
    async_db_factory, auth_headers_for_user, monkeypatch, _clear_settings_cache
):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@x.com")
    get_settings.cache_clear()

    _uid, headers = await auth_headers_for_user(email="admin@x.com")

    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

    async with async_db_factory() as s:
        s.add(Market(market_id="0xroll", question="q", active=True))
        s.add(Event(id=401, title="e", status="active"))
        await s.flush()
        # Three signals, one per day for the last 3 days. All 'signal' variant,
        # all correct.
        for d in (1, 2, 3):
            sig = Signal(
                event_id=401, market_id="0xroll", signal_score=80,
                direction="BUY_YES", market_price_at_signal=0.6,
            )
            s.add(sig)
            await s.flush()
            s.add(SignalPrediction(
                signal_id=sig.id, variant="signal",
                predicted_direction="BUY_YES", predicted_probability=0.7,
                direction_correct=True,
                created_at=now - timedelta(days=d),
                resolved_at=now - timedelta(days=d) + timedelta(hours=1),
            ))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get(
            "/api/admin/metrics/variants/rolling?window=30d&step=1d",
            headers=headers,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    series = body["series"]
    # All series entries refer to the 'signal' variant we seeded
    sig_pts = [p for p in series if p["variant"] == "signal"]
    assert len(sig_pts) >= 3
    # n_cumulative is monotonic non-decreasing
    ns = [p["n_cumulative"] for p in sig_pts]
    assert ns == sorted(ns)
    # Final cumulative n reaches 3
    assert max(ns) == 3
```

- [ ] **Step 2: Run test, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/integration/test_admin_metrics_rolling.py -v`
Expected: 404 (route not yet registered).

- [ ] **Step 3: Implement the route**

Append to `app/api/routes/admin_metrics.py`:

```python
from app.api.schemas.admin_metrics import RollingPoint, RollingResponse


@router.get("/variants/rolling", response_model=RollingResponse)
async def get_rolling(
    window: str = Query("30d"),
    step: str = Query("1d"),
    _admin=Depends(require_admin),
) -> RollingResponse:
    if step != "1d":
        # YAGNI — only 1d step for now.
        raise ValueError(f"unsupported step: {step!r}")

    now = datetime.now(timezone.utc)
    cutoff = _window_to_cutoff(window, now)

    factory = get_session_factory()
    async with factory() as s:
        rows = (
            await s.execute(
                select(
                    SignalPrediction.variant,
                    SignalPrediction.resolved_at,
                    SignalPrediction.direction_correct,
                ).where(
                    SignalPrediction.resolved_at >= cutoff,
                    SignalPrediction.resolved_at.is_not(None),
                    SignalPrediction.predicted_direction.is_not(None),
                ).order_by(SignalPrediction.resolved_at)
            )
        ).all()

    # Group by (variant, day), then compute cumulative per variant over time.
    by_variant: dict[str, list[tuple[datetime, bool]]] = {}
    for v, ra, correct in rows:
        by_variant.setdefault(v, []).append((ra, bool(correct)))

    series: list[RollingPoint] = []
    for v, events in by_variant.items():
        events.sort(key=lambda t: t[0])
        n_cum = 0
        w_cum = 0
        current_day = None
        for ra, correct in events:
            day = ra.date().isoformat()
            n_cum += 1
            if correct:
                w_cum += 1
            if day != current_day:
                current_day = day
            # One point per event; the CLI/FE can down-sample to 1 point/day by
            # taking the last entry per day.
        # Emit 1 point per day with the cumulative values as of end-of-day.
        # Re-scan to aggregate per day:
        agg: dict[str, tuple[int, int]] = {}
        n_run = 0
        w_run = 0
        for ra, correct in events:
            n_run += 1
            if correct:
                w_run += 1
            day = ra.date().isoformat()
            agg[day] = (n_run, w_run)  # overwrite; final value = end-of-day cumulative
        for day, (n_cum_d, w_cum_d) in sorted(agg.items()):
            series.append(RollingPoint(
                date=day,
                variant=v,
                n_cumulative=n_cum_d,
                winrate_cumulative=(w_cum_d / n_cum_d) if n_cum_d else None,
            ))

    return RollingResponse(window=window, step=step, series=series)
```

- [ ] **Step 4: Run test, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/integration/test_admin_metrics_rolling.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/admin_metrics.py tests/integration/test_admin_metrics_rolling.py
git commit -m "feat(admin-metrics): GET /api/admin/metrics/variants/rolling"
```

---

## Task 13: Backfill script — `scripts/backfill_signal_predictions.py`

**Files:**
- Create: `scripts/backfill_signal_predictions.py`
- Create: `tests/unit/test_backfill_signal_predictions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_backfill_signal_predictions.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import Event, Market, Signal, SignalOutcome, SignalPrediction


@pytest.mark.asyncio
async def test_backfill_creates_variant_rows_for_historical_signal(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    async with async_db_factory() as s:
        s.add(Market(market_id="0xbk1", question="q", active=True))
        s.add(Event(id=501, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=501, market_id="0xbk1", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
            signal_strength=70.0,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    stats = await backfill(dry_run=False, since=None, batch_size=100)
    assert stats["signals_processed"] >= 1

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sid)
            )
        ).scalars().all()
    variants = {r.variant for r in rows}
    assert variants == {
        "signal",
        "baseline_random",
        "baseline_market_price",
        "baseline_momentum",
        "baseline_news_sentiment",
    }


@pytest.mark.asyncio
async def test_backfill_is_idempotent(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    async with async_db_factory() as s:
        s.add(Market(market_id="0xbk2", question="q", active=True))
        s.add(Event(id=502, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=502, market_id="0xbk2", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()

    await backfill(dry_run=False, since=None, batch_size=100)
    await backfill(dry_run=False, since=None, batch_size=100)  # second run

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sig.id)
            )
        ).scalars().all()
    # Still exactly 5 rows, not 10
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_backfill_resolves_when_outcome_present(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    async with async_db_factory() as s:
        s.add(Market(market_id="0xbk3", question="q", active=True))
        s.add(Event(id=503, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=503, market_id="0xbk3", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.flush()
        s.add(SignalOutcome(signal_id=sig.id, price_resolved=1.0))
        await s.commit()
        sid = sig.id

    await backfill(dry_run=False, since=None, batch_size=100)

    async with async_db_factory() as s:
        sig_row = (
            await s.execute(
                select(SignalPrediction).where(
                    SignalPrediction.signal_id == sid,
                    SignalPrediction.variant == "signal",
                )
            )
        ).scalar_one()
    assert sig_row.resolved_at is not None
    assert sig_row.direction_correct is True


@pytest.mark.asyncio
async def test_backfill_dry_run_writes_nothing(async_db_factory):
    from scripts.backfill_signal_predictions import backfill

    async with async_db_factory() as s:
        s.add(Market(market_id="0xbk4", question="q", active=True))
        s.add(Event(id=504, title="e", status="active"))
        await s.flush()
        sig = Signal(
            event_id=504, market_id="0xbk4", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()

    stats = await backfill(dry_run=True, since=None, batch_size=100)

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalPrediction).where(SignalPrediction.signal_id == sig.id)
            )
        ).scalars().all()
    assert len(rows) == 0
    assert stats["dry_run"] is True
```

- [ ] **Step 2: Run tests, confirm failure**

Run: `docker compose exec -T app python -m pytest tests/unit/test_backfill_signal_predictions.py -v`
Expected: ImportError on `scripts.backfill_signal_predictions`.

- [ ] **Step 3: Implement the backfill**

Create `scripts/backfill_signal_predictions.py`:

```python
"""Backfill signal_predictions for historical signals.

For every Signal row, insert the 5 variant rows (signal + 4 baselines). If the
signal's market already has a SignalOutcome.price_resolved value, compute
direction_correct / brier / pnl / resolved_at immediately.

Idempotent — ON CONFLICT DO NOTHING means rerunning is safe. `--since` limits
to recent signals. `--dry-run` reports intent without writing.

Usage:
    docker compose exec app python -m scripts.backfill_signal_predictions
    docker compose exec app python -m scripts.backfill_signal_predictions --dry-run
    docker compose exec app python -m scripts.backfill_signal_predictions --since 2026-04-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

import app.measurement  # noqa: F401 — register baselines on import
from app.db.database import get_session_factory
from app.db.models import Signal, SignalOutcome, SignalPrediction
from app.measurement.pipeline import record_baselines, record_prediction_resolution
from app.measurement.scoring_context import build_scoring_context
from app.measurement.variant_registry import get_registry

logger = logging.getLogger(__name__)


async def backfill(
    *,
    dry_run: bool = False,
    since: datetime | None = None,
    batch_size: int = 100,
) -> dict:
    """Returns a stats dict including per-variant coverage counts."""
    factory = get_session_factory()
    registry = get_registry()

    stats = {
        "dry_run": dry_run,
        "signals_processed": 0,
        "predictions_inserted": 0,
        "resolutions_backfilled": 0,
        "coverage": defaultdict(int),
    }

    async with factory() as s:
        q = select(Signal).order_by(Signal.created_at)
        if since is not None:
            q = q.where(Signal.created_at >= since)
        signals = (await s.execute(q)).scalars().all()

    for batch_start in range(0, len(signals), batch_size):
        batch = signals[batch_start : batch_start + batch_size]
        async with factory() as s:
            for sig in batch:
                stats["signals_processed"] += 1

                ctx = await build_scoring_context(
                    signal_id=sig.id,
                    market_id=sig.market_id,
                    event_id=sig.event_id,
                    market_price=float(sig.market_price_at_signal or 0.5),
                    articles=None,  # historical articles not reconstructed
                    t0=sig.created_at or datetime.now(timezone.utc),
                    market_price_24h_ago=None,  # no price history at backfill time
                )

                if dry_run:
                    # count coverage intent
                    for name in ("signal",) + tuple(registry.baselines().keys()):
                        stats["coverage"][name] += 1
                    continue

                inserted = await record_baselines(
                    s, signal_id=sig.id, ctx=ctx, registry=registry
                )
                stats["predictions_inserted"] += inserted
                for name in ("signal",) + tuple(registry.baselines().keys()):
                    stats["coverage"][name] += 1

                # If outcome already known, resolve the variants now.
                outcome = (
                    await s.execute(
                        select(SignalOutcome).where(SignalOutcome.signal_id == sig.id)
                    )
                ).scalar_one_or_none()
                if outcome is not None and outcome.price_resolved is not None:
                    n = await record_prediction_resolution(
                        s, signal_id=sig.id, price_resolved=float(outcome.price_resolved)
                    )
                    stats["resolutions_backfilled"] += n

            if not dry_run:
                await s.commit()

    # Coverage report
    print(f"Processed: {stats['signals_processed']} signals")
    print("Coverage by variant:")
    total = max(stats["signals_processed"], 1)
    for name, count in sorted(stats["coverage"].items()):
        pct = 100.0 * count / total
        print(f"  {name:26} → {count:5} ({pct:5.1f}%)")
    print(f"Outcomes backfilled: {stats['resolutions_backfilled']} rows updated")
    if dry_run:
        print("(dry-run: no rows written)")

    # Ensure dict type for return (defaultdict breaks json.dumps in some envs)
    stats["coverage"] = dict(stats["coverage"])
    return stats


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--since", type=str, default=None, help="YYYY-MM-DD")
    p.add_argument("--batch-size", type=int, default=100)
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    asyncio.run(backfill(dry_run=args.dry_run, since=since, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `docker compose exec -T app python -m pytest tests/unit/test_backfill_signal_predictions.py -v`
Expected: 4 passed.

- [ ] **Step 5: Smoke — dry-run against the live DB**

Run: `docker compose exec -T app python -m scripts.backfill_signal_predictions --dry-run`
Expected: a coverage report printed, `(dry-run: no rows written)` at the end, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_signal_predictions.py tests/unit/test_backfill_signal_predictions.py
git commit -m "feat(measurement): backfill script for historical signals"
```

---

## Task 14: CLI wrapper — `scripts/report_metrics.py`

**Files:**
- Create: `scripts/report_metrics.py`

This task is formatting-only — no new tests beyond a smoke invocation. The business logic lives in the admin API, which already has integration coverage.

- [ ] **Step 1: Implement the CLI**

Create `scripts/report_metrics.py`:

```python
"""ASCII table report of /api/admin/metrics/variants.

Calls the API in-process via httpx + ASGITransport — no need to spin up a
webserver or pass auth tokens. Exits non-zero on API error.

Usage:
    docker compose exec app python -m scripts.report_metrics --window 30d
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from app.api.main import app


async def _fetch(window: str, token: str | None) -> dict:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with AsyncClient(transport=transport, base_url="http://cli") as c:
        r = await c.get(
            f"/api/admin/metrics/variants?window={window}", headers=headers
        )
    if r.status_code != 200:
        sys.stderr.write(f"API error {r.status_code}: {r.text}\n")
        sys.exit(1)
    return r.json()


def _fmt(v: float | None, width: int, decimals: int = 3) -> str:
    if v is None:
        return "n/a".rjust(width)
    return f"{v:.{decimals}f}".rjust(width)


def _render_table(data: dict, window: str) -> str:
    lines: list[str] = []
    header = (
        "Variant                   |  n  | Winrate (CI95)          | Brier "
        "| PnL/trade | PnL total"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)
    for v in data["variants"]:
        name = v["variant"][:26].ljust(26)
        n = str(v["n"]).rjust(3)
        if v["winrate"] is None:
            wr = "       n/a             "
        else:
            wr = (
                f"{v['winrate']:.3f} "
                f"[{v['winrate_ci95_low']:.2f}-{v['winrate_ci95_high']:.2f}]"
            ).rjust(23)
        br = _fmt(v["brier"], width=5)
        ppt = _fmt(v["pnl_per_trade_eur"], width=8, decimals=2) + "€"
        pt = _fmt(v["pnl_total_eur"], width=8, decimals=2) + "€"
        lines.append(f"{name} | {n} | {wr} | {br} | {ppt}  | {pt}")

    try:
        days = int(window.rstrip("d"))
        start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        end = datetime.now(timezone.utc).date().isoformat()
        lines.append("")
        lines.append(f"Window: {start} → {end} ({window})")
    except ValueError:
        pass
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", default="30d")
    p.add_argument("--token", default=None, help="Bearer JWT for an admin account")
    p.add_argument("--json", action="store_true", help="emit raw JSON, no table")
    args = p.parse_args()

    data = asyncio.run(_fetch(args.window, args.token))
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(_render_table(data, args.window))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke — run the CLI**

Run: `docker compose exec -T app python -m scripts.report_metrics --window 30d --json 2>&1 | head -50`

Expected behaviour: either (a) HTTP 401 from the admin endpoint (expected without a token — this proves the CLI reaches the API), or (b) a JSON body if you pass `--token <admin_jwt>`. Either is acceptable — the point is "no crash, exit code makes sense".

- [ ] **Step 3: Commit**

```bash
git add scripts/report_metrics.py
git commit -m "feat(measurement): CLI report_metrics — ASCII table over admin API"
```

---

## Task 15: Final verification — full test suite + smoke on real DB

**Files:** none.

- [ ] **Step 1: Run the entire backend test suite**

Run: `docker compose exec -T app python -m pytest tests/ --ignore=tests/unit/test_migration_014.py -q`
Expected: all pass (the `test_migration_014` ignore is the documented pre-existing flake, unrelated to this chantier).

- [ ] **Step 2: Verify the full measurement module in one go**

Run: `docker compose exec -T app python -m pytest tests/unit/test_measurement_* tests/integration/test_signal_predictions_hook.py tests/integration/test_resolution_hook.py tests/integration/test_admin_metrics_variants.py tests/integration/test_admin_metrics_rolling.py tests/unit/test_admin_require_admin.py tests/unit/test_backfill_signal_predictions.py -v`
Expected: all green, no warnings beyond pre-existing ones.

- [ ] **Step 3: Smoke — dry-run backfill in the live dev DB**

Run: `docker compose exec -T app python -m scripts.backfill_signal_predictions --dry-run`
Expected: completes without error, prints coverage report.

- [ ] **Step 4: Smoke — real backfill**

Run: `docker compose exec -T app python -m scripts.backfill_signal_predictions`
Expected: completes without error; second run of `--dry-run` after this one shows identical coverage (idempotency proof).

- [ ] **Step 5: Verify one fresh signal gets variants on write**

Option A — if a scheduled Celery task runs frequently, wait for a new signal and query:

```bash
docker compose exec -T db psql -U postgres -d signal -c \
  "SELECT signal_id, variant, predicted_direction, predicted_probability
   FROM signal_predictions
   ORDER BY id DESC LIMIT 10;"
```

Expected: the 5 variant rows for the most recent signal(s) are present.

Option B — trigger `_persist_signal` directly (only if waiting isn't practical):

```bash
docker compose exec -T app python -c "
import asyncio
from app.signal.signal_builder import _persist_signal
asyncio.run(_persist_signal(
    {'event_id': 1, 'market_id': '<real_market_id>', 'market_price': 0.5,
     'direction_recommendation': 'YES', 'reasoning': 'smoke',
     'llm_model_version': 'smoke', 'source_tier_mix': {},
     'impact_score': 0.5, 'article_excerpts': []},
    articles=[{'news_clean_id': 1, 'direction_hint': 'YES', 'source_weight': 0.8}],
))"
```

Expected: 5 new rows in `signal_predictions` for the new signal.

- [ ] **Step 6: Final commit of any residual changes, push branch, stop here**

```bash
git status
# expected: working tree clean
git log --oneline main..HEAD
# expected: 14-ish commits, one per task above
```

Merge to `main` is **not** part of this plan — leave that to a human review after smoke has run for a few days on the dev environment.

---

## Rollout checklist (post-merge, for the operator — not an engineer task)

1. Apply migration `020` on production
2. Deploy new code
3. Run `backfill_signal_predictions --dry-run` → review output
4. Run `backfill_signal_predictions` → review the resolutions_backfilled count
5. Wait ≥14 days of signal traffic
6. `docker compose exec app python -m scripts.report_metrics --window 14d` → first honest read

## Known limitations (for chantier follow-ups)

- **`baseline_momentum` is forward-only until a price-history feed exists.** `build_scoring_context` passes `market_price_24h_ago=None` today. A future chantier can wire it to Polymarket `/prices-history` or a captured `market_price_history` table without changing baseline signatures.
- **Shadow variants are stubbed.** `schedule_shadow_variants` is a logger line — chantier #3 (LLM quality) will register the first real shadow.
- **Admin auth is env-allowlist.** Upgrade to a `role` column when we need >1 permission tier.
