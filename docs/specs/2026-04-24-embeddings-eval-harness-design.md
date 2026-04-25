# Embedding Quality — Eval Harness + Composition Shadows — Design Spec

**Chantier #3 of the "backend signals optimization" initiative.**
Follows chantier #1 (measurement foundations) and chantier #2 (signal sourcing & traceability). Assumes `signal_predictions`, variant registry, and the shadow-variant pattern established in those chantiers are already live. This spec adds a new capability at a layer below them: making embedding quality itself measurable, and landing a first wave of targeted composition improvements behind that harness.

## 1. Goal

Make every future change to the embedding layer **measurable** rather than vibes-based, and ship a first wave of three composition improvements that exercise the harness end-to-end.

Two concrete outcomes, delivered as two sequential phases of a single chantier:

**Phase 1 — Eval harness (C)**
A runnable offline benchmark that, given a variant (`v1` or `v2`) and a surface (`news` / `market` / `event` / `all`), computes retrieval quality metrics against a held-out labeled set, and emits a reproducible JSON report. A baseline of the current state (`v1`) is frozen in git; every future candidate is compared against it.

**Phase 2 — Three targeted composition shadows (A1 / A3 / A4)**
Each shadow runs side-by-side with production (new column `embedding_v2`, written in parallel by the pipeline and by a backfill task, never replaces `embedding`). Each is gated by the harness before a `embeddings_variant_<surface>` feature flag is flipped in production.

## 2. Non-goals

- No model upgrade (`text-embedding-3-small → text-embedding-3-large`). Requires `VECTOR(1536) → VECTOR(3072)` migration + 2× API cost; its own future chantier.
- No LLM-based summarization before embedding. Latency and cost too high for a first iteration.
- No fine-tuning, multi-vector per entity, query expansion, or cross-encoder reranker.
- No automatic promotion — the gate is manual, informed by harness JSON.
- No refactor of existing consumers (`hybrid_search`, `simple_clusterer`, `article_ranker`, `vector_retriever`) beyond adding a single read-side helper that routes by variant flag.
- No changes to the measurement layer (chantier #1) or the sourcing ranker (chantier #2). The embedding flag flip is transparent to both.

## 3. Architecture

### 3.1 The two-phase chantier

```
Phase 1 — Harness (tasks 1-7)
 ├─ Migration 022: NewsClean / Market / Event get
 │    - embedding_v2        VECTOR(1536) NULL
 │    - embedding_v2_composition  TEXT NULL
 │    - embedding_v2_computed_at  TIMESTAMPTZ NULL
 ├─ app/eval/labels.py    — pair loaders (3 sources)
 ├─ app/eval/metrics.py   — retrieval@k, nDCG@10, cluster purity, bootstrap
 ├─ app/eval/runner.py    — orchestration + EvalReport
 ├─ scripts/eval_embeddings.py — CLI
 └─ docs/eval_baselines/embeddings_2026-04-24_v1.json   ← frozen baseline

Phase 2 — Shadows (tasks 8-17)
 ├─ app/processing/text_composers.py  — v1 + v2 for news, market, event
 ├─ Migration of 3 call-sites to compose_event_v1() (A4 dette remboursée)
 ├─ app/workers/tasks_embeddings_backfill.py — recompute_embedding_v2(surface)
 ├─ Inline v2 write in tasks_pipeline / tasks_ingestion / event_builder
 ├─ app/processing/embedding_reader.py — get_active_embedding(row, surface) + active_column_name(surface)
 ├─ 4 consumer migrations:
 │    - hybrid_search_markets, simple_clusterer, article_ranker (chantier #2) → get_active_embedding(row, surface)
 │    - vector_retriever.search_markets_by_embedding → active_column_name("market") templated into the raw SQL
 ├─ Migration 023 (conditional, before market promotion): HNSW index on Market.embedding_v2
 └─ docs/runbooks/promote_embeddings_v2.md   ← 3-check gate, per surface
```

### 3.2 Data flow — production writes

Unchanged for `embedding` (v1). A new parallel write path populates `embedding_v2`:

```
create NewsClean:
  text_v1 = compose_news_v1(title, clean_text).text
  embedding = await embed(text_v1)                          ← existing path
  text_v2 = compose_news_v2(title, clean_text).text
  embedding_v2 = await embed(text_v2)                       ← NEW (best-effort)
  embedding_v2_composition = "news_v2_lead_tail"            ← NEW
```

If `embed(text_v2)` raises or returns None, `embedding_v2` stays `NULL` — the backfill task rescues it later. v2 failure never blocks the signal pipeline.

### 3.3 Data flow — consumer reads

Embedding consumers route through helpers in `app/processing/embedding_reader.py`. Two variants depending on whether the consumer holds an ORM row or writes raw SQL:

```python
# ORM consumers (hybrid_search_markets, simple_clusterer, article_ranker):
def get_active_embedding(row, surface: str) -> list[float] | None:
    variant = getattr(get_settings(), f"embeddings_variant_{surface}")
    return row.embedding if variant == "v1" else row.embedding_v2

# Raw-SQL consumers (vector_retriever.search_markets_by_embedding):
def active_column_name(surface: str) -> str:
    """Returns 'embedding' or 'embedding_v2' depending on the active variant.
    Only 'market' / 'event' / 'news' are valid — raises otherwise."""
    variant = getattr(get_settings(), f"embeddings_variant_{surface}")
    return "embedding" if variant == "v1" else "embedding_v2"
```

`vector_retriever` builds its KNN query by interpolating `active_column_name("market")` into the f-string at call time. Since it's a fixed whitelist of column names, this is safe against SQL injection and keeps the flag-flip rollback story intact.

Promotion = flip `embeddings_variant_news`/`_market`/`_event` in `.env` and redeploy workers. Rollback = flip back. No data migration, no recompute: v1 stays in `embedding`, v2 in `embedding_v2`, both populated in parallel indefinitely.

**Market surface has one additional pre-condition before its flip**: migration 023 must have added an HNSW index on `Market.embedding_v2`, otherwise `vector_retriever`'s KNN query against `embedding_v2` does a sequential scan and market retrieval latency blows up. News and Event surfaces have no such constraint because their consumers are all exact-cosine-on-bounded-pool, not KNN.

### 3.4 Data flow — harness (offline, manual)

```
eval_embeddings --variant v1 --surface news
  → labels.load_pairs(session, surface="news")
    ↳ _load_db_heuristic   (from event_news_links, etc.)
    ↳ _load_downstream_pnl (from signal_outcomes — only event_to_market)
    ↳ _load_llm_judge      (cached in .eval_cache/)
    ↳ dedup by (query_id, target_id), noblest source wins
  → for each pair:
      fetch candidate pool (same shaping as the prod consumer)
      score: cosine(query_embedding, candidate_embedding_vN)
      rank descending
      compute retrieval@k / nDCG@k against relevant_ids
  → aggregate → EvalReport → JSON to stdout or --out
```

## 4. Eval harness

### 4.1 `app/eval/labels.py`

```python
@dataclass(frozen=True)
class EvalPair:
    query_id: int | str
    relevant_ids: set[int | str]
    source: str          # "db_heuristic" | "downstream_pnl" | "llm_judge"
    surface: str         # "event_to_market" | "article_to_event" | "market_to_article"

async def load_pairs(session, *, surface: str, limit: int = 500) -> list[EvalPair]:
    ...
```

**Source 1 — DB heuristic** (SQL, no I/O outside DB):
- `event_to_market`: `event_market_candidates JOIN event_market_analysis` where `rank ≤ 3 AND impact_strength IS NOT NULL`. Positive: the analyzed top-3 candidates per event.
- `article_to_event`: `event_news_links WHERE role = 'primary'`.
- `market_to_article`: `signal_articles WHERE variant = 'signal' AND rank ≤ 5` (chantier #2 audit trail).

**Source 2 — Downstream P&L validation** (only `event_to_market`):
- `SELECT event_id, market_id FROM signals s JOIN signal_predictions p ON p.signal_id = s.id JOIN signal_outcomes o ON o.signal_id = s.id WHERE p.variant = 'signal' AND o.correct = TRUE AND o.pnl > 0`.
- Positive pairs validated by production outcomes — not tainted by the embedding we're evaluating.

**Source 3 — LLM judge** (uses `gpt-4o-mini`, cached):
- Sample `n ≈ 200` candidate pairs per surface (heuristic positives + random negatives, 50/50).
- Prompt: `"Is this <article> topically relevant to this <event>? Answer 'yes', 'no', or 'unclear'."`
- Cache keyed by `sha256(prompt + pair_key)` in `.eval_cache/llm_judge_<surface>.json`. Second call = 0 API cost.
- Budget hard-capped at `LLM_JUDGE_MAX_USD=10.0`; tracked via existing `llm_cost_log`.
- Result `"yes"` → positive pair, everything else dropped.

**Dedup**: same `(query_id, target_id)` across sources → keep one, prefer `downstream_pnl > llm_judge > db_heuristic`. Track the winning `source` on `EvalPair` for per-source stratification in metrics.

### 4.2 `app/eval/metrics.py`

Pure functions, no I/O, numpy-only:

```python
def retrieval_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """|relevant ∩ ranked[:k]| / min(k, |relevant|). Returns 0.0 if relevant is empty."""

def ndcg_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """Standard nDCG with binary relevance. Returns 0.0 if relevant is empty."""

def cluster_purity(clusters: dict[int, list[int]], ground_truth: dict[int, int]) -> float:
    """For article↔event: fraction of items in a cluster sharing the majority ground-truth label."""

def bootstrap_ci(values: list[float], *, n_resamples: int = 1000, alpha: float = 0.05) -> tuple[float, float, float]:
    """Returns (mean, ci_low, ci_high) with percentile method. Deterministic via seed."""

def aggregate(per_pair_scores: list[dict], strata: tuple[str, ...] = ("source",)) -> dict:
    """Input: [{'retrieval@5': 0.8, 'ndcg@10': 0.7, 'source': 'db_heuristic'}, ...]
       Output: {'retrieval@5': {'mean': ..., 'ci_low': ..., 'ci_high': ..., 'n': ...},
                'per_source': {'db_heuristic': {...}, ...}}"""
```

Edge cases covered by tests: empty `relevant_ids`, empty `ranked_ids`, `k=0`, `k > len(ranked)`, duplicates in `ranked_ids`, single-pair stratum.

### 4.3 `app/eval/runner.py`

```python
@dataclass
class EvalReport:
    variant: str
    surface: str
    metrics: dict[str, dict]   # {"retrieval@5": {"mean": ..., "ci_low": ..., ...}, ...}
    per_source: dict[str, dict]
    generated_at: datetime
    git_sha: str
    n_pairs: int
    n_skipped: int             # pairs where embedding_v2 was NULL (only for variant="v2")

async def run_eval(session, *, variant: str, surface: str) -> EvalReport: ...

def report_to_json(report: EvalReport) -> str: ...
def diff_reports(baseline: EvalReport, candidate: EvalReport) -> dict: ...
```

For each pair, the runner:
1. Reads the query entity's embedding for `variant` (skip if None).
2. Fetches the candidate pool using the same shaping as the prod consumer (e.g. for `event_to_market`: all active markets in the same `bucket` ±60 days; for `article_to_event`: events in ±72h).
3. Scores via cosine similarity.
4. Ranks descending.
5. Computes `retrieval@5`, `retrieval@10`, `nDCG@10` vs `relevant_ids`.

### 4.4 CLI `scripts/eval_embeddings.py`

```
usage: eval_embeddings.py [--variant v1|v2] [--surface news|market|event|all]
                          [--out PATH.json] [--baseline PATH.json]

Modes:
  baseline mode (no --baseline):
      prints the EvalReport JSON for one variant/surface to stdout or --out.
  diff mode (--baseline given):
      loads the baseline JSON, runs the current variant, emits a per-metric delta
      report with pass/fail verdicts against the gate rules from §7.
```

### 4.5 Baseline storage

The first invocation against v1 produces `docs/eval_baselines/embeddings_2026-04-24_v1.json`. This file is **committed to git** and never regenerated: it is the immutable reference for every future v2 comparison, regardless of when the v2 ships.

## 5. Text composers (phase 2)

All live in `app/processing/text_composers.py`. Shared contract:

```python
@dataclass(frozen=True)
class ComposedText:
    text: str
    composition_version: str    # e.g. "news_v1_title_trunc", "news_v2_lead_tail"
```

### 5.1 v1 composers (fidelity re-implementation)

`compose_news_v1`, `compose_market_v1`, `compose_event_v1` produce **bit-identical output** to the current inline f-strings they replace. This is enforced by tests that pin the exact output on representative inputs. Their only purpose is to (a) stop the divergence (A4 pain: 3 event-composer sites) by centralizing the formula, and (b) provide a symmetric API for v2 to plug into.

Call-sites migrated to v1 helpers (no behavior change):
- `app/workers/tasks_pipeline.py:98` (news inline embed) → `compose_news_v1`
- `app/workers/tasks_ingestion.py::_build_retrieval_text` → `compose_market_v1`
- `app/event_engine/event_builder.py:56-58` → `compose_event_v1`
- `app/workers/tasks_pipeline.py:271, 316-319, 513-516` → `compose_event_v1`

### 5.2 A1 — `compose_news_v2`

```python
def compose_news_v2(title: str, clean_text: str) -> ComposedText:
    """Title + lead paragraph + tail paragraph, capped at 1800 chars.
    Falls back to v1-like truncation when no paragraph structure is present."""
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if len(p.strip()) >= 80]
    if not paragraphs:
        body = clean_text[:1500]
    elif len(paragraphs) == 1:
        body = paragraphs[0][:1500]
    else:
        lead = paragraphs[0][:1200]
        tail = paragraphs[-1][:400]
        body = f"{lead}\n\n{tail}"
    text = f"{title.strip()}. {body}"[:1800]
    return ComposedText(text=text, composition_version="news_v2_lead_tail")
```

Hypothesis: articles longer than ~1500 chars frequently contain their lede (what/who/when) at the top and their implication/takeaway in the last paragraph. Blind truncation at `[:1500]` discards the tail. 1800-char cap remains well under `text-embedding-3-small`'s 8192-token window.

### 5.3 A3 — `compose_market_v2`

```python
def compose_market_v2(mkt: dict) -> ComposedText:
    question = (mkt.get("question") or "").strip()
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    category = (mkt.get("category") or "").strip()
    tags_str = " ".join(mkt.get("tags") or [])
    parts = [f"{question}.", desc_clean]
    if category:
        parts.append(f"[category: {category}]")
    if tags_str:
        parts.append(tags_str)
    text = " ".join(p for p in parts if p).strip()
    return ComposedText(text=text, composition_version="market_v2_with_category")
```

Only change vs v1: inject `[category: {category}]` between description and tags. Bracket format is intentional — the embedder treats it as a structural cue rather than free text. No change to truncation or boilerplate cleanup.

### 5.4 A4 — `compose_event_v2`

```python
def compose_event_v2(title: str, summary: str, entities: list[str], bucket: str | None) -> ComposedText:
    parts = []
    if bucket:
        parts.append(f"[{bucket}]")
    parts.append(title.strip())
    if summary:
        parts.append(summary.strip()[:400])
    if entities:
        parts.extend(entities[:5])
    text = " ".join(p for p in parts if p).strip()
    return ComposedText(text=text, composition_version="event_v2_bucket_prefix")
```

Two changes vs v1: (1) optional `[{bucket}]` prefix to anchor the embedding in the domain (geopolitics / politics / crypto / sports / …); (2) unified summary truncation at `[:400]` across all formerly-divergent call-sites (was `[:300]` in one site, `[:400]` elsewhere).

### 5.5 Backfill — `app/workers/tasks_embeddings_backfill.py`

```python
@celery_app.task(
    name="app.workers.tasks_embeddings_backfill.recompute_embedding_v2",
    bind=True,
    rate_limit="60/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,   # addresses IMPORTANT finding #1 from chantier #2 review
)
def recompute_embedding_v2(self, *, surface: str, batch_size: int = 100) -> dict:
    """Process one batch of rows where embedding_v2 IS NULL.

    Returns {'processed': int, 'remaining': int, 'est_cost_usd': float}.
    Idempotent: never touches a row where embedding_v2 IS NOT NULL.
    """
```

Invoked **manually** (never on beat schedule) after each v2 composer lands. Picks up stragglers that missed the inline-write path (failures, pre-existing rows). Per-surface dispatch so the three variants are independent. Total estimated backfill cost at current DB size:

| Surface | Row count (est.) | Tokens/row | Total tokens | Cost @ $0.02/1M |
|---------|------------------|------------|--------------|-----------------|
| news    | ~15,000          | ~500       | 7.5M         | $0.15           |
| market  | ~3,000           | ~100       | 0.3M         | $0.006          |
| event   | ~2,000           | ~100       | 0.2M         | $0.004          |

Total first-time backfill: **< $0.20**. Negligible. Re-backfills (if we iterate on v2 during chantier) stay equally cheap.

### 5.6 Inline v2 writes in new pipelines

Three call-sites that create new rows also write `embedding_v2` inline:

```python
# tasks_pipeline._process_article_async  (after existing embedding line)
v2_text = compose_news_v2(raw_title, clean_text).text
v2_emb = await get_embedding(v2_text)  # best-effort; None allowed
news_clean.embedding_v2 = v2_emb
news_clean.embedding_v2_composition = "news_v2_lead_tail" if v2_emb else None
news_clean.embedding_v2_computed_at = now if v2_emb else None
```

Same pattern for markets (in `tasks_ingestion._compute_market_embeddings` and the initial market creation path) and events (in `event_builder.build_event`). v2 failures are logged and swallowed — the backfill catches them.

## 6. Database schema

### 6.1 Migration 022 — `add_embedding_v2_columns`

```python
def upgrade():
    for table in ("news_clean", "markets", "events"):
        op.add_column(table, sa.Column("embedding_v2", Vector(1536), nullable=True))
        op.add_column(table, sa.Column("embedding_v2_composition", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("embedding_v2_computed_at",
                                       sa.DateTime(timezone=True), nullable=True))

def downgrade():
    for table in ("news_clean", "markets", "events"):
        op.drop_column(table, "embedding_v2_computed_at")
        op.drop_column(table, "embedding_v2_composition")
        op.drop_column(table, "embedding_v2")
```

No index on `embedding_v2` in migration 022. The harness does exact cosine on a bounded pool, not KNN, so it doesn't need one.

### 6.2 Migration 023 — `add_hnsw_index_on_market_embedding_v2` (conditional)

Executed **only if** the market surface v2 passes the harness gate. Required before flipping `embeddings_variant_market="v2"` because `vector_retriever.search_markets_by_embedding` does a pgvector KNN query. Without an index, a sequential scan replaces the existing HNSW lookup and market retrieval latency blows up from ~5ms to hundreds.

```python
def upgrade():
    op.execute(
        "CREATE INDEX CONCURRENTLY idx_markets_embedding_v2_hnsw "
        "ON markets USING hnsw (embedding_v2 vector_cosine_ops)"
    )

def downgrade():
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_markets_embedding_v2_hnsw")
```

News and Event surfaces need no equivalent — their consumers read exact-cosine on bounded pools (pool_builder's 72h window, clusterer's ±120m window), not KNN against the full table.

### 6.3 ORM additions

Three columns added to each of `NewsClean`, `Market`, `Event`. No new tables, no new relationships.

## 7. Promotion gate + rollout

See `docs/runbooks/promote_embeddings_v2.md` (written as part of the plan).

### 7.1 Three checks — all must pass, per surface

| # | Check | Pass condition |
|---|-------|----------------|
| 1 | Statistical confidence | `retrieval@5(v2).ci_low > retrieval@5(v1).ci_high` (bootstrap 1000 resamples, 95% CI) |
| 2 | Ranking quality | `nDCG@10(v2) > nDCG@10(v1)` (absolute delta) |
| 3 | Cross-source consistency | `retrieval@5(v2) > retrieval@5(v1)` stratified on each source (`db_heuristic`, `downstream_pnl`, `llm_judge`) independently |

Each surface (news / market / event) is promoted independently — their composers are orthogonal.

### 7.2 Pre-conditions

- `SELECT COUNT(*) WHERE embedding_v2 IS NULL` ≤ 5% of each surface's row count (backfill effectively complete).
- `n_pairs` per label source ≥ 30 (smaller strata produce noisy CI and trivially-passing checks).
- `composition_version` uniform within a surface (no mixed variants in-column).

### 7.3 Feature flag settings

Three new settings in `app/core/config.py`:

```python
class Settings(BaseSettings):
    ...
    embeddings_variant_news: Literal["v1", "v2"] = Field(default="v1")
    embeddings_variant_market: Literal["v1", "v2"] = Field(default="v1")
    embeddings_variant_event: Literal["v1", "v2"] = Field(default="v1")
```

Promotion = edit `.env` and redeploy workers listening on the `scoring` and `pipeline` queues. No DB migration, no backfill inversion.

### 7.4 Rollout order (per surface)

1. Composer v2 lands + backfill task added + inline write path added.
2. `recompute_embedding_v2(surface=<name>)` run until `embedding_v2 IS NULL` count ≤ 5%.
3. `scripts/eval_embeddings.py --variant v2 --surface <name> --baseline docs/eval_baselines/embeddings_2026-04-24_v1.json`.
4. If the 3 checks pass **and** `<name> == "market"`: apply migration 023 (HNSW index on `market.embedding_v2`). For `news` / `event`, skip this step.
5. Flip `embeddings_variant_<name>="v2"` in `.env`, redeploy the `scoring` and `pipeline` queue workers.
6. Monitor 7 days via chantier #1 dashboard: signal volume, Brier, P&L. No regression → promotion holds.

### 7.5 Rollback

Single action: flip `embeddings_variant_<surface>=v1` and redeploy. Takes < 5 minutes. `embedding` column untouched, no recompute needed.

If rollback triggers, produce a post-mortem documenting the gap between harness verdict and production outcome. A harness/prod divergence indicates a missing pair type in the label set — update `labels.py` before the next candidate.

## 8. Testing strategy

| Module | Level | Coverage |
|--------|-------|----------|
| `text_composers.py` | Unit | Bit-exact v1 regression ; v2 branch coverage (paragraph structure, truncation edges, empty inputs, special characters) |
| `eval/labels.py` | Unit + integration | DB-heuristic loaders on small fixtures ; dedup logic across sources ; LLM judge with `monkeypatch`-ed analyzer and canned responses |
| `eval/metrics.py` | Unit | Retrieval@k / nDCG@10 against hand-computed values ; bootstrap determinism via seed ; degenerate inputs (empty `relevant_ids`, `k=0`, duplicates) |
| `eval/runner.py` | Integration | End-to-end on a tiny DB fixture (3 events, 5 markets, 10 articles, 8 labeled pairs, toy embeddings) |
| `scripts/eval_embeddings.py` | Smoke | One subprocess invocation with `--out`, check exit 0 + JSON parsable |
| `tasks_embeddings_backfill.py` | Integration | Celery eager ; idempotence ; partial-crash transaction semantics (batch 1 committed, batch 2 rolled back) ; rate-limit decorator present |
| `embedding_reader.py::get_active_embedding` | Unit | Flag v1/v2 routing ; `None` when active column is `None` (no silent fallback) ; invalid surface raises |

**~35-45 new tests total.** All < 100ms except DB-integration ones (≤ 2s each). No new external services.

**Regression tests already in place, preserved:**
- Chantier #1 + #2 integration tests must all still pass after `compose_*_v1` replaces inline f-strings.
- `test_article_ranker.py` unchanged — ranker still reads `market.embedding` (via `get_active_embedding` after task 14).

## 9. Failure modes & edge cases

Enumerated exhaustively so the plan has tests for each:

1. **News without paragraph structure** (no `\n\n`) → fallback to `clean_text[:1500]`, no crash.
2. **News with single long paragraph** → lead = full paragraph truncated at 1200, tail = empty string (join skips it).
3. **Market without `category`** → no bracket in v2 output, nearly identical to v1.
4. **Event without `bucket`** → no bracket prefix, no `"[] title …"` output.
5. **Pair count < 30 on a source** → `run_eval` logs warning, skips that source's stratum, does not crash.
6. **Row in eval set with `embedding_v2 IS NULL`** → runner skips the pair, increments `n_skipped`, logs it. Not counted in any denominator.
7. **LLM judge cache hit** → second invocation with same `(prompt, pair_key)` hash makes zero OpenAI calls.
8. **Backfill task crash mid-batch** → async session rollback scoped to the crashed batch ; prior committed batches are durable.
9. **Variant flag flip during a concurrent signal** → `get_active_embedding` is read per-consumption, so a flip mid-signal causes at worst a v1/v2 mix across stages (millisecond-order, acceptable).
10. **Embedding service returns None for v2** → `embedding_v2 = NULL`, backfill rescues later. Never raises.

## 10. Open questions / future chantiers

- **Model upgrade** (`3-small → 3-large`, 3072-dim) is the natural follow-up once composition is optimized — the harness is already dimension-agnostic, so a future migration `embedding_v3 VECTOR(3072)` follows the same shadow pattern.
- **Per-field multi-vector** (separate embeddings for question, description, tags on markets) is a bigger architectural lift ; capitalize for chantier #4 or #5 depending on what the baseline reveals.
- **Cluster purity** on news↔events is defined in `metrics.py` but only consumed by chantier #4 (clustering) — shipped here pre-emptively since the math is cheap and reusable.
- **Admin endpoint for harness results** is out of scope. Running the CLI + reading the JSON is enough for a solo operator ; a dashboard is YAGNI until we have ≥ 3 eval baselines over time.

## 11. Acceptance criteria

- [ ] Migration 022 applies cleanly up and down.
- [ ] Migration 023 applies cleanly up and down (independent of 022 promotion state).
- [ ] `compose_*_v1` reproduce inline f-strings bit-exactly (tests pinned).
- [ ] All 4 call-sites of event composition converge on `compose_event_v1`.
- [ ] `scripts/eval_embeddings.py --variant v1 --surface all` runs end-to-end on the prod DB, writes `docs/eval_baselines/embeddings_2026-04-24_v1.json`, exit 0.
- [ ] Every new row (`NewsClean`, `Market`, `Event`) has `embedding` AND `embedding_v2` populated within 1 minute of creation (best-effort for v2).
- [ ] `recompute_embedding_v2(surface="news")` drains v2-NULL rows to ≤ 5%.
- [ ] `get_active_embedding(row, "news")` returns `row.embedding` when flag is `"v1"` and `row.embedding_v2` when flag is `"v2"`.
- [ ] `active_column_name("market")` returns the literal `"embedding"` or `"embedding_v2"` depending on flag, and `vector_retriever` interpolates it safely.
- [ ] Runbook `docs/runbooks/promote_embeddings_v2.md` documents the 3-check gate per surface.
- [ ] All 171+ existing backend tests still pass ; ~40 new tests added and passing.

---

*End of spec. Next step: implementation plan in `docs/plans/2026-04-24-embeddings-eval-harness.md`.*
