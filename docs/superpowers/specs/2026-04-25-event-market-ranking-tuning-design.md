# Chantier #4 — Event→Market Ranking Tuning: Design

**Date:** 2026-04-25
**Status:** Draft (pending user review)
**Depends on:** chantier #1 (measurement foundations), chantier #2 (signal sourcing), chantier #3 (embeddings eval harness)

## 1. Goal

Turn the current event→market hybrid search from an untuned set of hand-picked
constants into an empirically-tuned ranker, validated against a human-seeded
ground-truth label set and gated by the chantier #3 eval harness.

The ranking quality problem was flagged in the initial audit ("matching market
fragile — hybrid search OK mais pas de ground truth pour valider"). Chantier #3
shipped the measurement infrastructure (`retrieval@k`, `nDCG@10`,
`cluster_purity`, `cluster_event_to_market` surface) explicitly to unblock this
chantier.

Non-goals:
- Not replacing the hybrid search architecture (vector + BM25 + RRF + entity boost).
- Not introducing a cross-encoder LLM reranker in the synchronous signal path.
- Not clustering/canonicalising Polymarket markets that duplicate each other.
- Not running canary A/B in production.

Those are candidates for future chantiers (scored after this one ships).

## 2. Architecture

Two paths coexist after this chantier:

**Production synchronous path (latency-neutral):**
```
event created
  → hybrid_search_markets(event)        # dispatcher reads ranking_variant flag
  → top-k markets
  → scoring heuristique
  → signal
  → [async] schedule_ranking_shadow.delay(event_id)
```

**Offline tuning path (one-shot human work, then repeatable):**
```
scripts/label_event_market_seed.py        # ~1h human review, 50-100 seed pairs
  ↓
app/eval/labels_event_market.py            # LLM-judge calibrated via seed, scale to 500
  ↓
scripts/tune_event_market_ranking.py       # coordinate descent over 5 params
  ↓
docs/eval_baselines/ranking_event_market_best_*.json
  ↓ [manual] update config.py defaults
  ↓ [manual] flip ranking_variant_event_to_market = "v2" after 48h shadow observation
```

**Key coherence:** mirrors chantier #3's shadow-first / manual-promote pattern,
applied to ranking weights instead of embeddings. Operators see the same
ergonomics.

**Tech stack:** Python 3.12, SQLAlchemy 2.0 async, Alembic, FastAPI, Celery,
pgvector, pytest-asyncio, OpenAI `gpt-4o-mini` (LLM-judge only, offline).

## 3. File Structure

**New files:**

| Path | Responsibility |
|---|---|
| `app/retrieval/hybrid_search_v2.py` | v2 formula: v1 + date_proximity + bucket_match, reads 5 weights from settings |
| `app/retrieval/ranking_variant.py` | `active_ranking_variant()` helper + `hybrid_search_markets_dispatch()`; whitelist-enforced |
| `app/eval/labels_event_market.py` | `load_event_market_labels()` → `list[LabeledPair]`; LLM-judge calibrated from human seed |
| `app/workers/tasks_ranking_shadow.py` | Celery task `record_shadow_ranking(event_id)` — computes opposite-variant top-k, stores in shadow table |
| `scripts/label_event_market_seed.py` | Human review CLI producing the 50-100 pair seed |
| `scripts/tune_event_market_ranking.py` | Coordinate descent over 5 params against ground truth labels |
| `scripts/analyze_ranking_shadow.py` | Offline report: divergence rate, per-bucket stats, signal delta projection |
| `docs/eval_labels/event_market_seed_2026-04-25.jsonl` | Human seed output (checked-in, ~50-100 lines) |
| `docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl` | Scaled labels (checked-in, ~500 lines) |
| `docs/eval_baselines/ranking_v1_2026-04-25.json` | Frozen v1 baseline against ground truth |
| `docs/eval_baselines/ranking_event_market_best_2026-04-25.json` | Best v2 config + per-bucket deltas |
| `docs/runbooks/promote_ranking_v2.md` | Operator runbook for the 3-check gate + flip |
| `alembic/versions/024_add_event_market_ranking_shadow.py` | Shadow table migration |
| `tests/unit/test_hybrid_search_v2.py` | Formula correctness + v1-equivalence when weights zeroed |
| `tests/unit/test_ranking_variant.py` | Dispatcher routes by flag; invalid flag defaults to v1 |
| `tests/unit/test_labels_event_market.py` | JSONL parsing, LabeledPair construction, weak_match gain |
| `tests/unit/test_tune_event_market_ranking.py` | Coordinate descent convergence, offline gate logic |
| `tests/integration/test_ranking_shadow.py` | Shadow task writes correct row, idempotent |
| `tests/integration/test_hybrid_search_v2_db.py` | Dispatcher routes by flag, v1/v2 return coherent shapes |

**Modified files:**

| Path | Change |
|---|---|
| `app/retrieval/__init__.py` | Export dispatcher; unchanged call-site signature |
| `app/retrieval/hybrid_search.py` | Untouched (v1 bit-exact regression shield) |
| `app/core/config.py` | Add 7 new settings (see Section 5) |
| `app/event_engine/event_builder.py` OR `app/workers/tasks_scoring.py` | Insert shadow hook (chosen at plan time) |

The hybrid search module stays small and focused. v1 is frozen. v2 lives in its
own module. The dispatcher is a 20-line helper. No file grows past ~200 lines.

## 4. Ground Truth Construction

### 4.1 Human seed (~1h, one-shot)

`scripts/label_event_market_seed.py` selects 100 events from the last 30 days,
stratified by bucket (politics / crypto / sports / tech / other — 20 each).
For each event, it fetches hybrid_search v1's top-20. Of the resulting 2000
candidates, we sample 500 stratified by rank bucket:
- 100 from ranks 1-3
- 100 from ranks 4-10
- 100 from ranks 11-20
- 200 from **hors-top-20** (random market sample, same bucket)

Why the 200 hors-top-20: this is the **anti-bias move**. If we only label
what v1 returned, we train our tuning on v1's own blind spots. Forcing 40% of
the seed to be markets v1 never ranked exposes the LLM-judge (and later the
grid search) to "markets we missed" as well as "markets we kept".

The CLI presents each pair with:
- Event: title, summary, bucket, entities
- Market: question, category, end_date, cosine_score, rrf_score, entity_matches

Verdicts: `strong_match` / `weak_match` / `not_related`. Output appended to
`docs/eval_labels/event_market_seed_2026-04-25.jsonl` line-by-line (idempotent
resume on rerun). Target: ~7 sec/pair × 500 = ~1 hour.

### 4.2 LLM-judge calibrated (one-shot + reusable)

`app/eval/labels_event_market.py` defines a prompt with 9 few-shot examples
pulled from the human seed: 3 per verdict (`strong_match`, `weak_match`,
`not_related`), chosen to span at least 3 different buckets to avoid
bucket-specific overfitting. Input: 1 event + 20 markets batched in 1 call.
Output: structured JSON `[{market_id, verdict, reason}]`. Model:
`gpt-4o-mini`. Budget cap: $10 per run (~3000 judgeable pairs, ample for 500).

**Agreement check**: 50 pairs from the human seed are held out. Run the
LLM-judge on them. Compute exact-match agreement on `verdict`. If ≥ 80% →
scale. If < 80% → re-calibrate the prompt (manual, not blocking the plan;
flagged as "DONE_WITH_CONCERNS" for operator attention).

### 4.3 Scale

Re-run the calibrated LLM-judge on 500 new pairs (fresh events not in the
seed, same bucket/rank stratification). Final ground truth file
`docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl` = the 500
human-labeled seed pairs **plus** the 500 LLM-labeled pairs = **1000 pairs
total**. Each row carries `source: "human" | "llm_calibrated"` for downstream
filtering if needed. The 50-pair hold-out used for agreement (Section 4.2) is
excluded from this file.

### 4.4 Binding with chantier #3 harness

`load_event_market_labels()` returns `list[LabeledPair]` compatible with the
chantier #3 `runner.run_eval()` interface. Convention:
- `query_id = event_id`
- `relevant_ids = [market_id for pair where verdict in ("strong", "weak")]`
- Weak matches contribute `gain=0.5` in nDCG; strong contribute `gain=1.0`

The existing `runner.py` needs no refactoring — only a new label source.

## 5. Hybrid Search v2 Formula

### 5.1 v1 (current, frozen)

```
rrf_score(m) = 1/(rrf_k + vec_rank(m) + 1) + 1/(rrf_k + bm25_rank(m) + 1)
             + entity_matches(m) * ENTITY_BOOST_PER_MATCH   # 0.5 each
```

### 5.2 v2

```
rrf_score_v2(m) = 1/(rrf_k + vec_rank(m) + 1) + 1/(rrf_k + bm25_rank(m) + 1)
                + entity_matches(m) * w_entity
                + date_proximity(m, event) * w_date
                + bucket_match(m, event) * w_bucket
```

where:

```python
def date_proximity(market, event) -> float:
    """Exponential decay past 7 days; 0 if already resolved."""
    if market.end_date is None:
        return 0.0
    days_until = (market.end_date - event.last_seen).days
    if days_until < 0:
        return 0.0
    return math.exp(-max(0, days_until - 7) / tau_days)

def bucket_match(market, event) -> float:
    if event.bucket in (None, "other"):
        return 0.0
    return 1.0 if market.bucket == event.bucket else 0.0
```

### 5.3 Settings (added to `app/core/config.py`)

```python
ranking_variant_event_to_market: Literal["v1", "v2"] = "v1"
ranking_shadow_enabled: bool = True
ranking_v2_rrf_k: int = 60
ranking_v2_w_entity: float = 0.5
ranking_v2_w_date: float = 0.0       # off until tuned
ranking_v2_w_bucket: float = 0.0     # off until tuned
ranking_v2_tau_days: float = 14.0
ranking_v2_min_sim: float = 0.45
```

Defaults make v2 ≡ v1 bit-exact. The tuning step overwrites defaults. Operators
flip the variant flag separately and deliberately after shadow observation.

### 5.4 Dispatcher

```python
# app/retrieval/ranking_variant.py
_VALID = ("v1", "v2")

def active_ranking_variant() -> str:
    v = getattr(get_settings(), "ranking_variant_event_to_market", "v1")
    return v if v in _VALID else "v1"

async def hybrid_search_markets(session, event_emb, event_text, **kwargs):
    if active_ranking_variant() == "v2":
        from .hybrid_search_v2 import hybrid_search_markets_v2
        return await hybrid_search_markets_v2(session, event_emb, event_text, **kwargs)
    from .hybrid_search import hybrid_search_markets as v1
    return await v1(session, event_emb, event_text, **kwargs)
```

All existing call-sites continue to `await hybrid_search_markets(...)` with no
change.

## 6. Offline Tuning

### 6.1 Parameter space

| Param | v1 | Grid | Count |
|---|---|---|---|
| `rrf_k` | 60 | 30, 60, 90, 120 | 4 |
| `w_entity` | 0.5 | 0.1, 0.3, 0.5, 0.8, 1.2 | 5 |
| `w_date` | — | 0, 0.2, 0.5, 1.0 | 4 |
| `w_bucket` | — | 0, 0.1, 0.3, 0.5 | 4 |
| `tau_days` | — | 7, 14, 30, 60 | 4 |
| `min_sim` | 0.45 | 0.35, 0.45, 0.55 | 3 |

Full grid = 3840 — too large. **Coordinate descent** instead:
- 2 passes over the parameter order `[w_entity, w_date, w_bucket, tau_days, min_sim, rrf_k]`
- Each param: fix others at current value, sweep its range, keep the best
- ~52 evaluations total
- Each eval uses pre-computed embeddings: ~5s → ~5 min total wall-clock

### 6.2 Scoring

Primary: `retrieval@5`. Tiebreak: `nDCG@10`. Reported per-bucket for
regression detection.

### 6.3 Offline gate (before shadow phase)

All three must pass, computed via 1000-iteration bootstrap (same as
chantier #3):
1. `retrieval@5_v2` CI-low > `retrieval@5_v1` CI-high (strict disjoint)
2. `nDCG@10_v2` mean > `v1` mean (CI overlap tolerated)
3. No bucket regresses > 5% on retrieval@5 vs v1

If gate fails → stop chantier, document diagnosis in
`ranking_event_market_best_*.json` under `gate_status: "failed"`.

### 6.4 CLI

```
python -m scripts.tune_event_market_ranking \
    --labels docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl \
    --out docs/eval_baselines/ranking_event_market_best_2026-04-25.json \
    [--resume]
```

Idempotent; `--resume` reads partial JSON and continues from the last completed
coordinate.

## 7. Shadow Rollout & 3-Check Gate

### 7.1 Shadow table (migration 024)

```sql
CREATE TABLE event_market_ranking_shadow (
    id BIGSERIAL PRIMARY KEY,
    event_id INT NOT NULL REFERENCES events(id),
    market_id TEXT NOT NULL,
    variant TEXT NOT NULL CHECK (variant IN ('v1','v2')),
    rank INT NOT NULL,
    rrf_score DOUBLE PRECISION NOT NULL,
    cosine_score DOUBLE PRECISION,
    entity_matches INT,
    date_proximity DOUBLE PRECISION,
    bucket_match BOOLEAN,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, variant, rank)
);
CREATE INDEX ON event_market_ranking_shadow (event_id, variant);
```

Retention: cron cleanup after 30 days (added to existing housekeeping worker,
out-of-scope if no housekeeping exists — defaults to manual DELETE).

### 7.2 Shadow hook

Inserted in `event_builder.py` (after event commit) or `tasks_scoring.py`
(after scoring enqueue) — chosen at plan time based on call graph. Same
try/except + local import pattern as chantier #1's `schedule_shadow_variants`:
```python
if settings.ranking_shadow_enabled:
    try:
        from app.workers.tasks_ranking_shadow import record_shadow_ranking
        record_shadow_ranking.delay(event_id)
    except Exception as exc:
        logger.debug("shadow ranking enqueue failed event_id=%s: %s", event_id, exc)
```

### 7.3 Shadow task

`record_shadow_ranking(event_id)`:
- Queue: `scoring`
- `acks_late=True, reject_on_worker_lost=True`
- Reads event, runs `hybrid_search_markets_{opposite_variant}`
- Writes top-5 to shadow table
- Idempotent via the `UNIQUE (event_id, variant, rank)` constraint + ON CONFLICT DO NOTHING

### 7.4 Observation (48h, ≥ 200 events)

`scripts/analyze_ranking_shadow.py` produces a report:
- **Divergence rate**: % events where top-1 differs, % where top-5 set
  intersection < 3
- **Per-bucket stats**: divergence by bucket
- **Signal delta projection**: for events that produced a signal on v1, what
  would the signal have been on v2? Match/mismatch rate. Proxy for downstream
  stability.
- **Outcome cross-check (best effort)**: for events ≥ 24h old, do the top-5 v2
  markets have outcomes that suggest better/worse discrimination?

### 7.5 3-check gate (manual, runbook)

Operator flips flag only if:
1. ✅ Offline gate passed (Section 6.3)
2. ✅ ≥ 200 events shadow-scored over 48h; divergence rate between 10% and
   50% (both bounds matter: < 10% = no meaningful change, > 50% = suspicious)
3. ✅ No bucket shows v2 killing > 30% of v1's signals in projection

Flip command: update env / config → `ranking_variant_event_to_market=v2` → redeploy.
Rollback: same flip in reverse, < 1 min.

### 7.6 Monitoring post-flip

- `/api/admin/metrics/variants` (chantier #1) already segments signals by
  variant; Brier/P&L observable once 72h of outcomes accumulate
- Alert threshold: if 7-day Brier regresses > 10% post-flip → operator alert
  (not auto-rollback; human decision)

## 8. Testing

**Unit:**
- `test_hybrid_search_v2.py` — date_proximity formula edges (None, past, 0d, 7d, 30d), bucket_match cases, v1-equivalence when w_date=w_bucket=0
- `test_ranking_variant.py` — dispatcher, invalid flag defaults to v1
- `test_labels_event_market.py` — JSONL parse, LabeledPair construction, weak gain, agreement calculation
- `test_tune_event_market_ranking.py` — coordinate descent converges on synthetic, offline gate detects regression

**Integration:**
- `test_ranking_shadow.py` — full signal path schedules shadow task, row written, idempotent re-run
- `test_hybrid_search_v2_db.py` — dispatcher routes by flag, shapes match

**Regression shield:** the 239 tests currently green (chantiers #1+#2+#3) must
remain green. Chantier #3's frozen v1 composer tests and eval harness tests are
load-bearing here.

## 9. Risks & Mitigations

| Risk | Probability | Mitigation |
|---|---|---|
| Human seed fatigue biases labels | Medium | 50-100 human reviews only; 400+ from calibrated LLM-judge; 50-pair hold-out for ≥ 80% agreement |
| LLM-judge biased toward v1's own top-20 | **High** | 40% of seed is random hors-top-20 markets; forces the judge to evaluate misses, not just hits |
| Grid search overfits 500 pairs | Medium | Coordinate descent ≠ full grid; 20% hold-out for final validation; bucket stratification prevents one bucket dominating |
| Shadow table grows unbounded | Low | 30-day retention; ~5 MB/month at current volumes |
| Downstream winrate regresses despite offline gate | Medium | Offline + shadow + 3-check gate + 1-flag rollback; Brier monitoring via chantier #1 |
| Date-proximity creates short-term bias (favors markets closing in 1 day) | Medium | Expected discovery; per-bucket stats surface it; mitigation = lower `w_date` or raise the 7d floor |

## 10. Rollback Levels

1. **Shadow only**: `ranking_shadow_enabled = False` → stops shadow compute, prod unchanged
2. **Flip**: `ranking_variant_event_to_market = "v1"` → instant return to v1
3. **Nuclear**: revert PR → v1 untouched, dispatcher trivial, v2 modules removed

## 11. Success Criteria

**Landed and ready to flip (minimum):**
- Offline gate passes on ≥ 1000 labeled pairs (500 human + 500 LLM-calibrated)
- Shadow observation shows ≥ 200 events with 10-50% divergence over 48h
- Per-bucket signal delta projection shows no bucket > 30% kill rate
- All 239 pre-existing tests green + new tests green
- Runbook committed; operator can flip in < 5 commands

**Flip successful:**
- Post-flip 7-day Brier/P&L (via chantier #1 dashboard) does not regress > 10%
- No unexpected alerts from monitoring metrics

If any of the "landed" criteria fail, the chantier still shipped useful
infrastructure (ground truth, shadow table, harness binding) that future work
can exploit — but the v2 variant stays dark.
