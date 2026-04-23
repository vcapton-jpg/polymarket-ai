# Promote `signal_v2_reranked` to production

This is a **manual** gate. Nothing auto-promotes. Run it when the shadow
variant has accumulated enough data to judge it honestly.

## Pre-conditions

1. ≥ 14 calendar days of shadow traffic (i.e. at least 14 days since the first
   `signal_v2_reranked` row landed in `signal_predictions`).
2. `n_resolved ≥ 100` per variant in the current 14-day window — check:
   ```bash
   docker compose exec -T app python -m scripts.report_metrics --window 14d
   ```
   Both `signal` and `signal_v2_reranked` must show `n ≥ 100`.

If either condition is not met: **wait longer**. Small samples will lie.

## The gate

Promotion is allowed **if and only if all three hold**:

| Check                                            | Pass condition                                                     |
|--------------------------------------------------|--------------------------------------------------------------------|
| `wilson_ci95_low("signal_v2_reranked")`          | `> wilson_ci95_high("signal")`                                     |
| `brier("signal_v2_reranked")`                    | `< brier("signal")`                                                |
| `pnl_total("signal_v2_reranked")`                | `> pnl_total("signal")`                                            |

All three numbers come from `/api/admin/metrics/variants?window=14d`. The CLI
report renders them side by side — eyeball or script the comparison.

If **any** check fails: do NOT promote. Options:

- Tune `SOURCING_ALPHA` / `SOURCING_BETA` / `SOURCING_RECENCY_TAU_HOURS`, redeploy, wait another week.
- Widen/narrow `SOURCING_POOL_WINDOW_HOURS`.
- Add per-tier source weighting (next chantier).

## The promotion (code change)

1. In `app/signal/signal_builder.py::build_signal`, replace the existing
   recency-only article selection with the `ArticleRanker`-backed path:

   ```python
   pool = await fetch_candidate_articles(s, event_id=event["id"], t0=now,
                                         window_hours=settings.sourcing_pool_window_hours)
   ranker = ArticleRanker.from_settings(settings)
   ranked = ranker.rank(pool, market_embedding, t0=now, top_k=settings.sourcing_top_k)
   articles = [by_id[r.news_clean_id] for r in ranked]   # same dict shape as today
   ```

2. Remove `app/workers/tasks_sourcing.py` and the autodiscover entry in
   `app/workers/celery_app.py` — the shadow task has no more reason to run.

3. Rename the production variant in `_persist_signal` recording so the
   measurement layer keeps a clean "before/after" split:

   ```python
   # ...in record_baselines, change the variant label for the prod row from
   #   "signal"  →  "signal_v2"    (this is the *next* name, not the shadow)
   # OR (preferred): leave record_baselines alone; rely on the historical
   # divide in resolved_at — rows before the deploy are "signal_v1", after
   # are "signal_v2". No code change needed if the CLI can slice by
   # resolved_at window.
   ```

4. Update `.env` on prod: `SOURCING_SHADOW_ENABLED=false` (redundant after
   step 2 but a belt-and-suspenders safeguard).

5. Deploy. Run `scripts/report_metrics --window 14d` the next day — the new
   variant should start accumulating rows.

## Rollback

If the promoted variant regresses vs the historical baseline after 1 week:

1. Revert the promotion commit (single commit that bundles steps 1–4 above).
2. Redeploy. No DB migration needed — `signal_articles` with `variant='signal'`
   and `variant='signal_v2_reranked'` stay valid historical records.

## Audit a specific signal

To see the five articles any given signal saw under each variant:

```sql
SELECT sa.variant, sa.rank, sa.score, sa.cosine_score, sa.recency_weight,
       nc.clean_text ~ 'fragment' AS matched_text_fragment,
       n.title, n.source_name, n.publish_date
FROM signal_articles sa
JOIN news_clean nc ON nc.id = sa.news_clean_id
JOIN news n ON n.id = nc.news_id
WHERE sa.signal_id = <id>
ORDER BY sa.variant, sa.rank;
```
