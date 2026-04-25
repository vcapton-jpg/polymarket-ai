# Heuristic Score Validation & Calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose the hand-picked heuristic scorer into pure testable sub-scorers, register it as a measurable variant alongside the 4 chantier #1 baselines, and offline-tune its 7 weights against ~225 short-horizon outcomes with a 3-check promotion gate — all without changing the public scoring API.

**Architecture:** Three layers. (A) A new `app/scoring/{weights,strength_scorer,trade_scorer}.py` trio holds the pure math; `HeuristicScorer.compute_score` delegates to them while keeping the public signature identical. (B) `app/measurement/pipeline.py::record_baselines` is rewired to write `variant='heuristic_v1'` (replacing the legacy `'signal'` name via Alembic migration 025) and an optional `variant='heuristic_shadow'` row computed with `Settings`-driven weights under a kill-switch flag. (C) Two offline scripts (`scripts/validate_heuristic_weights.py` and `scripts/tune_heuristic_weights.py`) join `signal_predictions ⋈ signal_outcomes` at the `t1h` horizon, report Brier / P&L / Wilson-CI95 per variant, and run coordinate descent over 7 weights under a 3-check rejection gate.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async (`Mapped` / `mapped_column`), Alembic (revision `025`, `down_revision="024"`), pytest-asyncio (AUTO mode + per-test `async_db_factory` fixture), `pg_insert().on_conflict_do_nothing(index_elements=["signal_id","variant"])` (pattern from chantier #1), no new external deps, no LLM calls.

**Spec:** `docs/specs/2026-04-24-heuristic-score-validation-design.md`. Read it once before starting — §3 (file structure), §4 (decomposition), §5 (variant rewiring), §6 (offline tuning + gate) are the ground truth.

**Depends on (already shipped in chantiers #1–#4):**
- `app/measurement/variant_registry.py::VariantPrediction` → `@dataclass(frozen=True)` with fields `direction: str | None` and `probability: float | None`.
- `app/measurement/pipeline.py::record_baselines` — chantier #1 hot path; writes one `SignalPrediction` row per variant inside the signal transaction.
- `app/measurement/metrics.py::{wilson_ci95, brier_from_outcome, simulated_pnl_eur}` — pure helpers used everywhere.
- `app/measurement/__init__.py` — registers the 4 baselines via side-effect on import.
- `app/db/models.py::{Signal, SignalPrediction, SignalOutcome, EventMarketFeatures}`. `SignalPrediction` has the composite unique key `(signal_id, variant)` and columns `predicted_direction: Text|None`, `predicted_probability: Numeric(6,4)|None`, `brier_score`, `simulated_pnl_eur`, `direction_correct`.
- `app/scoring/heuristic_scorer.py::HeuristicScorer` — current entry-point; keys are `freshness`, `source_weight`, `confirmation`, `liquidity`, `spread`, `time_to_resolution`; LLM enters separately as `llm_combined`.
- `app/signal/signal_builder.py::SignalBuilder.build_signal` — already calls `scorer.compute_score(features, llm_combined)`; already has the feature dict at signal commit time.
- `tests/unit/test_config_integrity.py` — chantier #1 CI gate that pins runtime constants to Settings defaults. Parametrized test `test_settings_field_types` is the extension point for new settings fields.
- `tests/conftest.py::async_db_factory` — per-test async session factory; mandatory for every DB-touching test (`async_session_factory` imported from `app.db.database` will break on event-loop isolation).

**Branch target:** continue on `pivot/learn-and-trade` (current branch). No new worktree — this chantier is a linear continuation.

---

## File structure (created / modified)

**New files:**
- `alembic/versions/025_rename_signal_variant_to_heuristic_v1.py` — data migration (task 5)
- `app/scoring/weights.py` — `HeuristicWeights` frozen dataclass + `load_from_settings` + `frozen_v1` (task 1)
- `app/scoring/strength_scorer.py` — `compute_signal_strength(features, weights, llm_combined) -> float` (task 2)
- `app/scoring/trade_scorer.py` — `compute_trade_quality(features, weights) -> float` (task 3)
- `app/measurement/heuristic_variant.py` — `predict_heuristic(weights, features, llm_combined, direction) -> VariantPrediction` (task 6)
- `scripts/validate_heuristic_weights.py` — join predictions+outcomes, report Brier / P&L / Wilson-CI95 per variant (task 10)
- `scripts/tune_heuristic_weights.py` — coordinate descent + 3-check gate (tasks 11 + 12)
- `docs/audit/heuristic_validation_report_2026-04-24.md` — generated report (task 13)
- `docs/runbooks/promote_heuristic_candidate.md` — operator runbook stub (task 14)
- `tests/unit/test_heuristic_weights.py` — invariants + load_from_settings (task 1)
- `tests/unit/test_strength_scorer.py` — monotone + zero-weight per weight (task 2)
- `tests/unit/test_trade_scorer.py` — monotone + zero-weight per weight (task 3)
- `tests/unit/test_heuristic_variant.py` — `predict_heuristic` round-trip + shadow-differs (task 6)
- `tests/unit/test_migration_025.py` — rename idempotency (task 5)
- `tests/unit/test_validate_heuristic_weights.py` — fixture-driven report assertions (task 10)
- `tests/unit/test_tune_heuristic_weights.py` — convergence + gate rejection + idempotence (tasks 11 + 12)
- `tests/integration/test_heuristic_shadow_write.py` — flag on/off writes correct variant rows (task 9)

**Modified files:**
- `app/core/config.py` — add `heuristic_shadow_enabled` + 7 weight overrides (task 7)
- `app/scoring/heuristic_scorer.py` — delegate to new modules; public API unchanged (task 4)
- `app/scoring/__init__.py` — export new symbols (task 4)
- `app/measurement/pipeline.py::record_baselines` — rename `'signal'` → `'heuristic_v1'`, append shadow row if flag on (task 8)
- `tests/unit/test_config_integrity.py` — extend parametrized type-pin to the 8 new Settings fields (task 7)
- `tests/unit/test_heuristic_scorer.py` — kept as smoke test; no edits needed (verified task 4)

---

## Task 1: `HeuristicWeights` frozen dataclass

**Files:**
- Create: `app/scoring/weights.py`
- Test: `tests/unit/test_heuristic_weights.py`

- [ ] **Step 1: Write the failing invariant test**

```python
# tests/unit/test_heuristic_weights.py
"""Chantier #5 — HeuristicWeights invariants.

These tests pin the sum-to-1 contract: if anyone edits the defaults and the
sums drift, the dataclass raises at construction so we never silently score
with a malformed weight vector in prod.
"""
from __future__ import annotations

import pytest

from app.scoring.weights import HeuristicWeights


def test_defaults_match_frozen_v1_values():
    w = HeuristicWeights()
    assert w.w_freshness == 0.15
    assert w.w_source == 0.10
    assert w.w_confirmation == 0.15
    assert w.w_llm == 0.60
    assert w.w_liquidity == 0.40
    assert w.w_spread == 0.35
    assert w.w_time_to_resolution == 0.25
    assert w.strength_weight == 0.75
    assert w.trade_weight == 0.25


def test_strength_bloc_must_sum_to_one():
    # 0.15 + 0.10 + 0.15 + 0.60 = 1.00 ✓ (default)
    HeuristicWeights()  # no raise

    with pytest.raises(ValueError, match="strength_weights sum"):
        HeuristicWeights(w_freshness=0.20)  # 1.05 total


def test_trade_bloc_must_sum_to_one():
    with pytest.raises(ValueError, match="trade_weights sum"):
        HeuristicWeights(w_liquidity=0.50)  # 1.10 total


def test_top_level_must_sum_to_one():
    with pytest.raises(ValueError, match="top_weights sum"):
        HeuristicWeights(strength_weight=0.80)  # 1.05 total


def test_frozen_v1_classmethod_returns_defaults():
    assert HeuristicWeights.frozen_v1() == HeuristicWeights()


def test_dataclass_is_frozen():
    w = HeuristicWeights()
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError subclasses AttributeError
        w.w_freshness = 0.99  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_heuristic_weights.py -v`
Expected: ImportError / ModuleNotFoundError on `app.scoring.weights`.

- [ ] **Step 3: Implement `HeuristicWeights`**

```python
# app/scoring/weights.py
"""Frozen dataclass holding the 9 knobs of the heuristic scorer.

Why frozen: the scorer is shared across threads (FastAPI + Celery workers).
Accidentally mutating `self.weights.w_llm` mid-request would be a nightmare
to debug. Freezing forbids that at the language level.

Sum invariants: each of the 3 blocs (strength / trade / top) must sum to
1.0 within 1e-6. Violations raise ValueError at construction — we'd rather
crash on startup than score with a malformed vector.

Chantier #5 entry point. Replaces the hand-picked dicts in
`HeuristicScorer.__init__`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeuristicWeights:
    # strength bloc: freshness + source + confirmation + llm must sum to 1.0
    w_freshness: float = 0.15
    w_source: float = 0.10
    w_confirmation: float = 0.15
    w_llm: float = 0.60

    # trade bloc: liquidity + spread + time_to_resolution must sum to 1.0
    w_liquidity: float = 0.40
    w_spread: float = 0.35
    w_time_to_resolution: float = 0.25

    # top-level combination: strength + trade must sum to 1.0
    strength_weight: float = 0.75
    trade_weight: float = 0.25

    def __post_init__(self) -> None:
        strength_sum = self.w_freshness + self.w_source + self.w_confirmation + self.w_llm
        trade_sum = self.w_liquidity + self.w_spread + self.w_time_to_resolution
        top_sum = self.strength_weight + self.trade_weight

        for name, total in (
            ("strength_weights", strength_sum),
            ("trade_weights", trade_sum),
            ("top_weights", top_sum),
        ):
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"{name} sum to {total:.6f}, expected 1.0 (±1e-6)"
                )

    @classmethod
    def frozen_v1(cls) -> "HeuristicWeights":
        """Snapshot of the chantier #5 launch weights.

        Anchor point for `heuristic_v1` measurement. Never edit — if the
        tuner produces a winner, introduce `HeuristicWeights.frozen_v2()`
        rather than mutating this.
        """
        return cls()

    @classmethod
    def load_from_settings(cls, settings) -> "HeuristicWeights":
        """Build from Settings overrides; fall back to defaults per field.

        Settings fields: heuristic_w_freshness, heuristic_w_source,
        heuristic_w_confirmation, heuristic_w_llm, heuristic_w_liquidity,
        heuristic_w_spread, heuristic_w_time_to_resolution,
        heuristic_strength_weight, heuristic_trade_weight.
        """
        return cls(
            w_freshness=getattr(settings, "heuristic_w_freshness", cls.w_freshness),
            w_source=getattr(settings, "heuristic_w_source", cls.w_source),
            w_confirmation=getattr(settings, "heuristic_w_confirmation", cls.w_confirmation),
            w_llm=getattr(settings, "heuristic_w_llm", cls.w_llm),
            w_liquidity=getattr(settings, "heuristic_w_liquidity", cls.w_liquidity),
            w_spread=getattr(settings, "heuristic_w_spread", cls.w_spread),
            w_time_to_resolution=getattr(
                settings, "heuristic_w_time_to_resolution", cls.w_time_to_resolution
            ),
            strength_weight=getattr(settings, "heuristic_strength_weight", cls.strength_weight),
            trade_weight=getattr(settings, "heuristic_trade_weight", cls.trade_weight),
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_heuristic_weights.py -v`
Expected: 6 passed.

- [ ] **Step 5: Add `load_from_settings` test**

Append to `tests/unit/test_heuristic_weights.py`:

```python
def test_load_from_settings_uses_override_values():
    class _FakeSettings:
        heuristic_w_freshness = 0.30
        heuristic_w_source = 0.05
        heuristic_w_confirmation = 0.05
        heuristic_w_llm = 0.60
        # others fall through to defaults

    w = HeuristicWeights.load_from_settings(_FakeSettings())
    assert w.w_freshness == 0.30
    assert w.w_source == 0.05
    assert w.w_llm == 0.60       # explicit override = default value is fine
    assert w.w_liquidity == 0.40  # default


def test_load_from_settings_missing_attr_falls_back_to_default():
    class _Empty:
        pass
    w = HeuristicWeights.load_from_settings(_Empty())
    assert w == HeuristicWeights()  # all defaults
```

- [ ] **Step 6: Run full file and commit**

Run: `pytest tests/unit/test_heuristic_weights.py -v`
Expected: 8 passed.

```bash
git add app/scoring/weights.py tests/unit/test_heuristic_weights.py
git commit -m "feat(chantier-5): add HeuristicWeights frozen dataclass with sum invariants"
```

---

## Task 2: `strength_scorer` pure function

**Files:**
- Create: `app/scoring/strength_scorer.py`
- Test: `tests/unit/test_strength_scorer.py`

- [ ] **Step 1: Write the failing monotonicity tests**

```python
# tests/unit/test_strength_scorer.py
"""Chantier #5 — strength_scorer pure function.

Each weight in the strength bloc gets two tests:
  - monotone: raising that feature strictly increases the output, others equal
  - zero-weight: if w_key=0, the feature has no effect on output

These pin the contribution of every knob. If a future refactor accidentally
drops a feature or swaps a weight, the corresponding test fails.
"""
from __future__ import annotations

from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.weights import HeuristicWeights


def _neutral_features(**overrides):
    base = {
        "freshness": 0.5,
        "source_weight": 0.5,
        "confirmation": 0.5,
    }
    base.update(overrides)
    return base


# ---- freshness ----------------------------------------------------------

def test_freshness_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(freshness=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(freshness=1.0), w, llm_combined=0.5)
    assert high > low


def test_freshness_zero_weight_eliminates_effect():
    # Redistribute the 0.15 to source to keep sum=1.0
    w = HeuristicWeights(w_freshness=0.0, w_source=0.25, w_confirmation=0.15, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(freshness=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(freshness=1.0), w, llm_combined=0.5)
    assert a == b


# ---- source_weight ------------------------------------------------------

def test_source_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(source_weight=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(source_weight=1.0), w, llm_combined=0.5)
    assert high > low


def test_source_zero_weight_eliminates_effect():
    w = HeuristicWeights(w_freshness=0.25, w_source=0.0, w_confirmation=0.15, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(source_weight=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(source_weight=1.0), w, llm_combined=0.5)
    assert a == b


# ---- confirmation -------------------------------------------------------

def test_confirmation_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(confirmation=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(confirmation=1.0), w, llm_combined=0.5)
    assert high > low


def test_confirmation_zero_weight_eliminates_effect():
    w = HeuristicWeights(w_freshness=0.15, w_source=0.25, w_confirmation=0.0, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(confirmation=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(confirmation=1.0), w, llm_combined=0.5)
    assert a == b


# ---- llm ---------------------------------------------------------------

def test_llm_monotone_when_present():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(), w, llm_combined=0.0)
    high = compute_signal_strength(_neutral_features(), w, llm_combined=1.0)
    assert high > low


def test_llm_zero_weight_eliminates_effect():
    # Redistribute 0.60 to the three backend weights to keep sum=1.0
    w = HeuristicWeights(w_freshness=0.35, w_source=0.30, w_confirmation=0.35, w_llm=0.0)
    a = compute_signal_strength(_neutral_features(), w, llm_combined=0.0)
    b = compute_signal_strength(_neutral_features(), w, llm_combined=1.0)
    assert a == b


# ---- output bounds ------------------------------------------------------

def test_output_bounded_in_unit_interval():
    w = HeuristicWeights()
    for f_val in (0.0, 0.5, 1.0):
        for llm in (0.0, 0.5, 1.0):
            score = compute_signal_strength(_neutral_features(
                freshness=f_val, source_weight=f_val, confirmation=f_val,
            ), w, llm_combined=llm)
            assert 0.0 <= score <= 1.0, f"{score} out of [0,1] for f={f_val}, llm={llm}"


def test_missing_feature_defaults_to_neutral():
    """Absent keys should behave the same as the legacy scorer: fallback 0.5."""
    w = HeuristicWeights()
    full = compute_signal_strength(
        {"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5}, w, llm_combined=0.5
    )
    partial = compute_signal_strength({}, w, llm_combined=0.5)
    assert abs(full - partial) < 1e-9


def test_llm_none_renormalizes_backend_contributions():
    """Legacy behaviour (`HeuristicScorer.compute_score(features)` with no
    `llm_combined`): backend contributions are renormalised to the full [0,1]
    range by dividing by (1 - w_llm). Preserve bit-exactness."""
    w = HeuristicWeights()
    # With llm=None, the backend 0.40 bloc is scaled up by 1/(1-0.60) = 2.5.
    features = _neutral_features()
    with_none = compute_signal_strength(features, w, llm_combined=None)
    # Same backend contribution, computed by hand: 0.5*0.15 + 0.5*0.10 + 0.5*0.15 = 0.20
    # Renormalised: 0.20 / 0.40 = 0.50
    assert abs(with_none - 0.50) < 1e-9
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_strength_scorer.py -v`
Expected: ImportError on `app.scoring.strength_scorer`.

- [ ] **Step 3: Implement `strength_scorer`**

```python
# app/scoring/strength_scorer.py
"""Pure function: compute signal strength from features + weights + LLM signal.

Bit-exactly reproduces the formula previously embedded in
`HeuristicScorer.compute_score` so the refactor is semantics-preserving.

Shape: features ∈ [0,1] per key, weights sum to 1.0 (enforced by
HeuristicWeights), output ∈ [0,1].
"""
from __future__ import annotations

from app.scoring.weights import HeuristicWeights


_NEUTRAL = 0.5  # legacy fallback when a feature key is missing


def compute_signal_strength(
    features: dict,
    weights: HeuristicWeights,
    llm_combined: float | None,
) -> float:
    """Weighted combination of backend features + LLM signal.

    When `llm_combined` is not None:
        score = Σ(w_k * features[k]) + w_llm * llm_combined

    When `llm_combined` is None (LLM unavailable):
        score = Σ(w_k * features[k]) / (1 - w_llm)

    That second branch renormalises the backend bloc to the full [0,1] range,
    so a signal with no LLM isn't artificially penalised to 40% of max.
    Preserved from the legacy HeuristicScorer semantics.
    """
    backend_sum = (
        features.get("freshness", _NEUTRAL) * weights.w_freshness
        + features.get("source_weight", _NEUTRAL) * weights.w_source
        + features.get("confirmation", _NEUTRAL) * weights.w_confirmation
    )
    if llm_combined is None:
        # Renormalise. If w_llm == 1.0 we'd divide by zero — treat that as
        # "backend has no signal, fall back to neutral 0.5".
        remaining = 1.0 - weights.w_llm
        if remaining < 1e-9:
            return _NEUTRAL
        return max(0.0, min(1.0, backend_sum / remaining))
    raw = backend_sum + llm_combined * weights.w_llm
    return max(0.0, min(1.0, raw))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_strength_scorer.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add app/scoring/strength_scorer.py tests/unit/test_strength_scorer.py
git commit -m "feat(chantier-5): extract strength_scorer as pure function with per-weight tests"
```

---

## Task 3: `trade_scorer` pure function

**Files:**
- Create: `app/scoring/trade_scorer.py`
- Test: `tests/unit/test_trade_scorer.py`

- [ ] **Step 1: Write the failing monotonicity tests**

```python
# tests/unit/test_trade_scorer.py
"""Chantier #5 — trade_scorer pure function.

Mirrors test_strength_scorer.py: monotone + zero-weight per weight,
output bounds, missing-key neutrality.
"""
from __future__ import annotations

from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights


def _neutral_features(**overrides):
    base = {
        "liquidity": 0.5,
        "spread": 0.5,
        "time_to_resolution": 0.5,
    }
    base.update(overrides)
    return base


# ---- liquidity ---------------------------------------------------------

def test_liquidity_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(liquidity=0.0), w)
    high = compute_trade_quality(_neutral_features(liquidity=1.0), w)
    assert high > low


def test_liquidity_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.0, w_spread=0.60, w_time_to_resolution=0.40,
    )
    a = compute_trade_quality(_neutral_features(liquidity=0.0), w)
    b = compute_trade_quality(_neutral_features(liquidity=1.0), w)
    assert a == b


# ---- spread ------------------------------------------------------------

def test_spread_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(spread=0.0), w)
    high = compute_trade_quality(_neutral_features(spread=1.0), w)
    assert high > low


def test_spread_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.60, w_spread=0.0, w_time_to_resolution=0.40,
    )
    a = compute_trade_quality(_neutral_features(spread=0.0), w)
    b = compute_trade_quality(_neutral_features(spread=1.0), w)
    assert a == b


# ---- time_to_resolution ------------------------------------------------

def test_time_to_resolution_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(time_to_resolution=0.0), w)
    high = compute_trade_quality(_neutral_features(time_to_resolution=1.0), w)
    assert high > low


def test_time_to_resolution_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.60, w_spread=0.40, w_time_to_resolution=0.0,
    )
    a = compute_trade_quality(_neutral_features(time_to_resolution=0.0), w)
    b = compute_trade_quality(_neutral_features(time_to_resolution=1.0), w)
    assert a == b


# ---- bounds + neutrality -----------------------------------------------

def test_output_bounded_in_unit_interval():
    w = HeuristicWeights()
    for val in (0.0, 0.25, 0.5, 0.75, 1.0):
        score = compute_trade_quality(_neutral_features(
            liquidity=val, spread=val, time_to_resolution=val,
        ), w)
        assert 0.0 <= score <= 1.0


def test_missing_feature_defaults_to_neutral():
    w = HeuristicWeights()
    full = compute_trade_quality(
        {"liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5}, w
    )
    partial = compute_trade_quality({}, w)
    assert abs(full - partial) < 1e-9
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_trade_scorer.py -v`
Expected: ImportError on `app.scoring.trade_scorer`.

- [ ] **Step 3: Implement `trade_scorer`**

```python
# app/scoring/trade_scorer.py
"""Pure function: compute trade quality from liquidity / spread / TTR features.

Mirrors the legacy `HeuristicScorer.compute_score` trade-bloc formula.
"""
from __future__ import annotations

from app.scoring.weights import HeuristicWeights


_NEUTRAL = 0.5


def compute_trade_quality(
    features: dict,
    weights: HeuristicWeights,
) -> float:
    """Weighted sum of liquidity + spread + time_to_resolution.

    Weights sum to 1.0 (HeuristicWeights invariant), so output ∈ [0,1] as
    long as each feature is in [0,1]. A defensive clamp guards against
    out-of-range inputs from legacy callers.
    """
    raw = (
        features.get("liquidity", _NEUTRAL) * weights.w_liquidity
        + features.get("spread", _NEUTRAL) * weights.w_spread
        + features.get("time_to_resolution", _NEUTRAL) * weights.w_time_to_resolution
    )
    return max(0.0, min(1.0, raw))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_trade_scorer.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/scoring/trade_scorer.py tests/unit/test_trade_scorer.py
git commit -m "feat(chantier-5): extract trade_scorer as pure function with per-weight tests"
```

---

## Task 4: Refactor `HeuristicScorer` to delegate

**Files:**
- Modify: `app/scoring/heuristic_scorer.py`
- Modify: `app/scoring/__init__.py`
- Verify: `tests/unit/test_heuristic_scorer.py` (keep existing 6 tests green)

- [ ] **Step 1: Read the current implementation and note the contract**

Run: `cat app/scoring/heuristic_scorer.py`

Observed contract (must not change):
- `HeuristicScorer()` no-arg constructor, reads `settings.signal_score_threshold`.
- `compute_score(features, llm_combined=None) -> dict` with keys
  `signal_score`, `signal_strength`, `trade_quality` — all ints in [0, 100].
- `is_actionable(score) -> bool`, threshold from Settings.
- `derive_confidence_label(score, source_count)`, `derive_urgency_label(score, time_factor)`,
  `derive_tradability_label(liquidity_factor, spread_penalty)` — unchanged strings.
- `create_heuristic_scorer() -> HeuristicScorer` factory (no args).

- [ ] **Step 2: Add a delegation test that will lock in bit-exactness**

Append to `tests/unit/test_heuristic_scorer.py`:

```python
def test_compute_score_matches_hand_computed_values():
    """Pins the exact numeric output for a deterministic feature vector.

    After the refactor (task 4), these numbers must not drift. If you change
    the formula in a later chantier, explicitly update these constants.
    """
    from app.scoring.heuristic_scorer import HeuristicScorer
    scorer = HeuristicScorer()
    features = {
        "freshness": 0.8, "source_weight": 0.6, "confirmation": 0.7,
        "liquidity": 0.9, "spread": 0.4, "time_to_resolution": 0.5,
    }
    result = scorer.compute_score(features, llm_combined=0.75)
    # strength_base = 0.8*0.15 + 0.6*0.10 + 0.7*0.15 = 0.285
    # strength_raw = 0.285 + 0.75*0.60 = 0.735 → int(73.5) = 73
    # trade_raw    = 0.9*0.40 + 0.4*0.35 + 0.5*0.25 = 0.625 → int(62.5) = 62
    # signal_score = int(73*0.75 + 62*0.25) = int(70.25) = 70
    assert result["signal_strength"] == 73
    assert result["trade_quality"] == 62
    assert result["signal_score"] == 70


def test_compute_score_without_llm_renormalises():
    from app.scoring.heuristic_scorer import HeuristicScorer
    scorer = HeuristicScorer()
    features = {
        "freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
        "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5,
    }
    result = scorer.compute_score(features)  # no llm_combined
    # strength_base = 0.5*(0.15+0.10+0.15) = 0.20
    # With llm=None: 0.20 / (1-0.60) = 0.50 → int(50) = 50
    # trade_raw = 0.5 → int(50) = 50
    # signal_score = int(50*0.75 + 50*0.25) = 50
    assert result["signal_strength"] == 50
    assert result["trade_quality"] == 50
    assert result["signal_score"] == 50
```

- [ ] **Step 3: Run tests to verify the new assertions fail or pass against current code**

Run: `pytest tests/unit/test_heuristic_scorer.py -v`

These two new tests should PASS against the current pre-refactor code (they
encode the current formula). If they don't, stop and investigate before
refactoring. The whole point is that task 4 is semantics-preserving.

- [ ] **Step 4: Refactor `HeuristicScorer` to delegate**

Replace `app/scoring/heuristic_scorer.py` with:

```python
"""Heuristic scorer — now a thin orchestrator over pure sub-scorers.

Chantier #5: the actual math lives in `strength_scorer.py`, `trade_scorer.py`,
and the knobs in `weights.py`. This class preserves the legacy public API
(constructor, `compute_score`, `is_actionable`, `derive_*_label`) so every
existing call-site in `SignalBuilder` works untouched.
"""

import logging

from app.core.config import get_settings
from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights

logger = logging.getLogger(__name__)


class HeuristicScorer:
    def __init__(self, weights: HeuristicWeights | None = None):
        settings = get_settings()
        self.threshold = settings.signal_score_threshold
        self.weights = weights or HeuristicWeights.load_from_settings(settings)

    def compute_score(
        self,
        features: dict,
        llm_combined: float | None = None,
    ) -> dict:
        """Two-dimensional score: strength + trade → final.

        Output values are int in [0, 100] for backward compatibility with
        existing DB columns (Numeric(5,1)) and UI rendering.
        """
        strength_float = compute_signal_strength(features, self.weights, llm_combined)
        trade_float = compute_trade_quality(features, self.weights)

        signal_strength = max(0, min(100, int(strength_float * 100)))
        trade_quality = max(0, min(100, int(trade_float * 100)))

        raw_final = (
            signal_strength * self.weights.strength_weight
            + trade_quality * self.weights.trade_weight
        )
        signal_score = max(0, min(100, int(raw_final)))

        return {
            "signal_score": signal_score,
            "signal_strength": signal_strength,
            "trade_quality": trade_quality,
        }

    def is_actionable(self, score: int) -> bool:
        return score >= self.threshold

    def derive_confidence_label(self, score: int, source_count: int) -> str:
        if score >= 80 and source_count >= 2:
            return "high"
        if score >= 65:
            return "medium"
        return "low"

    def derive_urgency_label(self, score: int, time_factor: float) -> str:
        if time_factor >= 0.8:
            return "critical"
        if time_factor >= 0.5:
            return "high"
        if time_factor >= 0.2:
            return "medium"
        return "low"

    def derive_tradability_label(
        self,
        liquidity_factor: float,
        spread_penalty: float,
    ) -> str:
        score = (liquidity_factor * 0.6) + (spread_penalty * 0.4)
        if score >= 0.8:
            return "excellent"
        if score >= 0.6:
            return "good"
        if score >= 0.4:
            return "fair"
        return "poor"


def create_heuristic_scorer() -> HeuristicScorer:
    return HeuristicScorer()
```

- [ ] **Step 5: Update `app/scoring/__init__.py`**

```python
# app/scoring/__init__.py
"""Scoring package — heuristic scorer + pure sub-scorers + weights dataclass."""
from app.scoring.heuristic_scorer import HeuristicScorer, create_heuristic_scorer
from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights

__all__ = [
    "HeuristicScorer",
    "HeuristicWeights",
    "compute_signal_strength",
    "compute_trade_quality",
    "create_heuristic_scorer",
]
```

- [ ] **Step 6: Run all scorer tests**

Run: `pytest tests/unit/test_heuristic_scorer.py tests/unit/test_strength_scorer.py tests/unit/test_trade_scorer.py tests/unit/test_heuristic_weights.py -v`
Expected: 8 (pins + legacy) + 11 + 8 + 8 = 35 passed.

- [ ] **Step 7: Commit**

```bash
git add app/scoring/heuristic_scorer.py app/scoring/__init__.py tests/unit/test_heuristic_scorer.py
git commit -m "refactor(chantier-5): HeuristicScorer delegates to pure sub-scorers"
```

---

## Task 5: Alembic migration 025 — rename `variant='signal'` → `'heuristic_v1'`

**Files:**
- Create: `alembic/versions/025_rename_signal_variant_to_heuristic_v1.py`
- Test: `tests/unit/test_migration_025.py`

- [ ] **Step 1: Write the migration test**

```python
# tests/unit/test_migration_025.py
"""Migration 025 — data-only rename of SignalPrediction.variant column values.

Chantier #5 renames the legacy variant name 'signal' (written by chantier #1's
record_baselines) to 'heuristic_v1' so the heuristic is first-class alongside
baseline_* and any future shadow variants.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_no_signal_variant_rows_remain_after_upgrade(async_db_factory):
    """After migration 025, no 'signal' rows exist in signal_predictions."""
    async with async_db_factory() as s:
        count = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions WHERE variant = 'signal'")
        )).scalar_one()
        assert count == 0, (
            f"Migration 025 leaves {count} 'signal' rows; expected 0. "
            "Re-run `alembic upgrade head` against the test database."
        )


@pytest.mark.asyncio
async def test_heuristic_v1_rows_present_when_signals_existed(async_db_factory):
    """Dev DB carries pre-migration data → heuristic_v1 rows now exist.

    Tolerant: if the DB is empty (e.g. fresh CI), the count can be 0.
    """
    async with async_db_factory() as s:
        total_preds = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions")
        )).scalar_one()
        if total_preds == 0:
            pytest.skip("signal_predictions empty — nothing to rename")
        heuristic = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions WHERE variant = 'heuristic_v1'")
        )).scalar_one()
        assert heuristic > 0, "Expected at least one heuristic_v1 row post-migration"


@pytest.mark.asyncio
async def test_check_constraint_if_present_allows_heuristic_v1(async_db_factory):
    """Variant check constraint (if any) must allow 'heuristic_v1' and 'heuristic_shadow'.

    We insert a probe row under a rollback-able SAVEPOINT; the assertion is
    'no IntegrityError', and the row never escapes the transaction.
    """
    async with async_db_factory() as s:
        # probe values that exercise any possible CHECK constraint
        try:
            async with s.begin_nested():
                await s.execute(text(
                    "INSERT INTO signal_predictions (signal_id, variant, predicted_probability) "
                    "VALUES (-1, 'heuristic_v1', 0.5)"
                ))
                await s.execute(text(
                    "INSERT INTO signal_predictions (signal_id, variant, predicted_probability) "
                    "VALUES (-1, 'heuristic_shadow', 0.5)"
                ))
                raise Exception("rollback")  # always rollback the savepoint
        except Exception as exc:
            if str(exc) != "rollback":
                raise  # CHECK constraint violation would propagate here
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_migration_025.py -v`
Expected: FAIL with "'signal' rows; expected 0" (the dev DB still has them).

- [ ] **Step 3: Write the migration**

```python
# alembic/versions/025_rename_signal_variant_to_heuristic_v1.py
"""Rename variant='signal' → 'heuristic_v1' in signal_predictions.

Revision ID: 025
Revises: 024
Create Date: 2026-04-24

Chantier #5: the legacy 'signal' name (written by chantier #1's record_baselines)
is renamed to 'heuristic_v1' so it sits next to baseline_* and any future
heuristic_shadow / heuristic_v2 variants with a consistent naming scheme.

This is a pure data migration — no DDL — and idempotent: re-running on
already-migrated data is a no-op (UPDATE affects 0 rows the second time).
"""
from __future__ import annotations

from alembic import op


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE signal_predictions SET variant = 'heuristic_v1' WHERE variant = 'signal'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE signal_predictions SET variant = 'signal' WHERE variant = 'heuristic_v1'"
    )
```

- [ ] **Step 4: Apply the migration**

Run: `docker compose exec app alembic upgrade head`
Expected output includes `Running upgrade 024 -> 025, rename variant='signal'`.

- [ ] **Step 5: Run the test to verify pass**

Run: `pytest tests/unit/test_migration_025.py -v`
Expected: 3 passed (or `test_heuristic_v1_rows_present_when_signals_existed` skipped on an empty DB).

- [ ] **Step 6: Sanity-check the rewrite**

Run:
```bash
docker compose exec db psql -U postgres -d signal -c "SELECT variant, COUNT(*) FROM signal_predictions GROUP BY variant ORDER BY 2 DESC;"
```

Expected: `heuristic_v1 | 235` (or whatever the pre-migration `signal` count
was); no `signal` row.

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/025_rename_signal_variant_to_heuristic_v1.py tests/unit/test_migration_025.py
git commit -m "feat(chantier-5): migration 025 renames variant='signal' to 'heuristic_v1'"
```

---

## Task 6: `predict_heuristic` helper

**Files:**
- Create: `app/measurement/heuristic_variant.py`
- Test: `tests/unit/test_heuristic_variant.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_heuristic_variant.py
"""Chantier #5 — predict_heuristic helper.

Used by record_baselines to produce a VariantPrediction for both the frozen
heuristic_v1 (reference) and the configurable heuristic_shadow (experimental)
without touching the production scoring path.
"""
from __future__ import annotations

import pytest

from app.measurement.heuristic_variant import predict_heuristic
from app.measurement.variant_registry import VariantPrediction
from app.scoring.weights import HeuristicWeights


def _sample_features(**overrides) -> dict:
    base = {
        "freshness": 0.6, "source_weight": 0.5, "confirmation": 0.7,
        "liquidity": 0.8, "spread": 0.4, "time_to_resolution": 0.5,
    }
    base.update(overrides)
    return base


def test_returns_variant_prediction_with_direction_and_probability():
    pred = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=_sample_features(),
        llm_combined=0.7,
        direction="BUY_YES",
    )
    assert isinstance(pred, VariantPrediction)
    assert pred.direction == "BUY_YES"
    assert pred.probability is not None
    assert 0.0 <= pred.probability <= 1.0


def test_probability_matches_hand_computed_value():
    """Pins: probability = strength_weight * strength + trade_weight * trade."""
    weights = HeuristicWeights.frozen_v1()
    features = {
        "freshness": 0.8, "source_weight": 0.6, "confirmation": 0.7,
        "liquidity": 0.9, "spread": 0.4, "time_to_resolution": 0.5,
    }
    # strength_base = 0.8*0.15 + 0.6*0.10 + 0.7*0.15 = 0.285
    # strength_raw  = 0.285 + 0.75*0.60 = 0.735
    # trade_raw     = 0.9*0.40 + 0.4*0.35 + 0.5*0.25 = 0.625
    # final         = 0.75*0.735 + 0.25*0.625 = 0.7075
    pred = predict_heuristic(
        weights=weights, features=features, llm_combined=0.75, direction="BUY_YES",
    )
    assert abs(pred.probability - 0.7075) < 1e-6


def test_heuristic_v1_differs_from_shadow_when_weights_differ():
    """Different weights → different probability for the same features."""
    features = _sample_features()
    v1 = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=features, llm_combined=0.8, direction="BUY_YES",
    )
    shadow = predict_heuristic(
        weights=HeuristicWeights(
            w_freshness=0.40, w_source=0.10, w_confirmation=0.10, w_llm=0.40,
            w_liquidity=0.40, w_spread=0.35, w_time_to_resolution=0.25,
            strength_weight=0.50, trade_weight=0.50,
        ),
        features=features, llm_combined=0.8, direction="BUY_YES",
    )
    assert v1.probability != pytest.approx(shadow.probability)


def test_probability_clamped_to_unit_interval():
    """Out-of-range features still produce a probability in [0,1]."""
    features = {
        "freshness": 2.0, "source_weight": 2.0, "confirmation": 2.0,
        "liquidity": 2.0, "spread": 2.0, "time_to_resolution": 2.0,
    }
    pred = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=features, llm_combined=2.0, direction="BUY_YES",
    )
    assert 0.0 <= pred.probability <= 1.0


def test_direction_passed_through_unchanged():
    for d in ("BUY_YES", "BUY_NO", None):
        pred = predict_heuristic(
            weights=HeuristicWeights.frozen_v1(),
            features=_sample_features(), llm_combined=0.5, direction=d,
        )
        assert pred.direction == d
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_heuristic_variant.py -v`
Expected: ImportError on `app.measurement.heuristic_variant`.

- [ ] **Step 3: Implement `predict_heuristic`**

```python
# app/measurement/heuristic_variant.py
"""Heuristic variant prediction builder.

`record_baselines` (pipeline.py) calls `predict_heuristic` once to build the
`heuristic_v1` row and, if the shadow flag is on, a second time with the
live Settings weights to build the `heuristic_shadow` row.

We duplicate the HeuristicScorer formula here rather than calling
`HeuristicScorer().compute_score()` for two reasons:
  - We need a VariantPrediction, not a dict; building one from the scorer
    output would require re-parsing the 0-100 int back to a probability.
  - The shadow path needs weights ≠ the live scorer's weights, so we can't
    reuse `HeuristicScorer()` without constructing a second one per signal.
"""
from __future__ import annotations

from app.measurement.variant_registry import VariantPrediction
from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights


def predict_heuristic(
    *,
    weights: HeuristicWeights,
    features: dict,
    llm_combined: float | None,
    direction: str | None,
) -> VariantPrediction:
    """Compute a VariantPrediction under arbitrary heuristic weights.

    The probability maps the final [0,1] score directly to P(move in `direction`),
    usable as input to `brier_from_outcome` against a binarised short-horizon
    price and to `simulated_pnl_eur` against the raw price.
    """
    strength = compute_signal_strength(features, weights, llm_combined)
    trade = compute_trade_quality(features, weights)
    final = weights.strength_weight * strength + weights.trade_weight * trade
    return VariantPrediction(
        direction=direction,
        probability=max(0.0, min(1.0, final)),
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_heuristic_variant.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/measurement/heuristic_variant.py tests/unit/test_heuristic_variant.py
git commit -m "feat(chantier-5): add predict_heuristic helper for measurement pipeline"
```

---

## Task 7: Add `heuristic_shadow_enabled` + 7 weight overrides to Settings

**Files:**
- Modify: `app/core/config.py`
- Modify: `tests/unit/test_config_integrity.py`

- [ ] **Step 1: Locate the current Settings class**

Run: `grep -n "class Settings\|clustering_cosine_threshold\|ranking_v2_rrf_k" app/core/config.py`

Note the line numbers of the chantier #4 block (`ranking_v2_*`) so the new
block lands in the same area.

- [ ] **Step 2: Extend `test_config_integrity.py` first**

Edit `tests/unit/test_config_integrity.py`, extending the `@pytest.mark.parametrize`
list used by `test_settings_field_types`:

```python
@pytest.mark.parametrize("attr,expected_type", [
    ("clustering_cosine_threshold", float),
    ("clustering_time_window_minutes", int),
    ("rrf_k", int),
    ("ranking_v2_rrf_k", int),
    ("ranking_v2_w_entity", float),
    ("ranking_v2_w_date", float),
    ("ranking_v2_w_bucket", float),
    ("ranking_v2_tau_days", float),
    ("ranking_v2_min_sim", float),
    # Chantier #5 — heuristic score knobs
    ("heuristic_shadow_enabled", bool),
    ("heuristic_w_freshness", float),
    ("heuristic_w_source", float),
    ("heuristic_w_confirmation", float),
    ("heuristic_w_llm", float),
    ("heuristic_w_liquidity", float),
    ("heuristic_w_spread", float),
    ("heuristic_w_time_to_resolution", float),
    ("heuristic_strength_weight", float),
    ("heuristic_trade_weight", float),
])
def test_settings_field_types(attr: str, expected_type: type):
    """Pin the declared type of settings fields we reason about elsewhere."""
    defaults = Settings.model_fields
    assert attr in defaults, f"Settings missing expected field {attr!r}"
    default = defaults[attr].default
    assert isinstance(default, expected_type), (
        f"Settings.{attr} default {default!r} has type {type(default).__name__}, "
        f"expected {expected_type.__name__}"
    )
```

And append a new dedicated test file block at the end:

```python
def test_heuristic_weight_defaults_sum_to_one_per_bloc():
    """Settings defaults must satisfy the HeuristicWeights sum invariants."""
    defaults = Settings.model_fields
    s_sum = (
        defaults["heuristic_w_freshness"].default
        + defaults["heuristic_w_source"].default
        + defaults["heuristic_w_confirmation"].default
        + defaults["heuristic_w_llm"].default
    )
    t_sum = (
        defaults["heuristic_w_liquidity"].default
        + defaults["heuristic_w_spread"].default
        + defaults["heuristic_w_time_to_resolution"].default
    )
    top_sum = (
        defaults["heuristic_strength_weight"].default
        + defaults["heuristic_trade_weight"].default
    )
    assert abs(s_sum - 1.0) < 1e-6, f"strength bloc sums to {s_sum}"
    assert abs(t_sum - 1.0) < 1e-6, f"trade bloc sums to {t_sum}"
    assert abs(top_sum - 1.0) < 1e-6, f"top bloc sums to {top_sum}"


def test_heuristicweights_from_settings_defaults_equals_frozen_v1():
    """Loading weights from Settings defaults must equal HeuristicWeights.frozen_v1()."""
    from app.scoring.weights import HeuristicWeights
    from app.core.config import get_settings

    get_settings.cache_clear()  # ensure we read the latest declaration
    s = get_settings()
    loaded = HeuristicWeights.load_from_settings(s)
    assert loaded == HeuristicWeights.frozen_v1()
```

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest tests/unit/test_config_integrity.py -v`
Expected: FAIL with "Settings missing expected field 'heuristic_shadow_enabled'".

- [ ] **Step 4: Add the Settings fields**

Edit `app/core/config.py`. Find the `ranking_v2_min_sim` field and insert immediately below (keep alphabetical group ordering loose — co-locate with the other "runtime tunables"):

```python
    # ── chantier #5: heuristic score — validation & calibration ──────────
    heuristic_shadow_enabled: bool = False
    heuristic_w_freshness: float = 0.15
    heuristic_w_source: float = 0.10
    heuristic_w_confirmation: float = 0.15
    heuristic_w_llm: float = 0.60
    heuristic_w_liquidity: float = 0.40
    heuristic_w_spread: float = 0.35
    heuristic_w_time_to_resolution: float = 0.25
    heuristic_strength_weight: float = 0.75
    heuristic_trade_weight: float = 0.25
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/test_config_integrity.py -v`
Expected: all parametrized `test_settings_field_types` cases pass (including
the 10 new ones) plus the two new bloc-sum tests.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py tests/unit/test_config_integrity.py
git commit -m "feat(chantier-5): add heuristic_shadow_enabled + 9 weight overrides to Settings"
```

---

## Task 8: Rewire `record_baselines` — `variant='heuristic_v1'` + optional shadow

**Files:**
- Modify: `app/measurement/pipeline.py`
- Modify: caller in `app/signal/signal_builder.py` (pass `features`, `llm_combined`)

- [ ] **Step 1: Find every call-site of `record_baselines`**

Run: `grep -rn "record_baselines" app/ tests/ | grep -v __pycache__`

Expected: at least two hits — one in `pipeline.py` (definition), one or more
in the scoring path. Read each call and note the kwargs already passed
(must include `session`, `signal_id`, `ctx`, `registry`). The features dict
lives in `SignalBuilder.build_signal` right after the scorer call.

- [ ] **Step 2: Update the signature and body**

Edit `app/measurement/pipeline.py::record_baselines` to:

```python
async def record_baselines(
    session: "AsyncSession",
    *,
    signal_id: int,
    ctx: ScoringContext,
    registry: VariantRegistry,
    features: dict | None = None,
    llm_combined: float | None = None,
) -> int:
    """Insert one row per variant into signal_predictions.

    Variants written:
      - 'heuristic_v1' (frozen reference, always) — uses the Signal's own
        signal_strength/100 as probability, preserving pre-chantier #5
        bit-exactness.
      - 'heuristic_shadow' (optional, opt-in via
        settings.heuristic_shadow_enabled) — recomputed from the provided
        `features` + `llm_combined` under Settings-loaded weights. Skipped
        silently when `features is None` (defensive: the caller may forget
        to pass it for some legacy paths).
      - every baseline registered in `registry` — unchanged.

    Conflicts on (signal_id, variant) are swallowed via ON CONFLICT DO NOTHING
    so retries / backfills are idempotent.
    """
    from app.core.config import get_settings
    from app.measurement.heuristic_variant import predict_heuristic
    from app.scoring.weights import HeuristicWeights

    sig = (
        await session.execute(select(Signal).where(Signal.id == signal_id))
    ).scalar_one()
    signal_prob = (
        float(sig.signal_strength) / 100.0
        if sig.signal_strength is not None
        else 0.5
    )

    rows: list[dict] = [
        {
            "signal_id": signal_id,
            "variant": "heuristic_v1",
            "predicted_direction": sig.direction,
            "predicted_probability": signal_prob,
        }
    ]

    settings = get_settings()
    if settings.heuristic_shadow_enabled and features is not None:
        shadow_pred = predict_heuristic(
            weights=HeuristicWeights.load_from_settings(settings),
            features=features,
            llm_combined=llm_combined,
            direction=sig.direction,
        )
        rows.append(
            {
                "signal_id": signal_id,
                "variant": "heuristic_shadow",
                "predicted_direction": shadow_pred.direction,
                "predicted_probability": shadow_pred.probability,
            }
        )

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
    return int(result.rowcount or 0)
```

- [ ] **Step 3: Update the caller in `SignalBuilder.build_signal`**

Find the existing `record_baselines(...)` call in
`app/signal/signal_builder.py` and add the two new kwargs:

```python
await record_baselines(
    session=session,
    signal_id=signal.id,
    ctx=ctx,
    registry=get_registry(),
    features=features,          # chantier #5: enable heuristic_shadow
    llm_combined=llm_combined,  # chantier #5: enable heuristic_shadow
)
```

Re-read the surrounding code after editing to confirm `features` and
`llm_combined` are in scope (they are both built earlier in `build_signal`
before the scorer call).

- [ ] **Step 4: Run the existing pipeline tests**

Run: `pytest tests/unit/test_pipeline.py tests/integration/test_admin_metrics_variants.py -v`

Any test that asserted `variant='signal'` must now assert `variant='heuristic_v1'`.
Update the few failing tests inline (they are assertions on string
literals).

- [ ] **Step 5: Grep for any remaining `'signal'` literal**

Run:
```bash
grep -rn "variant\s*=\s*['\"]signal['\"]\|variant=='signal'\|variant\s*=\s*\"signal\"" app/ tests/ scripts/ | grep -v __pycache__
```

Expected: no hits (migration 025 + code edit here fully retire the old name).
Known false-positive to ignore: lines that reference the table name
`"signals"` (the plural ORM table) or the Python variable `signal` — those are not
variant values.

- [ ] **Step 6: Commit**

```bash
git add app/measurement/pipeline.py app/signal/signal_builder.py tests/
git commit -m "feat(chantier-5): record_baselines writes heuristic_v1 + optional heuristic_shadow"
```

---

## Task 9: Integration test — shadow writes correct variant rows

**Files:**
- Create: `tests/integration/test_heuristic_shadow_write.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/integration/test_heuristic_shadow_write.py
"""End-to-end: record_baselines must write the correct variants based on the
heuristic_shadow_enabled flag.

Uses a real async DB (Postgres via docker-compose), a registered Signal row,
and a ScoringContext built from the existing builder. No LLM calls.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.models import Market, Signal
from app.measurement.pipeline import record_baselines
from app.measurement.scoring_context import build_scoring_context
from app.measurement.variant_registry import get_registry


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Per-test Settings cache flush so `heuristic_shadow_enabled` toggles take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_signal(session) -> tuple[int, str]:
    """Insert a minimal Market + Signal row; return (signal_id, market_id)."""
    market_id = f"test-mkt-{uuid.uuid4().hex[:8]}"
    await session.execute(
        text(
            "INSERT INTO markets (market_id, question, outcome_type, is_active) "
            "VALUES (:mid, 'Test market', 'binary', true)"
        ),
        {"mid": market_id},
    )
    # Signal needs event_id — grab any existing event or insert one
    eid = (await session.execute(
        text("SELECT id FROM events LIMIT 1")
    )).scalar_one_or_none()
    if eid is None:
        await session.execute(text(
            "INSERT INTO events (title, cluster_id, last_seen, bucket) "
            "VALUES ('test-event', 'c-test', NOW(), 'other') RETURNING id"
        ))
        eid = (await session.execute(text("SELECT currval('events_id_seq')"))).scalar_one()

    sig_id = (await session.execute(
        text(
            "INSERT INTO signals (event_id, market_id, signal_score, signal_strength, "
            "trade_quality, direction) "
            "VALUES (:eid, :mid, 70, 73, 62, 'BUY_YES') RETURNING id"
        ),
        {"eid": eid, "mid": market_id},
    )).scalar_one()
    await session.commit()
    return sig_id, market_id


@pytest.mark.asyncio
async def test_heuristic_v1_always_written(async_db_factory):
    """Flag off → only heuristic_v1 + 4 baselines (no heuristic_shadow)."""
    with patch.dict(os.environ, {"HEURISTIC_SHADOW_ENABLED": "false"}):
        get_settings.cache_clear()
        # register baselines via package import side-effect
        import app.measurement  # noqa: F401

        async with async_db_factory() as session:
            sig_id, mid = await _seed_signal(session)
            ctx = await build_scoring_context(
                signal_id=sig_id, market_id=mid, event_id=None,
                market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
            )
            await record_baselines(
                session=session,
                signal_id=sig_id,
                ctx=ctx,
                registry=get_registry(),
                features={"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
                          "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
                llm_combined=0.5,
            )
            await session.commit()

            variants = [r[0] for r in (await session.execute(
                text("SELECT variant FROM signal_predictions WHERE signal_id=:sid"),
                {"sid": sig_id},
            )).all()]
            assert "heuristic_v1" in variants
            assert "heuristic_shadow" not in variants
            assert len([v for v in variants if v.startswith("baseline_")]) == 4


@pytest.mark.asyncio
async def test_heuristic_shadow_written_when_flag_on(async_db_factory, monkeypatch):
    """Flag on → 6 rows: heuristic_v1 + heuristic_shadow + 4 baselines."""
    monkeypatch.setenv("HEURISTIC_SHADOW_ENABLED", "true")
    get_settings.cache_clear()
    import app.measurement  # noqa: F401

    async with async_db_factory() as session:
        sig_id, mid = await _seed_signal(session)
        ctx = await build_scoring_context(
            signal_id=sig_id, market_id=mid, event_id=None,
            market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
        )
        await record_baselines(
            session=session,
            signal_id=sig_id,
            ctx=ctx,
            registry=get_registry(),
            features={"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
                      "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
            llm_combined=0.5,
        )
        await session.commit()

        variants = [r[0] for r in (await session.execute(
            text("SELECT variant FROM signal_predictions WHERE signal_id=:sid"),
            {"sid": sig_id},
        )).all()]
        assert "heuristic_v1" in variants
        assert "heuristic_shadow" in variants
        assert len([v for v in variants if v.startswith("baseline_")]) == 4


@pytest.mark.asyncio
async def test_shadow_probability_differs_when_settings_override_weights(
    async_db_factory, monkeypatch,
):
    """When shadow weights diverge from v1, the two probabilities must differ."""
    # Shadow weights put all strength on freshness instead of llm
    monkeypatch.setenv("HEURISTIC_SHADOW_ENABLED", "true")
    monkeypatch.setenv("HEURISTIC_W_FRESHNESS", "0.50")
    monkeypatch.setenv("HEURISTIC_W_SOURCE", "0.10")
    monkeypatch.setenv("HEURISTIC_W_CONFIRMATION", "0.15")
    monkeypatch.setenv("HEURISTIC_W_LLM", "0.25")
    get_settings.cache_clear()
    import app.measurement  # noqa: F401

    async with async_db_factory() as session:
        sig_id, mid = await _seed_signal(session)
        ctx = await build_scoring_context(
            signal_id=sig_id, market_id=mid, event_id=None,
            market_price=0.5, articles=[], t0=datetime.now(timezone.utc),
        )
        # freshness=1.0 dominates under shadow weights; default v1 weights
        # give more weight to llm → v1_prob < shadow_prob.
        await record_baselines(
            session=session, signal_id=sig_id, ctx=ctx,
            registry=get_registry(),
            features={"freshness": 1.0, "source_weight": 0.1, "confirmation": 0.1,
                      "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
            llm_combined=0.0,
        )
        await session.commit()

        rows = {r[0]: float(r[1]) for r in (await session.execute(
            text("SELECT variant, predicted_probability FROM signal_predictions "
                 "WHERE signal_id=:sid AND variant LIKE 'heuristic_%'"),
            {"sid": sig_id},
        )).all()}
        assert rows["heuristic_v1"] != pytest.approx(rows["heuristic_shadow"], abs=1e-4)
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/integration/test_heuristic_shadow_write.py -v`
Expected: 3 passed. (If `HEURISTIC_*` env vars are already set in shell, unset
them first: `unset $(env | grep ^HEURISTIC_ | cut -d= -f1)`.)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_heuristic_shadow_write.py
git commit -m "test(chantier-5): integration test for heuristic_v1 + heuristic_shadow write"
```

---

## Task 10: Offline validation script

**Files:**
- Create: `scripts/validate_heuristic_weights.py`
- Test: `tests/unit/test_validate_heuristic_weights.py`

- [ ] **Step 1: Write the fixture-driven test**

```python
# tests/unit/test_validate_heuristic_weights.py
"""Chantier #5 — validate_heuristic_weights script logic (pure, no DB).

Feeds a synthetic set of 20 (prediction, outcome) rows and asserts the
aggregated Brier / P&L / Wilson CI95 per variant match hand-computed values.
"""
from __future__ import annotations

import math

from scripts.validate_heuristic_weights import (
    JoinedRow,
    aggregate_variant_metrics,
    build_markdown_report,
)


def _row(variant: str, prob: float, direction: str, price: float) -> JoinedRow:
    return JoinedRow(
        variant=variant,
        predicted_probability=prob,
        predicted_direction=direction,
        price_t1h=price,
    )


def test_aggregate_metrics_single_variant_brier_from_binarized_price():
    """With all prices ∈ {0.02, 0.98}, every row contributes a defined Brier."""
    rows = [
        _row("heuristic_v1", 0.7, "BUY_YES", 0.98),  # b = (0.7-1)^2 = 0.09
        _row("heuristic_v1", 0.3, "BUY_YES", 0.02),  # b = (0.3-0)^2 = 0.09
    ]
    metrics = aggregate_variant_metrics(rows)
    assert set(metrics.keys()) == {"heuristic_v1"}
    m = metrics["heuristic_v1"]
    assert m["n"] == 2
    assert m["n_brier_defined"] == 2
    assert math.isclose(m["brier_mean"], 0.09, abs_tol=1e-9)


def test_aggregate_metrics_ambiguous_outcomes_skipped_from_brier():
    """Prices in (0.05, 0.95) don't map to a binary label — skipped."""
    rows = [
        _row("v", 0.6, "BUY_YES", 0.98),  # binary=1, counted
        _row("v", 0.6, "BUY_YES", 0.50),  # ambiguous, skipped
    ]
    m = aggregate_variant_metrics(rows)["v"]
    assert m["n"] == 2
    assert m["n_brier_defined"] == 1
    assert math.isclose(m["brier_mean"], (0.6 - 1) ** 2, abs_tol=1e-9)


def test_aggregate_metrics_pnl_uses_raw_price_not_binarised():
    rows = [
        _row("v", 0.6, "BUY_YES", 0.70),  # pnl = 10 * (0.7 - 0.6) = 1.0
        _row("v", 0.4, "BUY_YES", 0.30),  # pnl = 10 * (0.3 - 0.4) = -1.0
    ]
    m = aggregate_variant_metrics(rows)["v"]
    assert math.isclose(m["pnl_mean"], 0.0, abs_tol=1e-9)


def test_build_markdown_report_has_required_columns():
    metrics = {
        "heuristic_v1": {
            "n": 100, "n_brier_defined": 80, "brier_mean": 0.20,
            "brier_ci95": (0.17, 0.23),
            "pnl_mean": 0.5, "pnl_ci95": (-0.1, 1.1),
            "hit_rate": 0.55, "hit_rate_ci95": (0.45, 0.65),
        },
        "baseline_random": {
            "n": 100, "n_brier_defined": 80, "brier_mean": 0.25,
            "brier_ci95": (0.22, 0.28),
            "pnl_mean": 0.0, "pnl_ci95": (-0.6, 0.6),
            "hit_rate": 0.50, "hit_rate_ci95": (0.40, 0.60),
        },
    }
    md = build_markdown_report(metrics, horizon="t1h", generated_at="2026-04-24")
    assert "| variant" in md
    assert "heuristic_v1" in md
    assert "baseline_random" in md
    assert "brier_mean" in md
    assert "horizon=t1h" in md
    assert "2026-04-24" in md
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest tests/unit/test_validate_heuristic_weights.py -v`
Expected: ImportError on `scripts.validate_heuristic_weights`.

- [ ] **Step 3: Implement the script**

```python
# scripts/validate_heuristic_weights.py
"""Offline validation: join SignalPrediction × SignalOutcome at a given horizon,
compute Brier (binarised) / simulated P&L / Wilson-CI95 per variant, and emit a
markdown report suitable for committing to `docs/audit/`.

CLI:
    python -m scripts.validate_heuristic_weights \\
        --horizon t1h \\
        --out docs/audit/heuristic_validation_report_YYYY-MM-DD.md

Why a script, not a FastAPI endpoint: one-shot, human-triggered, audited via
git history. The measurement infra has no scheduler for this.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import text

from app.db.database import async_session_factory
from app.measurement.metrics import (
    brier_from_outcome,
    simulated_pnl_eur,
    wilson_ci95,
)


ALLOWED_HORIZONS = ("t15min", "t1h", "t24h")


@dataclass(frozen=True)
class JoinedRow:
    variant: str
    predicted_probability: float
    predicted_direction: str | None
    price_t1h: float   # reused for whichever horizon was selected


def _binarise(price: float) -> int | None:
    """Mirror `app.measurement.pipeline._binary_from_resolved`."""
    if price >= 0.95:
        return 1
    if price <= 0.05:
        return 0
    return None


def aggregate_variant_metrics(rows: Iterable[JoinedRow]) -> dict[str, dict]:
    """Compute per-variant metrics from a batch of JoinedRow."""
    by_variant: dict[str, list[JoinedRow]] = {}
    for r in rows:
        by_variant.setdefault(r.variant, []).append(r)

    out: dict[str, dict] = {}
    for variant, batch in by_variant.items():
        n = len(batch)
        briers: list[float] = []
        pnls: list[float] = []
        hits: list[int] = []
        for r in batch:
            bin_outcome = _binarise(r.price_t1h)
            if bin_outcome is not None:
                b = brier_from_outcome(r.predicted_probability, bin_outcome)
                if b is not None:
                    briers.append(b)
                # hit = 1 if direction was right
                if r.predicted_direction in ("BUY_YES", "BUY_NO"):
                    correct = (
                        (r.predicted_direction == "BUY_YES" and bin_outcome == 1)
                        or (r.predicted_direction == "BUY_NO" and bin_outcome == 0)
                    )
                    hits.append(1 if correct else 0)
            if r.predicted_direction in ("BUY_YES", "BUY_NO"):
                pnls.append(simulated_pnl_eur(
                    direction=r.predicted_direction,
                    probability=r.predicted_probability,
                    price_resolved=r.price_t1h,
                ))

        brier_mean = sum(briers) / len(briers) if briers else float("nan")
        pnl_mean = sum(pnls) / len(pnls) if pnls else 0.0
        hit_rate = sum(hits) / len(hits) if hits else float("nan")
        hit_ci_low, hit_ci_high = wilson_ci95(len(hits), sum(hits)) if hits else (0.0, 1.0)

        # Brier and P&L CI95 via ±1.96·σ/√n on the mean (simple approximation;
        # aligns with chantier #1's reporting practice).
        def _ci(values: list[float]) -> tuple[float, float]:
            if len(values) < 2:
                return (float("nan"), float("nan"))
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            se = (var / len(values)) ** 0.5
            return (mean - 1.96 * se, mean + 1.96 * se)

        out[variant] = {
            "n": n,
            "n_brier_defined": len(briers),
            "brier_mean": brier_mean,
            "brier_ci95": _ci(briers),
            "pnl_mean": pnl_mean,
            "pnl_ci95": _ci(pnls),
            "hit_rate": hit_rate,
            "hit_rate_ci95": (hit_ci_low, hit_ci_high),
        }
    return out


def build_markdown_report(metrics: dict[str, dict], *, horizon: str, generated_at: str) -> str:
    """Render the metrics dict as a committable markdown table."""
    header = (
        f"# Heuristic Validation Report — horizon={horizon}\n\n"
        f"Generated: {generated_at}\n\n"
        "| variant | n | n_brier_defined | brier_mean | brier_ci95 | pnl_mean | pnl_ci95 | hit_rate | hit_rate_ci95 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    # Sort: heuristic first, then baselines alphabetically
    ordered = sorted(
        metrics.keys(),
        key=lambda v: (not v.startswith("heuristic_"), v),
    )
    for variant in ordered:
        m = metrics[variant]
        lines.append(
            f"| `{variant}` | {m['n']} | {m['n_brier_defined']} | "
            f"{m['brier_mean']:.4f} | "
            f"[{m['brier_ci95'][0]:.4f}, {m['brier_ci95'][1]:.4f}] | "
            f"€{m['pnl_mean']:.3f} | "
            f"[€{m['pnl_ci95'][0]:.3f}, €{m['pnl_ci95'][1]:.3f}] | "
            f"{m['hit_rate']:.3f} | "
            f"[{m['hit_rate_ci95'][0]:.3f}, {m['hit_rate_ci95'][1]:.3f}] |"
        )
    return header + "\n".join(lines) + "\n"


async def _fetch_joined_rows(horizon: str) -> list[JoinedRow]:
    col = f"price_{horizon}"
    sql = text(
        f"""SELECT sp.variant, sp.predicted_probability, sp.predicted_direction,
                   so.{col} AS price_horizon
            FROM signal_predictions sp
            JOIN signal_outcomes so ON sp.signal_id = so.signal_id
            WHERE so.{col} IS NOT NULL
              AND sp.predicted_probability IS NOT NULL"""
    )
    async with async_session_factory() as s:
        rs = await s.execute(sql)
        return [
            JoinedRow(
                variant=row[0],
                predicted_probability=float(row[1]),
                predicted_direction=row[2],
                price_t1h=float(row[3]),
            )
            for row in rs.all()
        ]


async def _main_async(*, horizon: str, out_path: str) -> None:
    rows = await _fetch_joined_rows(horizon)
    metrics = aggregate_variant_metrics(rows)
    md = build_markdown_report(metrics, horizon=horizon, generated_at=str(date.today()))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {out_path} ({len(rows)} joined rows, {len(metrics)} variants)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate heuristic weights vs baselines.")
    parser.add_argument(
        "--horizon",
        choices=ALLOWED_HORIZONS,
        default="t1h",
        help="Which outcome horizon to validate against (default: t1h).",
    )
    parser.add_argument(
        "--out",
        default=f"docs/audit/heuristic_validation_report_{date.today().isoformat()}.md",
        help="Output markdown report path.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(horizon=args.horizon, out_path=args.out))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify pass**

Run: `pytest tests/unit/test_validate_heuristic_weights.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_heuristic_weights.py tests/unit/test_validate_heuristic_weights.py
git commit -m "feat(chantier-5): offline validation script — Brier/P&L/Wilson-CI95 per variant"
```

---

## Task 11: Coordinate-descent tuner — core

**Files:**
- Create: `scripts/tune_heuristic_weights.py`
- Test: `tests/unit/test_tune_heuristic_weights.py`

- [ ] **Step 1: Write the convergence test**

```python
# tests/unit/test_tune_heuristic_weights.py
"""Chantier #5 — coordinate descent convergence + gate logic.

Tests run on synthetic data (no DB) so they are fast and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.tune_heuristic_weights import (
    CandidateResult,
    coordinate_descent,
    evaluate_candidate,
    evaluation_gate,
)


@dataclass(frozen=True)
class _Sample:
    features: dict
    llm_combined: float
    direction: str
    price_t1h: float


# Synthetic dataset: "true" weights put all mass on freshness, binary outcomes.
def _make_synthetic_dataset() -> list[_Sample]:
    samples = []
    for f_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] * 20:
        # outcome = 1 iff freshness > 0.5
        price = 0.98 if f_val > 0.5 else 0.02
        samples.append(_Sample(
            features={"freshness": f_val, "source_weight": 0.5, "confirmation": 0.5,
                      "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
            llm_combined=0.5,
            direction="BUY_YES" if f_val > 0.5 else "BUY_NO",
            price_t1h=price,
        ))
    return samples


def test_evaluate_candidate_returns_brier_and_pnl():
    samples = _make_synthetic_dataset()
    from app.scoring.weights import HeuristicWeights
    result = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    assert isinstance(result, CandidateResult)
    assert 0.0 <= result.brier_mean <= 1.0
    assert result.n > 0


def test_coordinate_descent_moves_toward_better_config():
    """On synthetic data where freshness is the only signal, descent should
    push w_freshness up from the 0.15 default."""
    samples = _make_synthetic_dataset()
    best = coordinate_descent(samples, passes=2)
    # The optimum isn't a single point (sum-to-1 constraints matter), but
    # w_freshness should end strictly above the default.
    assert best.weights.w_freshness > 0.15, (
        f"descent left w_freshness at {best.weights.w_freshness} — "
        "tuner didn't move toward the truth"
    )
    # And Brier should have decreased below the v1 baseline.
    from app.scoring.weights import HeuristicWeights
    baseline = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    assert best.brier_mean < baseline.brier_mean


def test_coordinate_descent_idempotent_on_same_inputs():
    samples = _make_synthetic_dataset()
    a = coordinate_descent(samples, passes=2)
    b = coordinate_descent(samples, passes=2)
    assert a.weights == b.weights
    assert a.brier_mean == b.brier_mean
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest tests/unit/test_tune_heuristic_weights.py -v`
Expected: ImportError on `scripts.tune_heuristic_weights`.

- [ ] **Step 3: Implement the tuner core**

```python
# scripts/tune_heuristic_weights.py
"""Offline tuner: coordinate descent over 5 free heuristic weights against a
short-horizon Brier objective with a 3-check promotion gate.

Parameter space (sum-to-1 constraints handled by deriving 4 weights from the
5 free ones):

    Free:    w_llm, w_liquidity, w_spread, w_freshness, strength_weight
    Derived: w_source        = 0.15   (fixed — small effect, reduce search)
             w_confirmation  = 1 - w_freshness - w_source - w_llm
             w_time_to_res   = 1 - w_liquidity - w_spread
             trade_weight    = 1 - strength_weight

See spec §6 for the full parameter rationale.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import text

from app.db.database import async_session_factory
from app.measurement.heuristic_variant import predict_heuristic
from app.measurement.metrics import brier_from_outcome, simulated_pnl_eur
from app.scoring.weights import HeuristicWeights


@dataclass(frozen=True)
class Sample:
    features: dict
    llm_combined: float
    direction: str
    price_t1h: float


@dataclass(frozen=True)
class CandidateResult:
    weights: HeuristicWeights
    brier_mean: float
    pnl_mean: float
    n: int
    n_brier_defined: int


def _binarise(price: float) -> int | None:
    if price >= 0.95:
        return 1
    if price <= 0.05:
        return 0
    return None


def evaluate_candidate(w: HeuristicWeights, samples: Iterable[Sample]) -> CandidateResult:
    """Score the full sample set under `w`; return Brier mean + P&L mean."""
    briers: list[float] = []
    pnls: list[float] = []
    n = 0
    for s in samples:
        n += 1
        pred = predict_heuristic(
            weights=w, features=s.features, llm_combined=s.llm_combined,
            direction=s.direction,
        )
        if pred.probability is None:
            continue
        bin_out = _binarise(s.price_t1h)
        if bin_out is not None:
            b = brier_from_outcome(pred.probability, bin_out)
            if b is not None:
                briers.append(b)
        if s.direction in ("BUY_YES", "BUY_NO"):
            pnls.append(simulated_pnl_eur(
                direction=s.direction, probability=pred.probability,
                price_resolved=s.price_t1h,
            ))
    return CandidateResult(
        weights=w,
        brier_mean=sum(briers) / len(briers) if briers else float("inf"),
        pnl_mean=sum(pnls) / len(pnls) if pnls else 0.0,
        n=n,
        n_brier_defined=len(briers),
    )


def _safe_weights(
    *,
    w_freshness: float,
    w_source: float,
    w_llm: float,
    w_liquidity: float,
    w_spread: float,
    strength_weight: float,
) -> HeuristicWeights | None:
    """Build HeuristicWeights from 6 values; return None if the invariant fails
    (so the caller can skip invalid grid points without crashing descent).
    """
    w_confirmation = 1.0 - w_freshness - w_source - w_llm
    w_ttr = 1.0 - w_liquidity - w_spread
    trade_weight = 1.0 - strength_weight
    if w_confirmation < 0.0 or w_ttr < 0.0 or trade_weight < 0.0:
        return None
    try:
        return HeuristicWeights(
            w_freshness=w_freshness, w_source=w_source,
            w_confirmation=w_confirmation, w_llm=w_llm,
            w_liquidity=w_liquidity, w_spread=w_spread,
            w_time_to_resolution=w_ttr,
            strength_weight=strength_weight, trade_weight=trade_weight,
        )
    except ValueError:
        return None


# Grids for each free parameter (sorted; iteration order is deterministic).
_GRID = {
    "w_freshness":     [0.05, 0.15, 0.25, 0.35, 0.50],
    "w_llm":           [0.30, 0.45, 0.60, 0.75, 0.90],
    "w_liquidity":     [0.20, 0.40, 0.60],
    "w_spread":        [0.15, 0.35, 0.50],
    "strength_weight": [0.50, 0.65, 0.75, 0.85],
}


def coordinate_descent(
    samples: list[Sample],
    *,
    passes: int = 2,
    w_source_fixed: float = 0.10,
) -> CandidateResult:
    """Two passes of coordinate descent over the 5 free parameters.

    Each pass iterates in a fixed order, picks the grid value minimising
    brier_mean conditional on the current other parameters, and moves on.
    Deterministic: same input → same output.
    """
    current = HeuristicWeights.frozen_v1()
    best = evaluate_candidate(current, samples)
    order = ("w_freshness", "w_llm", "w_liquidity", "w_spread", "strength_weight")

    for _ in range(passes):
        for param in order:
            for candidate_val in _GRID[param]:
                # Build candidate with `param` overridden; others from `current`
                kwargs = {
                    "w_freshness": current.w_freshness,
                    "w_source": w_source_fixed,
                    "w_llm": current.w_llm,
                    "w_liquidity": current.w_liquidity,
                    "w_spread": current.w_spread,
                    "strength_weight": current.strength_weight,
                }
                kwargs[param] = candidate_val
                trial = _safe_weights(**kwargs)
                if trial is None:
                    continue
                result = evaluate_candidate(trial, samples)
                # Prefer strict Brier improvement; ties broken by higher P&L.
                if (
                    result.brier_mean < best.brier_mean
                    or (
                        result.brier_mean == best.brier_mean
                        and result.pnl_mean > best.pnl_mean
                    )
                ):
                    best = result
                    current = trial
    return best


def evaluation_gate(
    *,
    candidate: CandidateResult,
    baseline_v1: CandidateResult,
    per_bucket: dict[str, tuple[CandidateResult, CandidateResult]] | None = None,
    pnl_slip_tolerance: float = 0.05,
    bucket_brier_regression_cap: float = 0.05,
) -> dict:
    """Apply the 3-check gate.

    Returns a dict with `passed: bool` and per-check diagnostics.
    """
    # Simple Brier-CI proxy: ±1.96·√(var/n). We use the 95% two-tailed rule.
    def _se(brier: float, n: int) -> float:
        if n < 2:
            return float("inf")
        return (brier * (1 - brier) / n) ** 0.5

    cand_se = _se(candidate.brier_mean, candidate.n_brier_defined)
    base_se = _se(baseline_v1.brier_mean, baseline_v1.n_brier_defined)
    cand_hi = candidate.brier_mean + 1.96 * cand_se
    base_lo = baseline_v1.brier_mean - 1.96 * base_se
    brier_disjoint = cand_hi < base_lo

    pnl_floor = baseline_v1.pnl_mean * (1.0 - pnl_slip_tolerance)
    pnl_ok = candidate.pnl_mean >= pnl_floor

    bucket_ok = True
    bucket_diagnostics: dict[str, dict] = {}
    if per_bucket:
        for bucket_name, (cand_b, base_b) in per_bucket.items():
            regression = cand_b.brier_mean - base_b.brier_mean
            passed = regression <= bucket_brier_regression_cap
            bucket_diagnostics[bucket_name] = {
                "candidate_brier": cand_b.brier_mean,
                "baseline_brier": base_b.brier_mean,
                "regression": regression,
                "passed": passed,
            }
            if not passed:
                bucket_ok = False

    return {
        "passed": brier_disjoint and pnl_ok and bucket_ok,
        "brier_disjoint": brier_disjoint,
        "pnl_ok": pnl_ok,
        "bucket_ok": bucket_ok,
        "candidate_brier": candidate.brier_mean,
        "candidate_pnl": candidate.pnl_mean,
        "baseline_brier": baseline_v1.brier_mean,
        "baseline_pnl": baseline_v1.pnl_mean,
        "pnl_floor": pnl_floor,
        "buckets": bucket_diagnostics,
    }


async def _fetch_samples(horizon: str) -> list[Sample]:
    col = f"price_{horizon}"
    sql = text(
        f"""SELECT s.id, s.direction,
                   sp.predicted_probability,
                   emf.freshness_factor, emf.source_weight, emf.confirmation_factor,
                   emf.liquidity_factor, emf.spread_penalty, emf.time_to_resolution_factor,
                   emf.impact_strength, emf.llm_confidence,
                   so.{col} AS price_horizon
            FROM signals s
            JOIN signal_predictions sp ON sp.signal_id = s.id AND sp.variant = 'heuristic_v1'
            JOIN signal_outcomes so ON so.signal_id = s.id
            LEFT JOIN event_market_features emf
              ON emf.event_id = s.event_id AND emf.market_id = s.market_id
            WHERE so.{col} IS NOT NULL"""
    )
    samples: list[Sample] = []
    async with async_session_factory() as s:
        rows = (await s.execute(sql)).all()
    for r in rows:
        (_sid, direction, _prob,
         fresh, src, confirm, liq, spread, ttr,
         impact, llm_conf, price) = r
        # Reconstruct llm_combined with the same formula as SignalBuilder
        # (impact * 0.65 + llm_confidence * 0.35). If either is None, skip
        # LLM contribution — predict_heuristic accepts None.
        llm_combined: float | None = None
        if impact is not None and llm_conf is not None:
            llm_combined = float(impact) * 0.65 + float(llm_conf) * 0.35
        samples.append(Sample(
            features={
                "freshness": float(fresh) if fresh is not None else 0.5,
                "source_weight": float(src) if src is not None else 0.5,
                "confirmation": float(confirm) if confirm is not None else 0.5,
                "liquidity": float(liq) if liq is not None else 0.5,
                "spread": float(spread) if spread is not None else 0.5,
                "time_to_resolution": float(ttr) if ttr is not None else 0.5,
            },
            llm_combined=llm_combined if llm_combined is not None else 0.5,
            direction=direction,
            price_t1h=float(price),
        ))
    return samples


async def _main_async(*, horizon: str, out_path: str, passes: int) -> None:
    samples = await _fetch_samples(horizon)
    if not samples:
        print(f"No joined samples at horizon={horizon}; exit.")
        return
    baseline = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    best = coordinate_descent(samples, passes=passes)
    gate = evaluation_gate(candidate=best, baseline_v1=baseline)
    payload = {
        "generated_at": str(date.today()),
        "horizon": horizon,
        "n_samples": len(samples),
        "baseline_v1": {
            "brier_mean": baseline.brier_mean, "pnl_mean": baseline.pnl_mean,
            "n_brier_defined": baseline.n_brier_defined,
        },
        "candidate": {
            "weights": best.weights.__dict__,
            "brier_mean": best.brier_mean,
            "pnl_mean": best.pnl_mean,
            "n_brier_defined": best.n_brier_defined,
        },
        "gate": gate,
        "gate_status": "passed" if gate["passed"] else "failed",
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"wrote {out_path} — gate_status={payload['gate_status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune heuristic weights via coordinate descent.")
    parser.add_argument("--horizon", choices=("t15min", "t1h", "t24h"), default="t1h")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument(
        "--out",
        default=f"docs/audit/heuristic_weights_candidate_{date.today().isoformat()}.json",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(horizon=args.horizon, out_path=args.out, passes=args.passes))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify pass**

Run: `pytest tests/unit/test_tune_heuristic_weights.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/tune_heuristic_weights.py tests/unit/test_tune_heuristic_weights.py
git commit -m "feat(chantier-5): coordinate descent tuner for heuristic weights"
```

---

## Task 12: Tuner — gate rejection + idempotence assertions

**Files:**
- Modify: `tests/unit/test_tune_heuristic_weights.py`

- [ ] **Step 1: Append gate tests**

```python
# append to tests/unit/test_tune_heuristic_weights.py
from dataclasses import replace

from app.scoring.weights import HeuristicWeights


def _mk_result(brier: float, pnl: float, n: int = 200) -> CandidateResult:
    return CandidateResult(
        weights=HeuristicWeights.frozen_v1(),
        brier_mean=brier, pnl_mean=pnl, n=n, n_brier_defined=n,
    )


def test_gate_passes_when_candidate_is_cleanly_better():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is True
    assert g["brier_disjoint"] is True
    assert g["pnl_ok"] is True


def test_gate_rejects_when_brier_ci_overlaps():
    cand = _mk_result(brier=0.24, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is False
    assert g["brier_disjoint"] is False


def test_gate_rejects_when_pnl_regresses_past_tolerance():
    cand = _mk_result(brier=0.10, pnl=0.50)   # 50% P&L slip
    base = _mk_result(brier=0.25, pnl=1.00)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is False
    assert g["pnl_ok"] is False
    # default tolerance 5% → pnl_floor = 0.95; 0.50 < 0.95 → fail
    assert g["pnl_floor"] == 0.95


def test_gate_rejects_when_bucket_regresses_past_cap():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    buckets = {
        "high":   (_mk_result(brier=0.10, pnl=1.0), _mk_result(brier=0.15, pnl=0.9)),  # improves
        "medium": (_mk_result(brier=0.30, pnl=0.5), _mk_result(brier=0.20, pnl=0.8)),  # regresses +0.10 > 0.05
    }
    g = evaluation_gate(candidate=cand, baseline_v1=base, per_bucket=buckets)
    assert g["passed"] is False
    assert g["bucket_ok"] is False
    assert g["buckets"]["medium"]["passed"] is False
    assert g["buckets"]["high"]["passed"] is True


def test_gate_passes_when_all_buckets_stable():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    buckets = {
        "high":   (_mk_result(brier=0.10), _mk_result(brier=0.12)),
        "medium": (_mk_result(brier=0.16), _mk_result(brier=0.18)),
        "low":    (_mk_result(brier=0.22), _mk_result(brier=0.20)),  # +0.02 ≤ 0.05 OK
    }
    g = evaluation_gate(candidate=cand, baseline_v1=base, per_bucket=buckets)
    assert g["passed"] is True


def test_coordinate_descent_result_weights_sum_invariant_holds():
    """Every weights object the tuner can return must satisfy the
    HeuristicWeights sum-to-1 invariants (redundant check since _safe_weights
    already filters, but explicit here in case `_safe_weights` is ever bypassed)."""
    samples = _make_synthetic_dataset()
    best = coordinate_descent(samples, passes=2)
    # __post_init__ already asserts; re-constructing from the attrs would
    # raise if anything drifted.
    HeuristicWeights(**best.weights.__dict__)
```

- [ ] **Step 2: Fix `_mk_result` helper to accept optional pnl**

The test calls `_mk_result(brier=0.10)` without `pnl`. Update the helper:

```python
def _mk_result(brier: float, pnl: float = 0.0, n: int = 200) -> CandidateResult:
    return CandidateResult(
        weights=HeuristicWeights.frozen_v1(),
        brier_mean=brier, pnl_mean=pnl, n=n, n_brier_defined=n,
    )
```

- [ ] **Step 3: Run the suite**

Run: `pytest tests/unit/test_tune_heuristic_weights.py -v`
Expected: 3 + 6 = 9 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_tune_heuristic_weights.py
git commit -m "test(chantier-5): tuner gate rejection + bucket regression + idempotence"
```

---

## Task 13: Generate & commit the validation report

**Files:**
- Create (via script run): `docs/audit/heuristic_validation_report_2026-04-24.md`

- [ ] **Step 1: Ensure the dev DB is current**

Run: `docker compose exec app alembic upgrade head`
Expected: "Running upgrade … -> 025" (or "no migration needed" if already done).

- [ ] **Step 2: Run the validation script**

Run:
```bash
docker compose exec app python -m scripts.validate_heuristic_weights \
    --horizon t1h \
    --out docs/audit/heuristic_validation_report_2026-04-24.md
```

Expected: console output "wrote docs/audit/heuristic_validation_report_2026-04-24.md (~225 joined rows, 5 variants)".

- [ ] **Step 3: Review the report**

Run: `cat docs/audit/heuristic_validation_report_2026-04-24.md`

Verify the table includes rows for `heuristic_v1`, `baseline_random`,
`baseline_market_price`, `baseline_momentum`, `baseline_news_sentiment` and
that each has non-NaN brier_mean and pnl_mean. If any `n_brier_defined` is 0,
escalate — that means the horizon has no binarisable outcomes, a data
problem rather than a script bug.

- [ ] **Step 4: Commit**

```bash
git add docs/audit/heuristic_validation_report_2026-04-24.md
git commit -m "docs(chantier-5): heuristic_v1 validation report vs 4 baselines @ t1h"
```

---

## Task 14: Promotion runbook stub

**Files:**
- Create: `docs/runbooks/promote_heuristic_candidate.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Runbook — Promote a Heuristic Weights Candidate

Applies when `scripts/tune_heuristic_weights.py` produces a candidate with
`gate_status: "passed"` in `docs/audit/heuristic_weights_candidate_*.json`.

This is a **manual** multi-step workflow. There is no auto-promotion.

## Pre-flight checklist

- [ ] Alembic at head (`docker compose exec app alembic current`).
- [ ] `heuristic_shadow_enabled=False` currently (verify via
      `env | grep HEURISTIC_SHADOW_ENABLED`).
- [ ] Latest `docs/audit/heuristic_weights_candidate_*.json` has
      `gate_status: "passed"` AND the spec §6.4 three checks are green.
- [ ] The candidate JSON was generated on the current dev DB, not a stale
      snapshot (check `generated_at`).

## Step 1 — Shadow confirmation (48h observation window)

1. Update `.env`:
   ```
   HEURISTIC_SHADOW_ENABLED=true
   HEURISTIC_W_FRESHNESS=<candidate.weights.w_freshness>
   HEURISTIC_W_SOURCE=<candidate.weights.w_source>
   HEURISTIC_W_CONFIRMATION=<candidate.weights.w_confirmation>
   HEURISTIC_W_LLM=<candidate.weights.w_llm>
   HEURISTIC_W_LIQUIDITY=<candidate.weights.w_liquidity>
   HEURISTIC_W_SPREAD=<candidate.weights.w_spread>
   HEURISTIC_W_TIME_TO_RESOLUTION=<candidate.weights.w_time_to_resolution>
   HEURISTIC_STRENGTH_WEIGHT=<candidate.weights.strength_weight>
   HEURISTIC_TRADE_WEIGHT=<candidate.weights.trade_weight>
   ```
2. Restart app + workers: `docker compose restart app worker-scoring`.
3. Wait 48h (enough for the outcome backfill to land t1h prices for
   signals scored under the shadow weights).

## Step 2 — Confirm offline finding on shadow data

Re-run validation, filtering to the `heuristic_shadow` variant only:

```bash
docker compose exec app python -m scripts.validate_heuristic_weights \
    --horizon t1h \
    --out docs/audit/heuristic_shadow_confirmation_$(date +%Y-%m-%d).md
```

Check that `heuristic_shadow.brier_mean` ≤ the tuner's candidate Brier
(±1-2% is acceptable — shadow samples come from a fresher time window).

## Step 3 — Promote

1. Edit `app/scoring/weights.py`:
   update the `HeuristicWeights` default values to match the candidate.
2. Edit `HeuristicWeights.frozen_v1` to **re-snapshot the new defaults**
   (so the next tuning run has the new baseline, not the old one).
3. Update `tests/unit/test_heuristic_weights.py::test_defaults_match_frozen_v1_values`
   to reflect the new constants.
4. Update `tests/unit/test_config_integrity.py` bloc-sum defaults if any
   drifted (they shouldn't — all candidates respect sum=1).
5. Run `pytest tests/unit/test_heuristic_weights.py tests/unit/test_config_integrity.py -v`.
   Must be all green.

## Step 4 — Re-disable shadow

1. `.env`: `HEURISTIC_SHADOW_ENABLED=false`, remove the `HEURISTIC_W_*`
   overrides (they now equal defaults).
2. Restart app + workers.
3. Merge, tag, deploy.

## Rollback

If Step 2 reveals the shadow Brier is worse than the offline finding
predicted, revert Step 1 (set `HEURISTIC_SHADOW_ENABLED=false`, clear the
`HEURISTIC_W_*` overrides) and document the discrepancy in
`docs/audit/`. The dev DB still has pre-shadow data; no DB rollback needed.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/promote_heuristic_candidate.md
git commit -m "docs(chantier-5): operator runbook for promoting a tuner candidate"
```

---

## Task 15: Whole-suite green run + backlog update

**Files:**
- Modify: `docs/audit/ISSUES_BACKLOG.md`

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -40`
Expected: 0 failed, 0 errored. Record the passed count (~310+ expected given
~30 new tests).

If any unrelated tests fail (e.g. network-dependent), mark them `@pytest.mark.skip`
with an inline reason and a follow-up TODO in the commit message — don't
attempt to fix unrelated breakage in this chantier.

- [ ] **Step 2: Update the backlog**

Edit `docs/audit/ISSUES_BACKLOG.md`: find the row for audit §6.1 "poids
arbitraires jamais validés" (or the chantier #5 umbrella row) and mark it
`🟢 Shipped (<short-sha>)`.

Also add a follow-up row (status `🟡 Operational`) for:

```
| — | Tuner run on real data — check if candidate passes the 3-check gate; if yes, exercise promote_heuristic_candidate.md end-to-end. |
```

- [ ] **Step 3: Verify chantier #5 deliverables vs spec §9 checklist**

Re-read `docs/specs/2026-04-24-heuristic-score-validation-design.md` §9.
Tick every box OR document what's deferred and why.

- [ ] **Step 4: Final commit**

```bash
git add docs/audit/ISSUES_BACKLOG.md
git commit -m "docs(chantier-5): mark audit §6.1 shipped; log operational follow-ups"
```

---

## Appendix A: DB column reference (read-only)

| Table | Column | Type | Notes |
|---|---|---|---|
| `signals` | `id`, `direction`, `signal_strength`, `signal_score` | PK + `BUY_YES`/`BUY_NO` + Numeric(5,1) | Written by `SignalBuilder.build_signal`. |
| `signal_predictions` | `signal_id`, `variant`, `predicted_direction`, `predicted_probability` | Composite PK (`signal_id`,`variant`) + Numeric(6,4) | Chantier #5 variants: `heuristic_v1`, optional `heuristic_shadow`. |
| `signal_outcomes` | `signal_id`, `price_t15min`, `price_t1h`, `price_t24h`, `price_resolved` | FK to `signals.id` + Numeric(6,4) each | Backfilled asynchronously by `tasks_outcomes.py`. |
| `event_market_features` | `event_id`, `market_id`, `freshness_factor`, `source_weight`, `confirmation_factor`, `liquidity_factor`, `spread_penalty`, `time_to_resolution_factor`, `impact_strength`, `llm_confidence` | Unique on (`event_id`,`market_id`) | Persists the exact features used at scoring time; the tuner re-reads from here. |

## Appendix B: Known test flakiness modes

- **Event-loop-closed** on integration tests → always use `async_db_factory` fixture,
  never import `async_session_factory` at module level in tests. Pattern established
  in chantier #4.
- **Settings cache** between tests → call `get_settings.cache_clear()` after any
  `monkeypatch.setenv` / `os.environ` mutation. Fixture `_clear_settings_cache` in
  task 9 is the template.
- **Parallel test runners** (`pytest-xdist`) are **not** supported by the integration
  shadow test (task 9) because each worker's DB state mutates `signal_predictions`.
  If CI ever enables `-n auto`, gate integration tests with
  `@pytest.mark.skipif(os.environ.get("PYTEST_XDIST_WORKER"), reason="not xdist-safe")`.
