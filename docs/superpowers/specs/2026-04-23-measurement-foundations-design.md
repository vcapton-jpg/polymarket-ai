# Measurement Foundations — Signal Baselines & Metrics

**Status:** Design approved — ready for implementation plan
**Chantier #1** of the broader "Signal backend optimization" initiative (5 chantiers total)
**Date:** 2026-04-23
**Branch target:** `measurement/foundations` (to be created off `main`)

---

## Problem statement

Today we produce ~10–20 signals per day. We have captured `direction_correct` on `n=22-24` resolved markets, which gives us a **winrate of 46–48%** — an IC95% of roughly `[26%, 68%]`. We cannot tell from this number whether the signal pipeline is adding any predictive value, because we have no honest comparison.

We also suspect (from audit notes) that GPT-4o has a pro-YES bias (BUY_NO signals in the 75–89 bucket win 72.7%, vs 29.2% for BUY_YES). We cannot confirm or reject this suspicion without a calibration metric and a stratified comparison.

Before optimizing any part of the pipeline (sourcing, LLM prompts, retrieval, scoring weights), we need a measurement layer that says **honestly** whether a change is an improvement. Without this, the next four chantiers are flying blind.

## Goal

Give the team the ability to answer four questions, with numbers and confidence intervals:

1. **Does the signal beat random?** (`signal.winrate − 0.5`)
2. **Does the signal beat the market consensus?** (`signal.winrate − market_price.winrate`)
3. **Is the signal well-calibrated?** (`signal.brier` vs `baseline.brier`)
4. **Is the signal profitable net of simulated fills?** (`signal.pnl_per_trade` in €)

## Non-goals

- **No change to the scoring pipeline itself.** This chantier only observes.
- **No LLM variants / prompt A/B.** Reserved for chantier #3 (LLM quality).
- **No real A/B allocation framework.** Shadow-only; users always see the production signal. True A/B requires more data than we will have in the next 30 days.
- **No frontend dashboard.** API-first. A `/admin/metrics` FE page can come later when we have enough data points for charts to carry meaning.
- **No ML calibration loop (LightGBM).** Reserved for chantier #5, which needs ≥500 resolved outcomes.

---

## Architecture

### Overview

```
┌──────────────────────────┐
│ SignalBuilder.build_     │  (existing scoring pipeline)
│   signal()               │
└────────────┬─────────────┘
             │ signal row committed
             ▼
┌──────────────────────────┐     ┌────────────────────────┐
│ record_baselines()       │     │ VariantRegistry        │
│  (in-band, same txn)     │◄────┤  - 4 baselines (boot)  │
│                          │     │  - shadows (future)    │
└────────────┬─────────────┘     └────────────────────────┘
             │ 5 rows inserted (signal + 4 baselines)
             ▼
┌──────────────────────────┐
│ signal_predictions       │
│  UNIQUE(signal_id,       │
│         variant)         │
└────────────┬─────────────┘
             │
             │ ... (market resolves) ...
             ▼
┌──────────────────────────┐
│ check_resolved_markets   │  (existing outcomes worker)
│  → UPDATE metrics for    │
│    all variants of       │
│    this signal           │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ /api/admin/metrics/      │
│  variants                │  → aggregated winrate, Brier, P&L
│  variants/rolling        │  → time series per variant
└──────────────────────────┘
```

### Why this topology

- **Baselines in-band** because they are pure, deterministic, and cheap (<15ms total). This guarantees that **every signal has its 5 variant rows** — no race conditions, no "missing baseline" case for aggregations to handle. The same transaction that creates the signal creates its measurement rows.
- **Shadow variants async** because chantier #3 will add variants that call a second LLM (expensive, slow, externally dependent). Blocking signal creation on these would regress perf. The Celery task `compute_shadow_variants.delay(signal_id)` fires after commit.
- **Resolution in the existing `check_resolved_markets` task** because that task already runs daily, already holds the `price_resolved` value, and a single UPDATE can refresh all variants of a signal at once.

---

## Data model

### New table: `signal_predictions`

```sql
CREATE TABLE signal_predictions (
  id                     BIGSERIAL PRIMARY KEY,
  signal_id              BIGINT       NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  variant                TEXT         NOT NULL,
  predicted_direction    TEXT,                               -- 'BUY_YES' | 'BUY_NO' | NULL
  predicted_probability  NUMERIC(5,4),                       -- implied P(YES) in [0, 1]
  created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),

  -- Filled when the market resolves:
  direction_correct      BOOLEAN,
  brier_score            NUMERIC(6,4),
  simulated_pnl_eur      NUMERIC(8,2),
  resolved_at            TIMESTAMPTZ,

  UNIQUE (signal_id, variant)
);

CREATE INDEX idx_sp_variant_resolved
  ON signal_predictions(variant, resolved_at)
  WHERE resolved_at IS NOT NULL;
CREATE INDEX idx_sp_signal ON signal_predictions(signal_id);
```

### `variant` values

- `signal` — the production scoring output (direction + `impact_strength` as implied probability)
- `baseline_random`
- `baseline_market_price`
- `baseline_momentum`
- `baseline_news_sentiment`
- `shadow_<name>` — reserved, filled by chantiers #3/#4 when they register shadow variants

### Conventions

**Probability convention** — always implied `P(YES)` in `[0, 1]`:
- `random`: 0.5 exactly
- `market_price`: `ctx.market_price` (already in `[0, 1]`)
- `momentum`: `clip(0.5 + 0.5 * (market_price - market_price_24h_ago), 0.01, 0.99)`
- `news_sentiment`: `sigmoid(2 * sentiment)` where `sentiment = Σ(direction_sign × source_weight) / Σ(source_weight)`

**Metric definitions — which outcomes count**

The system distinguishes two ground-truth values at resolution:
- `price_resolved` (float in `[0, 1]`) — raw resolved price. Used for P&L.
- `price_resolved_binary` (`1` if `price_resolved >= 0.95`, `0` if `price_resolved <= 0.05`, else `NULL`) — binary outcome. Used for Brier.

**Winrate** uses `direction_correct` (already computed by `direction_matches_price_move`) and therefore **includes ambiguous resolutions** — a BUY_YES signal on a market that resolved at `0.70` counts as correct.

**Brier** uses `price_resolved_binary` and therefore **excludes ambiguous resolutions** (binary calibration is undefined for non-binary outcomes). Brier coverage will be lower than winrate coverage; the admin endpoint reports `n` and `brier_n` separately to surface this.

**Simulated P&L** — stake fixe 10€ per variant, using `price_resolved` (not binary) so partial resolutions are captured:
- if `predicted_direction == 'BUY_YES'`: `pnl_eur = 10 * (price_resolved − predicted_probability)`
- if `predicted_direction == 'BUY_NO'`:  `pnl_eur = 10 * (predicted_probability − price_resolved)`

This is a **simulated** P&L — it assumes fills at exactly `predicted_probability` with zero slippage and zero fees. The absolute number is not tradable; the **relative** number across variants is what matters.

**Missing data**:
If a baseline cannot compute (e.g. `momentum` without a price 24h ago), it inserts a row with `predicted_direction = NULL` and `predicted_probability = NULL`. Aggregation queries filter `WHERE predicted_direction IS NOT NULL AND resolved_at IS NOT NULL`. The row's presence (not its values) proves we tried — this matters for coverage reporting.

---

## Components

### 1. `app/measurement/variant_registry.py` (new)

```python
from typing import Callable, Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class VariantPrediction:
    direction: str | None          # 'BUY_YES' | 'BUY_NO' | None
    probability: float | None      # P(YES) in [0, 1], or None if missing data


class BaselineFn(Protocol):
    def __call__(self, ctx: "ScoringContext") -> VariantPrediction: ...


class VariantRegistry:
    def __init__(self) -> None:
        self._baselines: dict[str, BaselineFn] = {}
        self._shadows: dict[str, BaselineFn] = {}

    def register_baseline(self, name: str, fn: BaselineFn) -> None: ...
    def register_shadow(self, name: str, fn: BaselineFn) -> None: ...
    def baselines(self) -> dict[str, BaselineFn]: ...
    def shadows(self) -> dict[str, BaselineFn]: ...


_registry = VariantRegistry()

def get_registry() -> VariantRegistry:
    return _registry
```

Single responsibility: registration + enumeration. No execution logic — that lives in `pipeline.py`. Trivial to test.

### 2. `app/measurement/baselines.py` (new — the 4 baselines)

Four pure functions, each with signature `(ctx: ScoringContext) -> VariantPrediction`.

- **`baseline_random(ctx)`** — deterministic via `random.Random(ctx.signal_id).random()`. Probability always `0.5`. Direction flips on the seeded draw. Deterministic so tests are stable and backfill is reproducible.
- **`baseline_market_price(ctx)`** — direction = `BUY_YES if ctx.market_price > 0.5 else BUY_NO`, probability = `ctx.market_price`.
- **`baseline_momentum(ctx)`** — if `ctx.market_price_24h_ago is None`, return `VariantPrediction(None, None)`. Otherwise `return_24h = ctx.market_price - ctx.market_price_24h_ago`; direction = `BUY_YES if return_24h > 0 else BUY_NO`; probability = `clip(0.5 + 0.5 * return_24h, 0.01, 0.99)`. The `0.5 *` factor keeps probability in `[0, 1]` since `return_24h` is in `[-1, 1]`.
- **`baseline_news_sentiment(ctx)`** — if `ctx.article_impacts` is empty, return `VariantPrediction(None, None)`. Otherwise compute `sentiment = Σ(direction_sign_i × source_weight_i) / Σ(source_weight_i)` where `direction_sign` is `+1` for YES-leaning articles and `-1` for NO-leaning. Direction = `BUY_YES if sentiment > 0 else BUY_NO`; probability = `sigmoid(sentiment * 2)` for a reasonable spread.

Registered at module import via `measurement/__init__.py`:

```python
from app.measurement.variant_registry import get_registry
from app.measurement.baselines import (
    baseline_random, baseline_market_price,
    baseline_momentum, baseline_news_sentiment,
)

_r = get_registry()
_r.register_baseline("baseline_random", baseline_random)
_r.register_baseline("baseline_market_price", baseline_market_price)
_r.register_baseline("baseline_momentum", baseline_momentum)
_r.register_baseline("baseline_news_sentiment", baseline_news_sentiment)
```

### 3. `app/measurement/scoring_context.py` (new)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ArticleImpact:
    direction: str      # 'YES' | 'NO' | 'NEUTRAL'
    source_weight: float

@dataclass(frozen=True)
class ScoringContext:
    signal_id: int
    market_id: str
    event_id: int | None
    market_price: float
    market_price_24h_ago: float | None
    article_impacts: tuple[ArticleImpact, ...]
    t0: datetime

    @classmethod
    def from_signal(cls, session, signal_row, event, candidate_market) -> "ScoringContext":
        """Assemble a context from rows already loaded by the scoring pipeline.
        No extra DB round-trips beyond a single lookup of market_price_24h_ago
        from market_price_history (indexed on market_id + timestamp)."""
        ...
```

Immutable, self-contained, zero DB access inside baseline functions. Enables unit testing with hand-built `ScoringContext` instances.

### 4. `app/measurement/pipeline.py` (new)

```python
def record_baselines(session, signal_id, ctx, registry) -> int:
    """Insert one row per baseline + one row for the 'signal' variant.
    Returns the count of rows inserted. Must be called inside the same
    transaction as the signal."""

def schedule_shadow_variants(signal_id: int) -> None:
    """Fire-and-forget Celery task. Currently a stub — chantier #3 fills the
    shadow registry. Kept in place so the hook exists before we need it."""
```

### 5. Hook in `SignalBuilder.build_signal()`

Single 6-line insertion, right before the signal commit:

```python
from app.measurement.pipeline import record_baselines, schedule_shadow_variants
from app.measurement.variant_registry import get_registry
from app.measurement.scoring_context import ScoringContext

ctx = ScoringContext.from_signal(session, signal_row, event, candidate_market)
record_baselines(session, signal_row.id, ctx, get_registry())
session.commit()
schedule_shadow_variants(signal_row.id)
```

The new code is **additive** — no change to existing scoring logic or signal fields.

### 6. Resolution — hook in `check_resolved_markets`

Inside `app/workers/tasks_outcomes.py::check_resolved_markets`, when a market resolves and `direction_correct` is being written on the signal, issue one batch UPDATE against `signal_predictions`:

```sql
UPDATE signal_predictions sp
SET
  direction_correct = (sp.predicted_direction = :expected_direction),
  brier_score = CASE
    WHEN :price_resolved_binary IS NULL THEN NULL
    ELSE POWER(sp.predicted_probability - :price_resolved_binary, 2)
  END,
  simulated_pnl_eur = 10 * (
    CASE WHEN sp.predicted_direction = 'BUY_YES'
         THEN :price_resolved - sp.predicted_probability
         ELSE sp.predicted_probability - :price_resolved END
  ),
  resolved_at = now()
WHERE sp.signal_id = :signal_id
  AND sp.predicted_direction IS NOT NULL
  AND sp.resolved_at IS NULL;
```

Bound parameters:
- `:expected_direction` — `'BUY_YES'` if `price_resolved >= 0.5` else `'BUY_NO'` (matches `direction_matches_price_move`)
- `:price_resolved` — raw resolved price (float)
- `:price_resolved_binary` — `1` if `price_resolved >= 0.95`, `0` if `<= 0.05`, else `NULL`

One query per signal resolved. Idempotent (`resolved_at IS NULL` guard). Skips rows with missing data (`predicted_direction IS NULL`). Brier is `NULL` for ambiguous resolutions; P&L is always computed.

### 7. Backfill — `scripts/backfill_signal_predictions.py`

Walks `signals` table chronologically. For each signal:
- Reconstruct a partial `ScoringContext` from whatever DB rows exist
- Call every registered baseline; insert rows even when `predicted_direction` is NULL (coverage proof)
- If the signal's market is already in `signal_outcomes.price_resolved`, immediately compute and write `direction_correct`, `brier_score`, `simulated_pnl_eur`, `resolved_at`

Flags:
- `--dry-run` — report intent without writing
- `--since YYYY-MM-DD` — limit to recent signals
- `--batch-size N` — commit every N signals (default 100)

Final report printed to stdout:

```
Processed: 1,247 signals
Coverage by variant:
  signal                    → 1,247 (100.0%)
  baseline_random           → 1,247 (100.0%)
  baseline_market_price     → 1,247 (100.0%)
  baseline_momentum         →   892 ( 71.5%)   # 355 signals lacked price history
  baseline_news_sentiment   → 1,203 ( 96.5%)
Outcomes backfilled:         22 signals × 5 variants = 110 rows updated
```

### 8. Admin API — `app/api/routes/admin_metrics.py` (new)

Two endpoints, both protected by the existing `require_admin` dependency that checks `UserProfile.role == 'admin'`:

#### `GET /api/admin/metrics/variants?window=30d`

Aggregate across all resolved signals within the window. One row per variant.

```json
{
  "window": "30d",
  "as_of": "2026-04-23T14:32:00Z",
  "variants": [
    {
      "variant": "signal",
      "n": 24,
      "n_coverage": 24,
      "winrate": 0.458,
      "winrate_ci95_low": 0.265,
      "winrate_ci95_high": 0.661,
      "brier": 0.298,
      "brier_n": 22,
      "pnl_per_trade_eur": -0.52,
      "pnl_total_eur": -12.48
    },
    { "variant": "baseline_random", "...": "..." },
    { "variant": "baseline_market_price", "...": "..." },
    { "variant": "baseline_momentum", "n_coverage": 18, "...": "..." },
    { "variant": "baseline_news_sentiment", "...": "..." }
  ]
}
```

IC95% computed server-side using Wilson score interval (stable for small `n`).

#### `GET /api/admin/metrics/variants/rolling?window=30d&step=1d`

Time series of cumulative metrics per variant per day within the window.

```json
{
  "window": "30d",
  "step": "1d",
  "series": [
    {
      "date": "2026-04-01",
      "variant": "signal",
      "n_cumulative": 6,
      "winrate_cumulative": 0.500
    },
    ...
  ]
}
```

### 9. CLI — `scripts/report_metrics.py`

Thin wrapper around the API. `curl` internally, format the response as an ASCII table. Zero business logic — formatting only.

```
$ docker compose exec app python -m scripts.report_metrics --window 30d

Variant                   |  n  | Winrate (CI95)    | Brier | PnL/trade | PnL total
--------------------------+-----+-------------------+-------+-----------+----------
signal                    | 24  | 0.458 [0.27-0.66] | 0.298 |   -0.52€  |  -12.48€
baseline_random           | 24  | 0.500 [0.31-0.69] | 0.250 |   +0.05€  |   +1.20€
baseline_market_price     | 24  | 0.625 [0.42-0.79] | 0.211 |   +1.20€  |  +28.80€   ← best
baseline_momentum         | 18  | 0.444 [0.24-0.67] | 0.289 |   -0.30€  |   -5.40€
baseline_news_sentiment   | 22  | 0.545 [0.34-0.73] | 0.272 |   +0.48€  |  +10.56€

Window: 2026-03-24 → 2026-04-23 (30d)
```

---

## Testing strategy

### Unit tests (~15 tests)

- `baselines.py`:
  - `baseline_random` is deterministic for a given `signal_id`
  - `baseline_market_price` on edge cases (exactly 0.5, 0.0, 1.0)
  - `baseline_momentum` returns `(None, None)` when `market_price_24h_ago is None`
  - `baseline_momentum` direction/probability on a positive return, a negative return, zero
  - `baseline_news_sentiment` empty list → `(None, None)`
  - `baseline_news_sentiment` weighted majority (mostly YES-leaning with high source_weight wins)
- `variant_registry.py`:
  - `register_baseline` is idempotent (re-registering same name is a no-op or raises — design: raises `ValueError`)
  - `baselines()` returns registered dict
- `pipeline.py`:
  - `record_baselines` inserts exactly `1 + len(registry.baselines())` rows
  - Variants with `predicted_direction = None` still insert (coverage proof)
- Metric math (in a helpers module):
  - Wilson CI on known fixtures (n=24, k=11 → expected CI)
  - Brier calculation (YES won, we said 0.85 → brier = 0.0225)
  - P&L calculation (stake 10€, BUY_YES, YES won at proba 0.6 → pnl = 4€)

### Integration tests (~6 tests)

- End-to-end: create signal → verify 5 rows in `signal_predictions` with correct `variant` names and non-null probabilities (except momentum which may be null in test DB)
- Resolution: seed signal + 5 variant rows → run `check_resolved_markets` mock → verify all 5 rows get `direction_correct + brier + pnl + resolved_at`
- Resolution skips `predicted_direction IS NULL` rows
- Admin endpoint `/variants` returns aggregated data with correct shape and auth-rejects non-admin
- Admin endpoint `/variants/rolling` returns time series with correct shape
- Backfill script on a fixture DB produces expected coverage report

### Smoke

After ship: `docker compose exec app python -m scripts.backfill_signal_predictions --dry-run` must complete without error on the current prod-like dataset.

---

## Migration & rollout

1. **Alembic migration** creates `signal_predictions` table (additive, zero risk to existing tables)
2. Deploy new code — signals written post-deploy automatically get their 5 variant rows
3. Run backfill script `--dry-run` → review coverage report
4. Run backfill script for real → historical signals get their variants
5. Wait 14 days
6. First meaningful aggregated read via `scripts/report_metrics.py --window 14d`

No feature flag needed — the only observable change is new rows in a new table. Roll back = drop the table + revert the hook call (5 lines of code).

---

## Dependencies on other chantiers

- **This chantier is a prerequisite for #3, #4, #5.** The variant registry provides the slot for shadow variants, and the metrics surface is how we will measure the gain (or loss) from prompt/retrieval/scoring changes.
- **No dependency** on chantier #2 (sourcing quality). The two can run in parallel — a sourcing fix would just appear as a winrate bump in the signal variant, measured by this chantier.

## Open risks

1. **`market_price_history` coverage** — backfill of `baseline_momentum` assumes at least ~70% coverage on historical signals. If coverage is lower (investigation pending), `momentum` becomes a forward-only variant. The spec handles this gracefully (NULL rows) but the diagnostic value of momentum on backfilled data will be limited.
2. **Signals on ambiguous markets** — markets that resolve in `(0.05, 0.95)` are excluded from Brier. If >20% of our markets resolve ambiguously, Brier coverage will be lower than winrate coverage. Report this in the `--window` summary.
3. **Deterministic random is per-signal-id** — if two signals happen to share a hash collision in `signal_id % large_prime`, the "random" direction correlates. The chosen `random.Random(signal_id)` avoids this by using the full int.

## Success criteria revisited

J+14 after ship:
- ✅ `/api/admin/metrics/variants?window=14d` returns all 5 variants with `n ≥ 50`
- ✅ Wilson CI95% width on `signal.winrate` is ≤ 0.30 (currently 0.40)
- ✅ Rolling endpoint gives a visible trend line
- ✅ For each variant, at most 1 of 3 metrics is missing (robustness of the coverage)

J+30:
- ✅ We can confidently answer "does the signal beat market_price?" one way or the other
- ✅ If `signal.winrate < market_price.winrate`, we have evidence to investigate chantier #3 (LLM quality) instead of pushing more features
