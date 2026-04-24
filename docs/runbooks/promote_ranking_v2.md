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
