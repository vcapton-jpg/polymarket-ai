# T-022 clustering fragmentation — diagnostic 2026-05-12

Read-only investigation of why **97.6 %** of events on prod 30 d are
singletons (1 article × 1 source). Performed during the v2 surveillance
window — no code change, no DB write.

## What the audit already knew

The 2026-05-10 audit flagged 97.6 % of events as singletons. Today's
data confirms this is structural, not a transient spike :

| `articles_count` | n_events (30d) | % |
|---:|---:|---:|
| **1** | **17 279** | **97.6 %** |
| 2 | 360 | 2.0 % |
| 3 | 43 | 0.2 % |
| 4-7 | 24 | 0.1 % |

| `unique_sources_count` | n_events | % |
|---:|---:|---:|
| **1** | **17 583** | **99.3 %** |
| 2 | 115 | 0.6 % |
| 3+ | 8 | <0.05 % |

| `unique_sources_count` of the event a signal came from | n_signals (30d) | % |
|---:|---:|---:|
| **1** | **725** | **98.6 %** |
| 2 | 6 | 0.8 % |
| 3+ | 4 | 0.5 % |

**Implication directe :** virtually every prod signal is built on a
single article from a single source. The `unique_sources_count`
feature in the scorer is effectively dead. The `source_tier_mix`
exposed to the LLM is `{tier_X: 1}` 99 % of the time — zero
information. Cross-source corroboration, the whole reason news-based
prediction signals are supposed to work, is absent.

## Why isn't the clustering working

Two distinct causes, both fixable.

### Cause #1 — Cosine threshold 0.75 is too strict

Pairwise cosine over 50 most-recent embedded articles within a
120-min window (1 224 pairs total):

| cosine bucket | n_pairs | % |
|---|---:|---:|
| ≥ 0.85 (very close) | 0 in sample, but observed in extended scan | — |
| 0.75-0.85 (above threshold) | 1 | **0.1 %** |
| 0.65-0.75 (near miss) | **24** | **2.0 %** |
| 0.55-0.65 (related) | 38 | 3.1 % |
| 0.40-0.55 (loose) | 19 | 1.6 % |
| < 0.40 (unrelated) | 1 143 | 93.3 % |

Top "near miss" pairs (cos = 0.749, just under the gate):

```
"IRAN: ENRICHMENT IS NON-NEGOTIABLE: IRIB"        ↔
  "IRAN SAYS ENRICHMENT IS NON-NEGOTIABLE: IRIB"        — 0 min apart

"Philippine lawmakers impeach VP Sara Duterte"    ↔
  "Philippine lawmakers to vote on impeachment of presiden..."  — 66 min apart

"TRUMP WILL TALK ABOUT WEAPONS SALES TO TAIWAN"   ↔
  "TRUMP SAYS XI PREFERS THE U.S. DOES NOT SUPPLY WEA..."   — 0 min apart

"Trump fans put millions of dollars into a gold phone"  (dup repost, 70 min apart, cos 1.000)
```

These are clearly the SAME news event being reported by different
sources / different angles. The `text-embedding-3-small` distance
between the rewrites lands at 0.65-0.749 — below the current 0.75
gate. **Lowering the threshold to 0.65 would have caught all of these**
without bringing in unrelated content (the 0.40-0.65 zone is fairly
sparse and qualitatively unrelated).

### Cause #2 — The candidate SELECT has no temporal filter and no ORDER BY

`app/workers/tasks_pipeline.py:254-265`:

```python
q = (
    select(NewsClean)
    .options(selectinload(NewsClean.news), selectinload(NewsClean.entities))
    .outerjoin(EventNewsLink)
    .where(
        EventNewsLink.id.is_(None),
        NewsClean.embedding.is_not(None),
        NewsClean.id != clean_id,
    )
)
candidates = (await session.execute(q.limit(200))).scalars().all()
```

There's a `_cutoff = datetime.now(UTC) - timedelta(minutes=120)` on
line 247 that is **computed and immediately discarded** — the
docstring acknowledges this on line 240 ("currently applied at the
per-candidate level via `is_fresh_enough`").

**Concrete failure mode :**

1. Queue accumulates >200 unlinked `news_clean` rows (typical at
   ingestion bursts — observed up to 600 unlinked in 7 d windows).
2. New article on event E arrives.
3. SQL returns 200 unlinked rows — but **with no ORDER BY**, Postgres
   returns them in physical-storage order, which on append-mostly
   tables is roughly oldest-first.
4. The actual neighbour for event E, ingested 5 min ago, is at
   position 250 in the queue and **not in the returned set**.
5. → Anchor becomes a singleton.

The Python-level `is_fresh_enough(cand_news, ...)` then *further*
filters the already-wrong 200. So the temporal contract is enforced
on the wrong sample.

## Recommended fix (T-022)

Two PRs, ordered by impact :

### T-022a — Fix the SQL candidate query (zero-cost, immediate)

```python
q = (
    select(NewsClean)
    .options(selectinload(NewsClean.news), selectinload(NewsClean.entities))
    .join(News, News.id == NewsClean.news_id)
    .outerjoin(EventNewsLink)
    .where(
        EventNewsLink.id.is_(None),
        NewsClean.embedding.is_not(None),
        NewsClean.id != clean_id,
        News.ingestion_date >= _cutoff,            # NEW: SQL-level temporal filter
    )
    .order_by(News.ingestion_date.desc())          # NEW: newest first
    .limit(200)
)
```

This addresses the most likely failure mode without touching any
threshold. Expected effect: when the unlinked queue is > 200, we now
look at the right 200 (recent neighbours) instead of the wrong 200
(stale tail). Backward-compatible : every existing candidate that
passed `is_fresh_enough` will still be in the new set, plus the ones
the bug was hiding.

### T-022b — Tune `clustering_cosine_threshold` down (gated)

`settings.clustering_cosine_threshold = 0.75 → 0.65`.

**Don't do this blind.** Ship as a setting (already is), but first run
a controlled comparison:

1. On a 7 d sample post-T-022a, replay clustering with thresholds 0.75,
   0.70, 0.65, 0.60 and count :
   - `n_events_singleton` at each threshold
   - `n_events_with_multi_source` at each threshold
   - Average `cosine` of newly-clustered pairs (qualitative)
2. Eyeball 10 random pairs at the proposed new threshold — are they
   the SAME news, or did we glue unrelated stories?
3. If singletons drop from 97.6 % to ~60-70 % AND the new pairs look
   correct, ship the threshold change behind `enable_clustering_v2`
   for 7 d, then bake in.

## Why this matters now (not in 2 weeks)

The 99.3 % singleton problem **structurally limits** every other
intervention:

- The `unique_sources_count` feature in `HeuristicScorer` is dead →
  any T-014 (LightGBM scoring) trained on it learns nothing.
- The `source_tier_mix` exposed to the LLM is `{tier_1: 1}` for 99 %
  of calls → the v2 prompt can't use it to weight cross-source agreement.
- Cross-source corroboration (the *whole point* of using news for
  prediction signals) is unavailable.

T-022a (the SQL fix) is the cheapest, lowest-risk change in the
backlog — single-file edit, no migration, immediately observable via
the same `articles_count` / `unique_sources_count` histograms above.

## Next action

When you're ready to attack T-022, **start with T-022a only.** Measure
the new histogram at H+24 against this baseline. If singletons drop
from 97.6 % to, say, 80-85 % from the SQL fix alone, the threshold
change (T-022b) may not even be needed. If they barely move, then we
know the threshold is the real bottleneck.
