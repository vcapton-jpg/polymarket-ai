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

**Caveat — shadow coverage in production.** The current production path
(`app/signal/signal_builder.py::_persist_signal`) calls `record_baselines`
with `features=None, llm_combined=None`, which means
`heuristic_shadow` is silently skipped even when the flag is on. To
exercise shadow in prod, a future change must thread the
`EventMarketFeatures` row into `_persist_signal`'s scope and pass it to
`record_baselines`. Until then, shadow confirmation must rely on the
offline tuner's `gate` output plus the integration tests in
`tests/integration/test_heuristic_shadow_write.py`.

## Step 2 — Confirm offline finding on shadow data

Re-run validation (filter to the `heuristic_shadow` variant if the
production shadow gap above is closed; otherwise re-run the tuner on
newer data):

```bash
docker compose exec app python -m scripts.validate_heuristic_weights \
    --horizon t1h \
    --out docs/audit/heuristic_shadow_confirmation_$(date +%Y-%m-%d).md
```

Check that `heuristic_shadow.brier_mean` ≤ the tuner's candidate Brier
(±1–2% is acceptable — shadow samples come from a fresher time window).

## Step 3 — Promote

1. Edit `app/scoring/weights.py`:
   update the `HeuristicWeights` default values to match the candidate.
2. Edit `HeuristicWeights.frozen_v1` to **re-snapshot the new defaults**
   (so the next tuning run has the new baseline, not the old one).
3. Update any pin tests that hardcode the old defaults
   (`tests/unit/test_heuristic_weights.py`,
   `tests/unit/test_heuristic_scorer.py::test_compute_score_pin_with_llm`
   and `test_compute_score_pin_without_llm`).
4. Update `app/core/config.py` field defaults if they drifted
   (they shouldn't — all candidates respect sum=1).
5. Run `pytest tests/unit/test_heuristic_weights.py tests/unit/test_heuristic_scorer.py tests/unit/test_strength_scorer.py tests/unit/test_trade_scorer.py tests/unit/test_config_integrity.py -v`.
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
`docs/audit/`. The dev DB still has pre-shadow data; no DB rollback
needed.
