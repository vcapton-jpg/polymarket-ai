# Gate Effectiveness Backtest — Design Spec

> **Date:** 2026-04-25
> **Status:** Draft (pre-implementation)
> **Companion plan:** `docs/plans/2026-04-25-gate-effectiveness-backtest.md`
> **Triggered by:** Heuristic v1 Brier=0.31 vs market-price baseline 0.03 ([heuristic_validation_report_2026-04-24.md](../audit/heuristic_validation_report_2026-04-24.md)). Before tuning weights, we must check whether the ~13 hard rejection gates are over-filtering — otherwise tuning a scorer that never sees the right inputs is wasted effort.

---

## 1. Problem

The signal pipeline applies ~13 hard rejection gates between LLM analysis and signal persistence:

**`SignalBuilder.build_signal`** ([app/signal/signal_builder.py:122-167](../../app/signal/signal_builder.py)) — 8 gates:
1. `cosine_score < signal_min_cosine_score` (default 0.52)
2. `spread > hard_exclusion_spread`
3. `direction in {NEUTRAL, UNCLEAR, ""}`
4. `ambiguity_score > hard_exclusion_ambiguity`
5. `specificity_score < hard_exclusion_min_specificity`
6. `impact_strength is None or == 0`
7. `last_trade_price` outside `[signal_tradeable_yes_min, signal_tradeable_yes_max]`
8. No `llm_analysis`

**`SignalBuilder._persist_signal`** ([signal_builder.py:300-344](../../app/signal/signal_builder.py)) — 3 gates:
9. `no_reasoning`
10. `no_excerpts`
11. `unclear_direction recommendation`

**`tasks_scoring`** ([app/workers/tasks_scoring.py:129-201](../../app/workers/tasks_scoring.py)) — 2 gates:
12. `_market_quality_reject` (volume / liquidity / age)
13. `_catalyst_disagrees_with_market`

None of these thresholds has been validated against resolved-outcome data. They were set by intuition during audit follow-ups. A gate that rejects 80 %+ of "would-have-been-correct" signals is a bigger problem than a sub-optimal scoring weight.

## 2. Goal

For each gate, produce a single number:

> **False-rejection rate (FRR)** = `P(market resolves in the predicted direction | gate fired)`

Plus, for every gate, the **delta on aggregate Brier / hit-rate / simulated PnL** if its threshold were moved by ± 1 standard step (e.g., ambiguity 0.6 → 0.7) on the held-out historical set.

The output is a single `docs/audit/gate_effectiveness_2026-04-25.md` report with a per-gate table and a recommended threshold change list.

**Out of scope** (future chantiers):
- Modifying any gate threshold in production (this report drives the *next* chantier).
- Replacing the gate with a learned classifier.
- Tuning the scorer weights (chantier #2 in the post-audit roadmap).

## 3. Data sources (all already in DB)

| What we need | Where it lives | Coverage |
|---|---|---|
| LLM gate inputs (impact_direction, impact_strength, ambiguity, specificity, llm_confidence) | `event_market_analysis` | One row per analyzed (event, market) |
| Backend gate inputs (freshness, source_weight, confirmation, liquidity, spread, time_to_resolution) | `event_market_features` | Same — written alongside analysis |
| Cosine score | `event_market_candidates.cosine_score` | One row per retrieved candidate |
| Market microstructure at signal time | `markets.last_trade_price`, `markets.spread`, `markets.liquidity` | Snapshot, drifts |
| Market resolution | `signal_outcomes.price_resolved` + `signal_outcomes.outcome_label` (kept signals) | Only for signals that PASSED the gates |
| Market resolution for rejected pairs | `markets.closed=true` + `markets.last_trade_price` (resolves to ~1.0 / ~0.0) OR `event_market_features.outcome_label` | Schema supports it; coverage TBD |

**Critical unknown — Task 1 of the plan:** measure how many `event_market_features` rows for *rejected* pairs have `outcome_label` filled. If coverage is low, we add a backfill task before continuing.

## 4. Approach — gate replay on historical data

```
For each (event_id, market_id) that produced an event_market_analysis row in the
last 90 days:

  1. Reconstruct the gate decision by re-running each gate against the stored
     features/analysis. Get a tuple {gate_id: passed | failed}.
  2. Look up the market resolution:
       - If signal exists → signal_outcomes.outcome_label
       - Else (rejected pair) → event_market_features.outcome_label
            (or markets.last_trade_price if closed=true and outcome_label NULL)
  3. For each gate that failed, count this as a "rejection". If the recorded
     outcome matches the LLM-predicted direction (impact_direction), count as
     "would have been correct".
  4. FRR(gate) = count(would-have-been-correct) / count(rejection)
```

Per-gate outputs:

| Gate | n_rejected | n_with_outcome | FRR | mean_brier_if_kept | recommended_action |
|---|---|---|---|---|---|
| cosine_score < 0.52 | 1234 | 567 | 0.61 | 0.18 | Lower threshold to 0.45 (FRR 0.40 + Brier 0.22) |
| ambiguity > 0.6 | 234 | 89 | 0.42 | 0.31 | Keep — signals would not have helped |

(Numbers above are illustrative.)

## 5. Counterfactual evaluation

For each gate, also compute "what if the threshold were ± 1 std?":

- The 3 numeric gates (cosine, ambiguity, specificity) are amenable: enumerate {threshold − 0.10, threshold − 0.05, threshold, threshold + 0.05, threshold + 0.10} and report Brier / hit-rate / PnL on the rejected-set-with-outcomes.
- The categorical gates (direction in NEUTRAL/UNCLEAR, no LLM analysis, no excerpts) are not threshold-tunable — for these we only report FRR.

## 6. Pass / Fail criteria for the chantier

The chantier produces a *report*, not a code change. It passes when:

1. The audit doc lists FRR + counterfactual delta for each of the 13 gates.
2. At least 3 of the 13 gates have a clear "lower threshold" or "raise threshold" recommendation backed by a Brier-CI-disjoint comparison.
3. The data-availability gap (rejected pairs without `outcome_label`) is quantified — if backfill is needed to reach statistical significance, that backfill is shipped as part of this chantier.

## 7. What we explicitly will NOT do here

- Touch any gate threshold in production code.
- Change the scorer.
- Add new gates.
- Build a learned-classifier replacement.

The report goes to `docs/audit/`. The threshold changes that survive review become a *separate* PR in a follow-up chantier — same discipline as `clustering-tuning-followup`.

## 8. Risks

| Risk | Mitigation |
|---|---|
| `event_market_features.outcome_label` not filled for rejected pairs → too few data points | Task 1 measures coverage; if low, backfill via `markets.closed=true` join is added before analysis |
| Outcome leakage (we use the *current* `markets.last_trade_price`, which post-dates the rejection) | Only use markets where `outcome_label is NOT NULL` (binary 0/1 on ≥0.95/≤0.05 band) — these are unambiguous resolutions, no near-miss noise |
| Threshold tuning over-fits to 90-day window | Recommend changes only when CI-disjoint vs current threshold — same gate as the heuristic tuner uses ([scripts/tune_heuristic_weights.py:169](../../scripts/tune_heuristic_weights.py)) |
| LLM `impact_direction` is itself wrong (not just the gate) | Out of scope for this chantier — flagged as "LLM calibration" in §10 |

## 9. Why this before tuning weights or calibrating probabilities

If gate 1 (cosine < 0.52) rejects 60 % of would-have-been-correct signals, no amount of weight tuning recovers them — they never reach the scorer. Gates pre-filter the data the scorer ever sees. **Order matters: gates → scorer → calibration.**

## 10. Follow-ups this report should enable

1. Threshold-change PR (next chantier) — apply the recommendations that pass the gate.
2. Heuristic weight tuning — once gates are sane, re-run `tune_heuristic_weights.py` on the now-larger held-out set.
3. Probability calibration (isotonic regression on `signal_predictions.predicted_probability` vs `outcome_label`) — orthogonal to gates, can run in parallel.
4. Per-bucket / per-horizon breakdown of `/api/admin/metrics/variants` — observability debt, separate chantier.
