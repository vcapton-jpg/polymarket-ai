# Signal Sourcing & Traceability — Design Spec

**Chantier #2 of the "backend signals optimization" initiative.**
Follows chantier #1 (measurement foundations, spec `2026-04-23-measurement-foundations-design.md`) — this spec assumes `signal_predictions`, variant registry, admin metrics endpoints, and the `schedule_shadow_variants` stub all exist in production.

## 1. Goal

Improve the articles fed to every signal's reasoning step, from "top-5 most recent in the event cluster" to "top-5 ranked by relevance to the specific market question × recency", and ship it behind a **shadow variant** so its impact is measured honestly via chantier #1 before it replaces production.

Three concrete outcomes:
1. **Better sourcing** — articles scored per `(event × market)` pair, not just per event.
2. **Wider window** — soft recency decay replaces the hard 24h cutoff; window extended to 72h.
3. **Audit trail** — every signal × variant writes the articles it actually saw into a new `signal_articles` table. "Which 5 articles generated this signal?" becomes a single SQL query.

## 2. Non-goals

- No LLM reranker (cascade approach C from brainstorming). Ship the embedding-based ranker first, measure, decide later.
- No automatic promotion of the shadow to production. Promotion gate is human, informed by `/api/admin/metrics/variants`.
- No change to the retrieval pipeline upstream (events↔markets hybrid search stays as-is).
- No refactor of `reasoning_analyzer` beyond passing a different article list.
- No per-source-tier re-weighting. Existing `source_tier_mix` aggregation stays.

## 3. Architecture

### 3.1 Data flow — production (synchronous, unchanged latency)

```
signal_builder.build_signal(articles=top_5_by_recency)   ← unchanged
  → reasoning_analyzer(articles)                          ← unchanged
  → _persist_signal(sig)
     ├─ record_baselines(sig.id, ctx, registry)           ← chantier #1
     ├─ record_prod_signal_articles(sig, articles)        ← NEW: audit trail for the prod variant
     └─ schedule_shadow_variants(sig.id)                  ← was stub; now enqueues Celery task
```

### 3.2 Data flow — shadow (asynchronous, Celery)

```
tasks_sourcing.sourcing_shadow_rerun(signal_id)
  1. Idempotency gate: skip if SignalPrediction(signal_id, variant="signal_v2_reranked") exists
  2. Load Signal + Event + Market rows
  3. pool_builder.fetch_candidate_articles(event_id, t0, window_hours=72)
  4. ArticleRanker.rank(pool, market.embedding, t0, top_k=5)
     → list[RankedArticle(news_clean_id, rank, score, cosine, recency_weight)]
  5. reasoning_analyzer(ranked_articles)                   ← same LLM, same prompt (ranker already returned top_k)
  6. Persist:
     - SignalPrediction(signal_id, variant="signal_v2_reranked",
                        predicted_direction, predicted_probability)
     - 5 rows in signal_articles(variant="signal_v2_reranked")
  7. Commit. Errors → retry 3× exponential backoff; final failure = silent, no row written.
```

Running async means the shadow LLM call never affects production latency. The measurement endpoints in chantier #1 treat missing variant rows via `n_coverage vs n` — partial coverage is visible, not silently masked.

### 3.3 Modules (new & modified)

**New**
- `app/sourcing/__init__.py` — re-exports `ArticleRanker`, `RankedArticle`.
- `app/sourcing/article_ranker.py` — pure class `ArticleRanker`. Takes candidates + market embedding + t0, returns a ranked list. No I/O. Fully unit-testable.
- `app/sourcing/pool_builder.py` — async `fetch_candidate_articles(session, event_id, t0, window_hours)` → list of article dicts (news_clean_id, embedding, publish_date, clean_text, source_name, source_tier, source_weight).
- `app/sourcing/prod_trace.py` — `record_prod_signal_articles(session, signal_id, articles)`. Called from `_persist_signal`; writes the prod variant's articles into `signal_articles`. Kept separate from `ArticleRanker` because prod doesn't re-rank; it just records what it already used.
- `app/workers/tasks_sourcing.py` — `@celery_app.task(name="sourcing.shadow_rerun", rate_limit="30/m", max_retries=3)` `sourcing_shadow_rerun(signal_id: int)`.
- `alembic/versions/021_signal_articles.py` — migration.
- Tests as listed in §8.

**Modified**
- `app/measurement/pipeline.py::schedule_shadow_variants` — body becomes `from app.workers.tasks_sourcing import sourcing_shadow_rerun; sourcing_shadow_rerun.delay(signal_id)`. Wrapped in try/except (a broken Celery must not kill signal persistence).
- `app/signal/signal_builder.py::_persist_signal` — after `record_baselines`, call `record_prod_signal_articles(session, sig.id, articles)` with the same article list that `reasoning_analyzer` saw. Same try/except policy: measurement never blocks the signal.
- `app/core/config.py` — add:
  ```python
  sourcing_alpha: float                  = Field(default=0.7)
  sourcing_beta: float                   = Field(default=0.3)
  sourcing_recency_tau_hours: float      = Field(default=24.0)
  sourcing_pool_window_hours: int        = Field(default=72)
  sourcing_shadow_enabled: bool          = Field(default=True)   # kill switch
  sourcing_top_k: int                    = Field(default=5)
  ```

## 4. `signal_articles` schema

```sql
CREATE TABLE signal_articles (
    signal_id       BIGINT       NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    variant         VARCHAR(64)  NOT NULL,           -- 'signal' | 'signal_v2_reranked' | futures
    news_clean_id   BIGINT       NOT NULL REFERENCES news_clean(id) ON DELETE CASCADE,
    rank            SMALLINT     NOT NULL,           -- 1..top_k, 1 = highest score
    score           NUMERIC(6,4) NOT NULL,           -- composite [0,1]
    cosine_score    NUMERIC(6,4) NOT NULL,           -- raw cosine [0,1] (clipped)
    recency_weight  NUMERIC(6,4) NOT NULL,           -- exp decay [0,1]
    excerpt         TEXT         NULL,               -- LLM-selected quote, optional
    PRIMARY KEY (signal_id, variant, news_clean_id)
);
CREATE INDEX idx_sa_signal_variant ON signal_articles(signal_id, variant);
CREATE INDEX idx_sa_news_clean     ON signal_articles(news_clean_id);
```

**Why a composite PK including `variant`**: a given signal can have the same article in multiple variants at different ranks. Prod top-5 and shadow top-5 can overlap.

**Why no UNIQUE on `(signal_id, variant, rank)`**: rank is a display attribute, not an identity. If a future chantier ties for rank (unlikely given deterministic tie-break, but possible), we don't want the DB to reject the write.

**Cascade**: dropping a signal drops its articles; dropping a news_clean drops its references. This is correct — if the news row is gone, any historical reference to it should go with it. Signals are rarely deleted, so the practical effect is bounded.

## 5. Scoring formula

Given a candidate article with embedding `e_a`, publish_date `t_a`, and the market's embedding `e_m` evaluated at signal time `t0`:

```
cosine      = max(0, dot(e_a, e_m))                 # clipped to [0,1]; embeddings assumed normalized
age_hours   = max(0, (t0 - t_a).total_seconds() / 3600)
recency_w   = exp(-age_hours / τ)                   # τ = sourcing_recency_tau_hours (24h default)
score       = clip(α·cosine + β·recency_w, 0, 1)    # α=0.7, β=0.3; α+β need NOT equal 1
```

Ranking: sort by `score` descending, take top-k. **Tie-break** (two articles with identical `score`): the one with the more recent `publish_date` wins. If still tied, lower `news_clean_id` wins — gives deterministic order.

Decay table (for intuition):
| age_hours | recency_w (τ=24h) |
|-----------|-------------------|
| 0         | 1.00              |
| 12        | 0.61              |
| 24        | 0.37              |
| 48        | 0.14              |
| 72        | 0.05              |

Worked example: a 1h-old article with cosine 0.60 scores `0.7·0.60 + 0.3·0.96 = 0.71`. For a 48h-old article to match that score, it needs `0.7·cosine + 0.3·0.14 = 0.71`, i.e. cosine ≥ 0.96. In other words, with the default α/β, the ranker strongly favours recency when relevance differences are marginal — older articles only displace fresh ones when they're *much* more relevant. That matches how traders actually read news.

**Embedding source for the market** (`e_m`): we use `Market.embedding` (1536-dim pgvector, already populated by the retrieval pipeline). If a market has no embedding (rare edge case for freshly-ingested markets), the ranker degrades gracefully: all articles score `β·recency_w` only, ranking by recency — equivalent to today's production behaviour.

## 6. Pool builder

`fetch_candidate_articles(session, event_id, t0, window_hours=72)`:

```
SELECT news_clean.id, news_clean.embedding, news_clean.publish_date,
       news_clean.clean_text, news_clean.source_name, news_clean.source_tier,
       news_clean.source_weight
FROM news_clean
JOIN event_news_links ON event_news_links.news_clean_id = news_clean.id
WHERE event_news_links.event_id = :event_id
  AND news_clean.publish_date >= :t0 - INTERVAL ':window_hours hours'
  AND news_clean.publish_date <= :t0
  AND news_clean.embedding IS NOT NULL
ORDER BY news_clean.publish_date DESC;
```

Returns a list of dicts. The ranker is the consumer; it doesn't care about order (it re-sorts by score).

**Why not use the existing article fetching in `signal_builder`?** Because that code path is entangled with the recency-top-5 cap. Pool builder is a minimal, focused helper scoped to *"all articles for this event in the last 72h, with embeddings"*. Unit-testable without mocking the entire signal builder.

## 7. Celery task — `sourcing_shadow_rerun`

```python
@celery_app.task(
    name="sourcing.shadow_rerun",
    rate_limit="30/m",          # hard ceiling on LLM spend
    max_retries=3,
    default_retry_delay=30,      # exponential backoff: 30s, 60s, 120s
    acks_late=True,              # don't ack until task completes
)
def sourcing_shadow_rerun(signal_id: int) -> None:
    if not get_settings().sourcing_shadow_enabled:
        return   # kill switch

    async def _run():
        async with get_session_factory()() as s:
            # Idempotency
            existing = await s.execute(select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.variant == "signal_v2_reranked",
            ))
            if existing.scalar_one_or_none():
                return

            sig = await s.get(Signal, signal_id)
            if sig is None:
                return  # signal deleted between enqueue and run

            market = await s.get(Market, sig.market_id)
            pool   = await fetch_candidate_articles(s, sig.event_id, sig.created_at, window_hours=72)
            if not pool:
                return  # nothing to re-rank, silent skip

            ranker = ArticleRanker.from_settings(get_settings())
            ranked = ranker.rank(pool, market.embedding, sig.created_at, top_k=5)
            if not ranked:
                return

            # Convert RankedArticle → the dict shape reasoning_analyzer expects
            # (news_clean_id, title, clean_text[:800], source_name, source_tier, publish_date).
            article_dicts = _ranked_to_article_dicts(ranked, pool)

            # Same LLM, same prompt, different articles.
            result = await reasoning_analyzer.run(
                market=market, event=sig.event, articles=article_dicts,
            )

            s.add(SignalPrediction(
                signal_id=signal_id,
                variant="signal_v2_reranked",
                predicted_direction=result.direction,
                predicted_probability=result.probability,
            ))
            for r in ranked:
                s.add(SignalArticle(
                    signal_id=signal_id, variant="signal_v2_reranked",
                    news_clean_id=r.news_clean_id, rank=r.rank,
                    score=r.score, cosine_score=r.cosine,
                    recency_weight=r.recency_weight,
                    excerpt=r.excerpt,
                ))
            await s.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("shadow rerun failed for signal %s: %s", signal_id, exc)
        raise self.retry(exc=exc)
```

Characteristics:
- **Idempotent** via the uniqueness check.
- **Self-healing** via 3 retries with backoff.
- **Observable**: task name shows in Flower/Celery logs; failures log with signal_id.
- **Bounded cost** via `rate_limit`.
- **Killable** via the `sourcing_shadow_enabled` setting — flip to False, deploy, task returns immediately.

## 8. Testing strategy

**Unit tests**
- `tests/unit/test_article_ranker.py`
  - Deterministic ordering (same inputs → same output)
  - α=1, β=0 collapses to pure cosine ordering
  - α=0, β=1 collapses to pure recency ordering
  - Tie-break: identical score → newer publish_date wins
  - Top-k respected (len(result) ≤ top_k)
  - Market embedding `None` degrades to recency-only with a warning
  - Articles without embeddings are excluded from the pool

- `tests/unit/test_sourcing_pool_builder.py` (uses `async_db_factory`)
  - Window filter: articles older than 72h excluded
  - Only articles linked to the event (via `event_news_links`) returned
  - Articles with NULL embedding excluded

- `tests/unit/test_sourcing_prod_trace.py`
  - 5 articles in → 5 rows out with variant="signal"
  - Idempotent: rerun writes same rows via ON CONFLICT DO NOTHING
  - Schema conformance

**Integration tests**
- `tests/integration/test_sourcing_shadow.py`
  - Celery in eager mode (`CELERY_TASK_ALWAYS_EAGER=True`)
  - Create signal → task runs inline → assertions:
    - `SignalPrediction(variant="signal_v2_reranked")` exists
    - 5 rows in `signal_articles(variant="signal_v2_reranked")`
  - Idempotency: re-enqueuing the task does not create duplicate rows

- `tests/integration/test_sourcing_prod_audit.py`
  - Signal persisted → `signal_articles(variant="signal")` has 5 rows matching the articles shown to the LLM
  - Verify via join to `news_clean`

- `tests/integration/test_sourcing_shadow_kill_switch.py`
  - `sourcing_shadow_enabled=False` → task is a no-op (no rows written)

**Reuse from chantier #1**
- No new admin endpoint. Once shadow data lands, `/api/admin/metrics/variants?window=14d` shows `signal_v2_reranked` alongside `signal` and the four baselines.

## 9. Configuration surface

All tunable via environment (`.env`):

| Setting                            | Default | Role |
|------------------------------------|---------|------|
| `SOURCING_ALPHA`                   | 0.7     | Relevance weight in composite score |
| `SOURCING_BETA`                    | 0.3     | Recency weight |
| `SOURCING_RECENCY_TAU_HOURS`       | 24.0    | Decay half-life (~actually 1/e point, see §5) |
| `SOURCING_POOL_WINDOW_HOURS`       | 72      | Hard cutoff for candidate pool |
| `SOURCING_TOP_K`                   | 5       | Articles fed to reasoning (match prod for clean A/B) |
| `SOURCING_SHADOW_ENABLED`          | true    | Kill switch for the Celery task |

α, β, τ are tuning knobs; the defaults are conservative (favouring relevance modestly over recency). After 2-3 weeks of data, a future chantier may automate grid-search tuning on resolved signals.

## 10. Rollout & promotion gate

Rollout = deploy, enable, wait. Promotion is human, **not automatic**. Runbook `docs/runbooks/promote_signal_v2.md`:

```
When: ≥14 days of shadow traffic AND n_resolved ≥ 100 per variant

Check:
  python -m scripts.report_metrics --window 14d
Promote if ALL of:
  wilson_ci95_low("signal_v2_reranked") > wilson_ci95_high("signal")
  brier("signal_v2_reranked") < brier("signal")
  pnl_total("signal_v2_reranked") > pnl_total("signal")

Promotion = code change:
  1. signal_builder switches to ArticleRanker-backed selection (prod path)
  2. Remove the shadow task
  3. The historical "signal" variant rows stay for comparison; new signals record under a new variant name ("signal_v3" or similar)

If gate fails: leave shadow running, tune α/β/τ, revisit in another week.
```

## 11. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Celery saturation at signal peak | Task-level `rate_limit="30/m"` + `acks_late=True` |
| LLM quota/timeout for shadow | 3 retries w/ backoff; persistent failure = silent skip, measurement shows reduced `n` for v2 |
| Market embedding stale between signal time and task time | Documented; acceptable dérive. The market's question rarely changes post-creation |
| `NewsClean.embedding` NULL | Pool builder excludes these rows. If the pool is empty, task exits silently |
| α/β miscalibrated at launch | Mitigated by conservative defaults (favouring cosine ≥ recency). Worst case: v2 tracks `signal` closely, measurement shows tie, no harm |
| Explosion in LLM cost | Kill switch `SOURCING_SHADOW_ENABLED=false` + rate limit cap; expected ≤ $1–5/day at current signal volume |
| `signal_articles` bloat | ~5 rows × 2 variants × ~50 signals/day ≈ 18k rows/month. Trivially manageable |

## 12. Known limitations (explicit YAGNI)

- **No upstream change to event→market retrieval.** Hybrid search stays as-is.
- **No freshness factor in retrieval** — only in per-signal article scoring.
- **No learning loop on α/β/τ.** Manual tuning.
- **No LLM reranker.** If A/B says embedding ranker is not enough, that's a *next* chantier (cascade: embedding pre-filter → LLM fine-rank).
- **No per-tier weighting** in score. `source_weight` field is present in the pool but unused in the composite score for now — held for a future chantier once we know if it correlates with outcomes.
- **No online change** to the production reasoning output — until the promotion gate fires.

## 13. Success criteria

This chantier is done when:
1. Every new signal persisted in prod has 5 rows in `signal_articles(variant="signal")`.
2. Every new signal triggers a shadow task that (absent Celery/LLM failure) writes 5 rows in `signal_articles(variant="signal_v2_reranked")` and one `SignalPrediction` with that variant.
3. `/api/admin/metrics/variants?window=14d` returns a `signal_v2_reranked` row alongside the existing variants, with Wilson CI95, Brier, and P&L populated as signals resolve.
4. All tests green. Backfill script (from #1) accepts the new variant without modification.
5. Runbook `promote_signal_v2.md` exists with the exact gate formula.

## 14. Files inventory

**New (10)**
- `alembic/versions/021_signal_articles.py`
- `app/sourcing/__init__.py`
- `app/sourcing/article_ranker.py`
- `app/sourcing/pool_builder.py`
- `app/sourcing/prod_trace.py`
- `app/workers/tasks_sourcing.py`
- `docs/runbooks/promote_signal_v2.md`
- `tests/unit/test_article_ranker.py`
- `tests/unit/test_sourcing_pool_builder.py`
- `tests/unit/test_sourcing_prod_trace.py`
- `tests/integration/test_sourcing_shadow.py`
- `tests/integration/test_sourcing_prod_audit.py`
- `tests/integration/test_sourcing_shadow_kill_switch.py`

**Modified (4)**
- `app/db/models.py` — add `SignalArticle` ORM class
- `app/measurement/pipeline.py` — fill in `schedule_shadow_variants`
- `app/signal/signal_builder.py` — call `record_prod_signal_articles` inside `_persist_signal`
- `app/core/config.py` — 6 new settings

## 15. References

- Chantier #1 spec: `docs/superpowers/specs/2026-04-23-measurement-foundations-design.md`
- Chantier #1 plan (for patterns to reuse): `docs/superpowers/plans/2026-04-23-measurement-foundations.md`
- Current signal builder: `app/signal/signal_builder.py`
- Reasoning analyzer (LLM call): `app/llm/reasoning_analyzer.py`
- Existing retrieval (event→market): `app/retrieval/hybrid_search.py`
