# Promote `embedding_v2` to production — per-surface manual gate

This is a **manual** gate. Nothing auto-promotes. Run it once per surface
(news, market, event) after the corresponding composer v2 has accumulated
enough `embedding_v2` coverage in the DB.

## Pre-conditions (per surface)

1. **Backfill ≥ 95% complete.** Check:
   ```bash
   docker compose exec -T db psql -U postgres -d signal -c "
     SELECT
       SUM(CASE WHEN embedding_v2 IS NULL THEN 1 ELSE 0 END)::float
       / GREATEST(COUNT(*), 1)::float AS null_fraction
     FROM news_clean;"
   ```
   (Repeat for `markets` and `events` as needed.) The `null_fraction` must be ≤ 0.05.
   If not, run the backfill until it is:
   ```bash
   docker compose exec -T app python -c "
   from app.workers.tasks_embeddings_backfill import recompute_embedding_v2
   while True:
       r = recompute_embedding_v2.apply(kwargs={'surface':'news','batch_size':200}).get()
       print(r)
       if r['remaining'] == 0:
           break
   "
   ```

2. **≥ 100 eval pairs per label source.** The harness prints `n` per metric
   per source. If any source has `n < 30`, the stratification check (#3
   below) is not reliable — wait for more data or accept the noise risk.

## The gate

Run the harness diff:

```bash
docker compose exec -T app python -m scripts.eval_embeddings \
    --variant v2 --surface <news|market|event> \
    --baseline docs/eval_baselines/embeddings_2026-04-24_v1.json
```

Promotion for that surface is allowed **if and only if all three hold**:

| Check                          | Pass condition                                                              |
|--------------------------------|------------------------------------------------------------------------------|
| Statistical confidence         | `retrieval@5(v2).ci_low > retrieval@5(v1).ci_high`                           |
| Ranking quality                | `nDCG@10(v2) > nDCG@10(v1)` (absolute delta)                                 |
| Cross-source consistency       | `retrieval@5(v2) > retrieval@5(v1)` on **each** source stratum independently |

The CLI's `--baseline` mode renders the three checks inline. Eyeball or grep
for `↑ improved` / `= flat` / `↓ regressed` per metric.

If **any** check fails: do NOT promote this surface. Options:
- Iterate on the composer (adjust A1's lead/tail ratio, A3's bracket label,
  A4's summary slice), reset `embedding_v2 = NULL` on the affected surface,
  rerun backfill, rerun eval.
- Accept the failure and leave v1 in place.

## Executing promotion

Different pre-flight per surface.

### For `news` or `event` (no index change needed)

1. Confirm gate passes.
2. Update `.env` on prod:
   ```
   EMBEDDINGS_VARIANT_NEWS=v2       # or EMBEDDINGS_VARIANT_EVENT=v2
   ```
3. Redeploy the `pipeline` and `scoring` queue workers + API.

### For `market` (requires migration 023)

1. Confirm gate passes.
2. **Apply migration 023** (creates HNSW index on `markets.embedding_v2`):
   ```bash
   docker compose exec -T app alembic upgrade 023
   ```
   Verify:
   ```bash
   docker compose exec -T db psql -U postgres -d signal -c "
     SELECT indexname FROM pg_indexes
     WHERE indexname = 'idx_markets_embedding_v2_hnsw';"
   ```
3. Update `.env`:
   ```
   EMBEDDINGS_VARIANT_MARKET=v2
   ```
4. Redeploy the `scoring` and `pipeline` queue workers + API.

## Monitoring (first 7 days post-flip, per surface)

- **Signal volume.** No abnormal drop vs the prior 7-day window.
- **Brier / P&L.** Chantier #1's `/api/admin/metrics/variants` shows the
  current production variant; its Brier/P&L must not regress by more than
  10% vs the pre-flip 7-day window.
- **Latency.** For the market surface in particular, monitor
  `hybrid_search_markets` p95 — if the HNSW index on `embedding_v2` is
  missing or misconfigured, this will spike.

## Rollback

Instant:
1. Flip `EMBEDDINGS_VARIANT_<SURFACE>=v1` in `.env`.
2. Redeploy workers + API.

`embedding` column is untouched, so v1 resumes immediately without any
data operation. No migration rollback needed. Write a short post-mortem
noting the gap between harness verdict and production — that gap indicates
a missing case in the label set that needs adding to `app/eval/labels.py`
before the next candidate.

## Audit one query's retrieval under each variant

To compare what event E retrieves under v1 vs v2 for a given surface:

```bash
docker compose exec -T app python -c "
import asyncio
from app.db.database import get_session_factory
from app.eval.runner import _fetch_embedding_for_query, _fetch_candidate_pool

async def main():
    factory = get_session_factory()
    async with factory() as s:
        for variant in ('v1', 'v2'):
            q = await _fetch_embedding_for_query(s, 'event_to_market', <EVENT_ID>, variant)
            pool = await _fetch_candidate_pool(s, 'event_to_market', <EVENT_ID>, variant)
            scored = sorted(
                [(cid, sum(x*y for x,y in zip(q, e))) for cid, e in pool if e is not None],
                key=lambda t: -t[1],
            )[:10]
            print(variant, scored)

asyncio.run(main())
"
```

Replace `<EVENT_ID>` with the event you want to audit.
