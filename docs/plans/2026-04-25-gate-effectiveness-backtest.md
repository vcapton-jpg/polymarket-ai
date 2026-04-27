# Gate Effectiveness Backtest — Implementation Plan

> **STATUS — 2026-04-25 (Task 1 ran, plan amended).** Data-availability check revealed `event_market_features` is empty in prod (0 rows, despite 5 425 `event_market_analysis` rows and 5 106 rejected pairs). Adopted **option C — split into two parallel PRs**: PR #1 instruments `event_market_features` going forward (so the *next* backtest is exhaustive across all 13 gates); PR #2 ships the partial backtest covering the 6 currently-replayable gates using `event_market_analysis` + `event_market_candidates` + `signal_outcomes` (n=441 rejected with binary outcome + n=23 kept with outcome). Both PRs land in parallel; the second is read-only and unblocked.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/audit/gate_effectiveness_2026-04-25.md` — a per-gate False-Rejection-Rate report with threshold-change recommendations for the 13 hard rejection gates, before any weight tuning. Companion spec: [`docs/specs/2026-04-25-gate-effectiveness-design.md`](../specs/2026-04-25-gate-effectiveness-design.md).

**Architecture:** Offline analysis only. Reads `event_market_analysis` + `event_market_features` + `signal_outcomes` + `markets`. Writes one Markdown report and one JSON sidecar. No prod-path code touched. TDD on the gate-replay logic so a future change to the gates breaks the test rather than silently shifting the report.

**Tech Stack:** Python / SQLAlchemy async / pytest-asyncio. New module under `scripts/`; new test file under `tests/unit/`.

---

## Empirical findings — Task 1 ran 2026-04-25

Live counts on the local-prod DB (worktree `quirky-lamport-98feca`, container `foresight-db`, db `signal`):

```
event_market_features  rows:        0   ← bug; never populated by the prod path
event_market_analysis  rows:    5 425
event_market_candidates rows:  16 543
events:                          3 559
markets:                       139 947
signals:                           322   (passed all gates)
signal_outcomes:                   313
signal_outcomes.outcome_label:      23   (binary-resolved)
markets.closed = true:          17 819
markets at binary band (≤0.05/≥0.95): 39 111

analyzed (event, market) pairs:        5 425
  ↳ passed (became signal):              322
  ↳ rejected:                          5 106

rejected pairs that have a binary-resolved outcome
(closed=true AND last_trade_price ≤0.05 or ≥0.95):  441
```

### Implications
- `event_market_features.outcome_label` is unusable today (0 rows). The historical features needed to replay the 5 backend gates (freshness, source_weight, confirmation, liquidity, spread, time_to_resolution) **were never persisted at-time** for either passed or rejected pairs. They live on `Signal._features` for kept signals only and are ephemeral.
- The 8 backend-side gates that depend on at-time market state (current price, current spread, current volume) cannot be backtested from snapshot data — current `markets.*` columns drift after rejection. They become backtestable only after PR #1 instruments persistence going forward.
- The 6 LLM-side / cosine gates ARE replayable today from `event_market_analysis` + `event_market_candidates`. Total usable rejected sample with a binary outcome on the resolved-market side: **441**, vs n=23 on the kept side — a 19× larger backtest dataset than the heuristic-validation report had.

### Decision — option C, two parallel PRs

- **PR #1 — instrument event_market_features (going forward + at-resolution backfill).** Touches `app/workers/tasks_scoring.py` (write features at-time) + `app/workers/tasks_outcomes.py` (back-populate `outcome_label` when markets resolve) + extracts a shared feature-build helper. Small, focused, prod-path. Does NOT change any gate.
- **PR #2 — partial gate backtest report.** Read-only. Covers the 6 currently-replayable gates only (cosine, direction, ambiguity, specificity, impact_strength, no_reasoning) using `event_market_analysis` + `event_market_candidates` + `signal_outcomes` + `markets`. Output: `docs/audit/gate_effectiveness_2026-04-25.md`. Explicitly flags the other 7 gates as "deferred until PR #1 has accumulated 2-4 weeks of data".

Both land in parallel; PR #2 doesn't depend on PR #1's data. A follow-up "PR #3 — full gate backtest" runs in ~3 weeks once PR #1 has captured features for the steady-state pipeline.

---

## File Structure

### PR #1 — Instrumentation (prod-path, ~150 LOC + tests)

**Created:**
- `app/scoring/feature_dict.py` — shared `build_feature_dict(event_data, market_data, ref_dt) -> dict[str, float]` extracted from `signal_builder.py:178-196`. Single source of truth for the 6 backend features.
- `tests/unit/test_feature_dict.py` — TDD coverage: golden output for known inputs; matches what `signal_builder.py` was producing inline (regression test pinned to the prior implementation).
- `tests/integration/test_event_market_features_persistence.py` — for both passed and rejected (event, market) pairs, verifies `EventMarketFeatures` is written exactly once with the expected shape.
- `tests/integration/test_outcome_label_backpopulation.py` — when `tasks_outcomes.check_resolved_markets` runs, `event_market_features.outcome_label` is populated for both passed and rejected pairs whose market just closed in the binary band.

**Modified:**
- `app/signal/signal_builder.py` — replace the inline `features = {...}` (lines 178-196) with a call to `build_feature_dict`. No behavior change; pure refactor. Pinned by `test_feature_dict.py`.
- `app/workers/tasks_scoring.py` — in the scoring loop after `event_data` + `market_data` are built, write `EventMarketFeatures` upsert (per `UniqueConstraint(event_id, market_id)`) **before** `_market_quality_reject` so features are captured for ALL analyzed pairs, not only those that survive the early gate.
- `app/workers/tasks_outcomes.py` — extend `check_resolved_markets` to also write `event_market_features.outcome_label` (alongside `signal_outcomes.outcome_label`) for every `(event_id, market_id)` whose market resolved in the binary band.

### PR #2 — Backtest report (read-only)

**Created:**
- `scripts/backtest_gates.py` — main entry point (CLI: `--window 90d --out docs/audit/gate_effectiveness_2026-04-25.md`).
- `app/scoring/gate_replay.py` — pure functions that re-apply each replayable gate to a stored feature dict; mirrors the in-prod gates verbatim. **NOT imported by any prod code path.**
- `tests/unit/test_gate_replay.py` — 6 gates × 3 cases (pass/fail/edge) = 18 tests minimum.
- `docs/audit/gate_effectiveness_2026-04-25.md` — the report.
- `docs/audit/gate_effectiveness_2026-04-25.json` — machine-readable sidecar.

**Modified:**
- *None.* PR #2 is read-only.

---

## PR #1 — Instrumentation tasks

## Task 1: ✅ DONE — Data availability diagnostic

Already executed; results above in **Empirical findings**. No code committed for this task (live SQL via `docker exec`).

## Task 2: Extract `build_feature_dict` into a shared helper

**Files:**
- Create: `app/scoring/feature_dict.py`
- Create: `tests/unit/test_feature_dict.py`
- Modify: `app/signal/signal_builder.py`

- [ ] **Step 1 (TDD):** write `tests/unit/test_feature_dict.py` with one golden-output test per feature key. Inputs: a fixture `event_data` + `market_data` + `ref_dt` triple. Assertions: each of the 6 expected keys with the expected value (computed by hand against the current `feature_builder.py` formulas). Test fails because module doesn't exist yet.
- [ ] **Step 2:** create `app/scoring/feature_dict.py` exporting `build_feature_dict(event_data, market_data, ref_dt, *, feature_builder=None) -> dict[str, float]`. Implementation: copy of the 6 lines currently in `signal_builder.py:178-196`. Default `feature_builder=create_feature_builder()`.
- [ ] **Step 3:** modify `app/signal/signal_builder.py:178-196` to call `build_feature_dict(event_data, market_data, ref_dt, feature_builder=self.feature_builder)`. Run existing signal-builder tests — must stay green (this is a refactor).
- [ ] **Step 4:** run `make lint && make test` — all green.

**VERIFY:**
- [ ] `signal_builder.py` produces identical features before vs after (covered by existing tests + new `test_feature_dict.py`).
- [ ] No new public surface beyond `build_feature_dict`.

## Task 3: Persist `EventMarketFeatures` for every analyzed pair

**Files:**
- Modify: `app/workers/tasks_scoring.py`
- Create: `tests/integration/test_event_market_features_persistence.py`

- [ ] **Step 1 (TDD):** write the integration test. Sets up an event + 2 markets. Mocks the LLM analysis. Runs the scoring loop. Asserts:
  - For the market that becomes a signal: an `EventMarketFeatures` row exists with the 6 backend features + 3 LLM features (`impact_strength`, `llm_confidence`, `ambiguity_score`).
  - For the market that gets rejected (e.g., low cosine): an `EventMarketFeatures` row ALSO exists with the same shape.
  - Re-running the scoring loop on the same event is idempotent (UPSERT, not duplicate rows). Verified by `UniqueConstraint(event_id, market_id)`.
- [ ] **Step 2:** in `tasks_scoring.py`, immediately after the `event_data` and `market_data` dicts are built (around line 644), call `build_feature_dict(...)` and write/upsert an `EventMarketFeatures` row. The upsert uses `INSERT ... ON CONFLICT (event_id, market_id) DO UPDATE` (PostgreSQL upsert; we're already PG-only).
- [ ] **Step 3:** ensure the write happens BEFORE `_market_quality_reject` (line 577 today) — this means restructuring the loop slightly so feature persistence is the first step inside `for mid in scored_mids`.
- [ ] **Step 4:** run integration tests.

**VERIFY:**
- [ ] After running the prod scoring path on a synthetic event with 2 markets, `event_market_features` has 2 rows (not 1).
- [ ] Re-running yields still 2 rows (UPSERT, not duplicates).
- [ ] No regression in signal creation count for the existing test suite.

## Task 4: Back-populate `outcome_label` at resolution time

**Files:**
- Modify: `app/workers/tasks_outcomes.py`
- Create: `tests/integration/test_outcome_label_backpopulation.py`

- [ ] **Step 1 (TDD):** integration test setup: create one `EventMarketFeatures` row (NULL outcome_label), one `Market` with `closed=true` and `last_trade_price=0.97`. Run `check_resolved_markets`. Assert `event_market_features.outcome_label == 1`. Repeat with `last_trade_price=0.03` → `outcome_label == 0`, with `last_trade_price=0.5` → stays NULL (ambiguous band).
- [ ] **Step 2:** in `tasks_outcomes.check_resolved_markets`, when a market resolves in the binary band, also UPDATE all `event_market_features` rows with that `market_id` to set `outcome_label`.
- [ ] **Step 3:** the outcome_label rule (`>=0.95 → 1`, `<=0.05 → 0`, else NULL) MUST match the rule already used for `signal_outcomes.outcome_label` ([app/workers/tasks_outcomes.py:258-262](../../app/workers/tasks_outcomes.py)). Eyeball-equal in the PR description.

**VERIFY:**
- [ ] One source of truth for the binary-band rule (extract a small `binary_label(price: float | None) -> int | None` helper if needed; share between signal_outcomes and event_market_features writes).
- [ ] Integration test catches the case where price is NULL — outcome stays NULL.

## Task 5: PR #1 land — instrumentation

- [ ] **Step 1:** PR title: `feat(scoring): persist event_market_features for all analyzed pairs + outcome_label backpop`.
- [ ] **Step 2:** PR body links the spec, summarizes the 0-row finding, and the 4 modified/created files. NO threshold changes.
- [ ] **Step 3:** monitor: 24h after merge, run the diagnostic SQL again. Expect `event_market_features` to be growing at ~`(rate of new analyses)` per hour.

---

## PR #2 — Partial gate backtest tasks

PR #2 is read-only and unblocked by PR #1. It can be developed in parallel.

## Task 6: Implement `app/scoring/gate_replay.py` — 6 replayable gates

**Files:**
- Create: `app/scoring/gate_replay.py`
- Create: `tests/unit/test_gate_replay.py`

- [ ] **Step 1 (TDD):** write the test file first. 6 gates × 3 cases (pass/fail/edge) = 18 tests minimum. Use a small dataclass for the input shape (LLM analysis fields + cosine score).

```python
# Replayable gates only:
#   gate_cosine          (input: cosine_score)
#   gate_direction_clear (input: impact_direction)
#   gate_ambiguity       (input: ambiguity_score)
#   gate_specificity     (input: specificity_score)
#   gate_impact_strength (input: impact_strength)
#   gate_has_reasoning   (input: reasoning string)
```

- [ ] **Step 2:** implement each gate as a pure function mirroring [signal_builder.py:122-167](../../app/signal/signal_builder.py) verbatim. Returns `GateResult(passed: bool, reason: str | None)`.
- [ ] **Step 3:** add `replay_replayable_gates(input: GateInput) -> dict[str, GateResult]` aggregator.
- [ ] **Step 4:** run tests; green.

**VERIFY:**
- [ ] Each gate function has a `# mirrors signal_builder.py:N-N` comment pointing at the prod source.
- [ ] No `app.scoring.gate_replay` import in `app/signal/` or `app/workers/`.

## Task 7: Implement `scripts/backtest_gates.py` — the analysis runner

**Files:**
- Create: `scripts/backtest_gates.py`

- [ ] **Step 1:** SQL pull. Single async query joining:
  - `event_market_analysis` (LLM gate inputs)
  - `event_market_candidates` (cosine_score)
  - `signal_outcomes` (kept-side outcome) ∪ `markets.closed=true AND price ∈ binary band` (rejected-side outcome)
  Window filter: `event_market_analysis.created_at >= NOW() - 90 days`.
- [ ] **Step 2:** for each row, call `replay_replayable_gates`, align with the recorded outcome.
- [ ] **Step 3:** per gate, compute `n_rejected`, `n_with_outcome`, `n_correct_if_kept`, `FRR`, plus bootstrap 95 % CI on FRR (1 000 resamples, seed=42).
- [ ] **Step 4:** counterfactual (numeric gates only — cosine, ambiguity, specificity): enumerate ± {0.05, 0.10} threshold deltas; report aggregate Brier mean + CI95 on the would-now-pass set.
- [ ] **Step 5:** render `docs/audit/gate_effectiveness_2026-04-25.md`. Sections: Executive summary, per-gate table, counterfactual table, recommended threshold changes, data appendix (window dates, n_total, deferred-gates list).
- [ ] **Step 6:** write `docs/audit/gate_effectiveness_2026-04-25.json` sidecar.

**VERIFY:**
- [ ] `uv run python scripts/backtest_gates.py --window 90d` produces both files.
- [ ] Markdown numbers match JSON numbers (Markdown renders FROM the JSON, not re-computed).
- [ ] Each gate where `n_with_outcome < 30` is flagged "low-N — interpret with caution".

## Task 8: Validate the report with sanity checks

- [ ] **Step 1:** baseline_random sanity — re-run the rejected-with-outcome bucket through coin-flip-with-seed; should produce hit-rate ≈ 0.50. If not, the join has a leak; stop and debug.
- [ ] **Step 2:** spot-check 5 rows by hand against the SQL — confirm the FRR script counts match.
- [ ] **Step 3:** any "lower threshold" recommendation MUST have a CI95 disjoint from the current threshold's CI95 — same gate as `tune_heuristic_weights.evaluation_gate`.

**VERIFY:**
- [ ] Report includes the sentence "no statistically significant changes recommended" if no gate passes the CI-disjoint test (this is a valid result).

## Task 9: PR #2 land — backtest report

- [ ] **Step 1:** PR title: `audit: gate effectiveness backtest (2026-04-25, 6 gates)`.
- [ ] **Step 2:** PR body: link the spec + PR #1, the per-gate FRR table inline, and an explicit "Why only 6 of 13 gates" paragraph pointing at PR #1's instrumentation.
- [ ] **Step 3:** NO threshold-change diff in this PR. That's a future PR after the report is reviewed.

---

## Out-of-scope, deferred to follow-up chantiers

- Applying any threshold change to `app/signal/signal_builder.py` or `app/core/config.py` — separate PR after PR #2 is reviewed.
- Backtesting the 7 gates that depend on at-time market state (spread, price-band, market-quality, catalyst-vs-market, no-LLM-analysis, no-excerpts, unclear-recommendation) — runs in 3 weeks once PR #1 has accumulated data.
- Re-tuning heuristic weights — chantier "heuristic-tuning-2" runs *after* both PRs land + the threshold-change PR.
- Probability calibration (isotonic regression on `signal_predictions`) — orthogonal, parallel chantier.
- Per-bucket / per-horizon admin metrics endpoint — observability debt, separate chantier.

