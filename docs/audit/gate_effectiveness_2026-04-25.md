# Gate Effectiveness Backtest — Report

**Generated:** 2026-04-25  
**Window:** last 90 days  
**Pairs analyzed:** 5469  
**Pairs with clear LLM direction (BUY_YES/BUY_NO):** 1478  
**Pairs with binary outcome (price ≤0.05 or ≥0.95):** 464  
**Pairs gradeable (clear direction AND binary outcome):** 109  
**Pairs passing all 6 replayable gates:** 1107  
**Companion PR:** [#3 — instrumentation](https://github.com/vcapton-jpg/polymarket-ai/pull/3)

## Executive summary

- **Cosine gate FRR = 0.640 [0.440, 0.840]** (n=25). The CI overlaps 0.50 (random-direction baseline) so the finding is not statistically conclusive, but the central estimate is directional: pairs the cosine gate rejects appear to retain useful signal.
- **No statistically significant threshold changes recommended** — sample size is below the CI-disjoint floor for every gate. The default thresholds may be fine, or the data volume is the bottleneck. Re-run after PR #3 has accumulated 2-4 weeks of `event_market_features` rows.
- **Coverage bottleneck:** only 109 of 5469 analyzed pairs (2.0 %) are gradeable. Two filters compound: (a) the LLM commits to BUY_YES/BUY_NO on only 1478 pairs (27.0 %); (b) only 464 markets (8.5 %) closed in the binary band within the window. This is structural, not a bug — many events are filed but never reach a clean YES/NO resolution.

## Per-gate False-Rejection Rate (FRR)

FRR = `P(LLM-predicted direction matches outcome | gate rejected the pair)`. Higher FRR = the gate is over-rejecting useful signals. `outcome` is the binary-band resolution (≥0.95→1, ≤0.05→0).

| Gate | Threshold | n_rejected | n_with_outcome | FRR | CI95 | Note |
|---|---|---|---|---|---|---|
| `cosine` | 0.52 | 3066 | 25 | 0.640 | [0.440, 0.840] | low-N (interpret with caution) |
| `direction_clear` | — | 3991 | 0 | — | — | low-N (interpret with caution) |
| `ambiguity` | 0.80 | 1218 | 0 | — | — | low-N (interpret with caution) |
| `specificity` | 0.40 | 2847 | 0 | — | — | low-N (interpret with caution) |
| `impact_strength` | — | 996 | 0 | — | — | low-N (interpret with caution) |
| `has_reasoning` | — | 0 | 0 | — | — | low-N (interpret with caution) |

## Counterfactual threshold sweep (numeric gates)

For each numeric gate, ± 0.05 / ± 0.10 around the default. Same FRR metric.

| Gate | Δ | Threshold | n_rejected | n_with_outcome | FRR | CI95 |
|---|---|---|---|---|---|---|
| `cosine` | -0.10 | 0.42 | 965 | 3 | 1.000 | [1.000, 1.000] |
| `cosine` | -0.05 | 0.47 | 1722 | 8 | 0.875 | [0.625, 1.000] |
| `cosine` | 0   | 0.52 | 3066 | 25 | 0.640 | [0.440, 0.840] |
| `cosine` | +0.05 | 0.57 | 4016 | 46 | 0.609 | [0.457, 0.761] |
| `cosine` | +0.10 | 0.62 | 4740 | 78 | 0.603 | [0.500, 0.718] |
| `ambiguity` | -0.10 | 0.70 | 1770 | 0 | — | — |
| `ambiguity` | -0.05 | 0.75 | 1770 | 0 | — | — |
| `ambiguity` | 0   | 0.80 | 1218 | 0 | — | — |
| `ambiguity` | +0.05 | 0.85 | 1218 | 0 | — | — |
| `ambiguity` | +0.10 | 0.90 | 0 | 0 | — | — |
| `specificity` | -0.10 | 0.30 | 1987 | 0 | — | — |
| `specificity` | -0.05 | 0.35 | 2847 | 0 | — | — |
| `specificity` | 0   | 0.40 | 2847 | 0 | — | — |
| `specificity` | +0.05 | 0.45 | 3096 | 3 | 0.333 | [0.000, 1.000] |
| `specificity` | +0.10 | 0.50 | 3096 | 3 | 0.333 | [0.000, 1.000] |

## Recommended threshold changes

_None — no CI-disjoint alternative found at current data volume._

## Deferred gates (require PR #1 instrumentation data)

These 7 gates depend on at-time market state (`spread`, `last_trade_price`, `liquidity`, `volume_24h`) that was not historically snapshotted. They become backtestable 2-4 weeks after [PR #3](https://github.com/vcapton-jpg/polymarket-ai/pull/3) merges and `event_market_features` accumulates.

- `spread`
- `price_band`
- `no_llm_analysis`
- `no_excerpts`
- `unclear_recommendation`
- `market_quality`
- `catalyst_disagrees_with_market`

## Methodology

1. SQL pull joins `event_market_analysis` × `event_market_candidates` × (`signal_outcomes` for passed pairs OR `markets.closed=true AND price ∈ binary band` for rejected pairs).
2. For each pair, the 6 replayable gates are evaluated against the stored LLM analysis + cosine.
3. For each gate, FRR counts the share of rejected pairs whose LLM direction matches the eventual outcome — i.e., the share of "would have been correct" rejections.
4. CI95 via 1 000-sample bootstrap, seed 42 (deterministic across runs).
5. A recommendation fires only if a less-strict threshold has FRR CI95 disjoint from (and below) the default's FRR — same gate as `scripts/tune_heuristic_weights.evaluation_gate`.
6. Categorical gates (`direction_clear`, `impact_strength`, `has_reasoning`) are not threshold-tunable — only their FRR is reported.
