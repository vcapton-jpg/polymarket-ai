# Foresight — Architecture (10,000-foot view)

> Living overview of the Foresight prediction-market intelligence platform.
> For exhaustive runtime detail, see [`BLUEPRINT.md`](../BLUEPRINT.md).
> Last refreshed: 2026-04-25.

---

## 1. What Foresight is

Foresight detects the moment a breaking news story makes a Polymarket
prediction market mispriced, then pushes a structured signal — direction,
score, urgency "life bar", reasoning, sources — to the trader before the
market corrects. Live in production at <https://getforesight.io>. Solo dev:
@vcapton-jpg (Vadim, frontend + product); Emmanuel co-dev (backend).

**Pitch:** Know before the market does — Foresight surfaces the news that
just made a Polymarket contract wrong, and lets you act on it in one click.

The product was originally branded **Signal**, briefly **Presage**, now
**Foresight**. Container names, the database name, and many module paths
still use the old `signal` slug — this is intentional and not a bug.

---

## 2. High-level flow

```
                ┌──────────────────────────────────────────┐
                │  External sources                        │
                │  RSS · X (RSSHub) · GDELT · WorldNewsAPI │
                └─────────────────────┬────────────────────┘
                                      ▼
                       ┌─────────────────────────────┐
                       │  Ingestion (Celery)          │
                       │  tasks_ingestion.py          │
                       └─────────────┬───────────────┘
                                      ▼
                  ┌─────────────────────────────────────┐
                  │  news → news_clean                   │
                  │  clean · simhash dedup · NER · embed │
                  └─────────────────────┬───────────────┘
                                        ▼
                  ┌─────────────────────────────────────┐
                  │  event_engine: cluster (cos≥0.75    │
                  │  + ≤120m) → Event row                │
                  └─────────────────────┬───────────────┘
                                        ▼
            ┌──────────────────────────────────────────────┐
            │  Hybrid retrieval (vector + BM25 + RRF       │
            │  fusion + entity boost) → top-K markets       │
            └─────────────────────┬────────────────────────┘
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  LLM impact (gpt-4o)  +  reasoning (gpt-4o-  │
            │  mini) → direction · catalyst · excerpts      │
            └─────────────────────┬────────────────────────┘
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  HeuristicScorer → strength · trade quality   │
            │  → Signal (75/25 blend) · 9 hard rejections   │
            └─────────────────────┬────────────────────────┘
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  Persist Signal · record baselines (4×)      │
            │  Schedule outcome captures @ T+5m/15m/1h/24h │
            └─────────────────────┬────────────────────────┘
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  Redis pub/sub `signal:new`                  │
            │      → FastAPI WebSocket fan-out             │
            │      → Telegram alert (high conviction)       │
            │      → Web push                               │
            └─────────────────────┬────────────────────────┘
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  React SignalCard · life-bar urgency · click │
            │      → Polymarket Builder order (gasless)    │
            └──────────────────────────────────────────────┘
```

---

## 3. Why prediction markets, why Polymarket, why Builder Program

Prediction markets are the cleanest information instrument we have: each
contract collapses a verifiable future event into a `[0, 1]` price that
moves continuously. When a wire-service article lands at T0, the market
can be slow to repriceF — that latency window is Foresight's edge. Because
the contract resolves to a known truth, every signal is back-testable
without subjectivity (`signal_outcomes.outcome_label`).

We picked **Polymarket** specifically because it is the only venue with
deep, on-chain, public liquidity across politics, geopolitics, sports,
crypto, and macro — the same buckets our news pipeline already covers. The
CLOB (Gamma + CLOB API) is open and free to read, so we can fetch
microstructure (`best_bid`, `best_ask`, `spread`, `liquidity`,
`liquidity_pct`) for every market without a paid feed.

The **Builder Program** is what makes the trade button possible without us
custodying USDC. After a one-time Gnosis Safe deployment per user
([`app/trading/safe_deployer.py`](../app/trading/safe_deployer.py)), our
builder key signs each order while the user's Safe address is supplied as
the `funder` on `OrderArgsV2` — gasless, attribution-tagged, never our
funds. Spec: [`docs/specs/2026-04-22-polymarket-wallet-link-design.md`](specs/2026-04-22-polymarket-wallet-link-design.md).

**Legal caveat (non-negotiable, see [`docs/audit/ISSUES_BACKLOG.md`](audit/ISSUES_BACKLOG.md) §0.1, §3.1).**
Polymarket has been blocked by the ANJ (French regulator) since the end of
2024. Holding a Builder Program slot does **not** confer regulatory cover
in France: it grants trading attribution on Polymarket, not a license to
intermediate bets for FR residents. A FR site that routes orders may fall
under ANJ (gambling intermediation) or AMF (PSI / CIF) jurisdiction. A
fintech-FR legal audit is open before any public launch.

---

## 4. Data sources

The ingestion layer pulls four classes of source on independent Celery
schedules and writes them all into the single `news` table with a
`source_tier` and `source_weight` snapshot for offline reproducibility.
Tiers reflect editorial trust + latency: tier 1 is an agency wire (Reuters,
AP, AFP, BBC) or a vetted X breaking-news handle, tier 2 is a syndicated
news API, tier 3 is specialist commentary. The seed list lives in
[`app/scripts/seed_sources.py`](../app/scripts/seed_sources.py) and is
mirrored to the runtime `sources_registry` table (`app/ingestion/sources_registry.py`).

| Tier | Type     | Examples                                                       | Default weight | Latency target |
|-----:|----------|----------------------------------------------------------------|---------------:|---------------:|
|    1 | RSS      | Reuters Top/Politics/World, AP Top/Politics, BBC World, AFP    | 0.85 - 1.0     | < 30 s         |
|    1 | X (RSSHub) | @Reuters, @AP, @AFP, @BBCBreaking, @sentdefender, @DeItaone, @politico, @axios, @markets, @financialtimes, @Polymarket | 0.70 - 1.0 | < 60 s |
|    2 | API      | World News API                                                 | 0.70           | < 5 min        |
|    3 | RSS      | Metaculus, Polymarket Blog                                     | 0.35           | best-effort    |

GDELT is fetched separately ([`app/ingestion/gdelt_client.py`](../app/ingestion/gdelt_client.py),
beat schedule every 5 min) for high-volume event coverage outside the
core wire feeds.

---

## 5. Pipeline components

### Ingestion — `app/ingestion/`, `app/workers/tasks_ingestion.py`
RSS poller hits every active row in `sources_registry`, deduplicates by
URL, computes `ingestion_lag_seconds = ingestion_date - publish_date`, and
inserts into `news` with the source's tier and weight snapshotted onto
the row. The X scraper consumes a JSON inbox volume
(`data/x_scraper_inbox/`) populated out-of-band by a logged-in burner
account. `worker-ingestion` runs the RSS, X and WorldNews jobs on a
dedicated queue with `--pool=solo --concurrency=1` (HTTP fan-out is the
real bottleneck, not CPU).

### Processing & dedup — `app/processing/`, `app/workers/tasks_pipeline.py::process_article`
The `news_cleaner` strips HTML and normalises whitespace. A 64-bit
**simhash** is computed for near-duplicate detection (Hamming gate
≈ 9 bits). The `ner_extractor` writes `article_entities` rows
(PERSON / ORG / GPE / EVENT). The `bucket_classifier` tags each article
(geopolitics / politics / markets / crypto / etc.). Finally
`embedding_service` writes a 1536-dim `text-embedding-3-small` vector
into `news_clean.embedding` (pgvector). Hot path runs synchronously; a
beat-scheduled batch (`compute_embedding_batch`, 120 s) backfills
stragglers.

### Event clustering — `app/event_engine/`
`SimpleClusterer` groups embedded `news_clean` rows where pairwise
cosine ≥ `clustering_cosine_threshold` (default **0.75**, see
[`simple_clusterer.py:23`](../app/event_engine/simple_clusterer.py))
**and** ingestion times within 120 min. `event_builder` then composes
`event_title`, `event_summary`, `event_retrieval_text`, and the
deduplicated `key_entities[]`. `event_counts.recompute_event_counts` keeps
`articles_count` / `unique_sources_count` truthful at write time
(audit-fixed in chantier #2; see [`scripts/clustering_diagnostic.py`](../scripts/clustering_diagnostic.py)).

### Retrieval — `app/retrieval/`
[`hybrid_search.py`](../app/retrieval/hybrid_search.py) (v1, in
production): vector top-3K via `vector_retriever` (pgvector cosine,
≥ `signal_min_cosine_score` = 0.52) is intersected with a
`BM25Index` rebuilt on the candidate set. Ranks are fused with **RRF**
(`1 / (rrf_k + rank)`, `rrf_k = 60`), then a half-point entity boost is
added per matched key entity. [`hybrid_search_v2.py`](../app/retrieval/hybrid_search_v2.py)
holds the in-flight tuning variant (chantier `2026-04-25-event-market-ranking-tuning`).

### LLM impact analysis — `app/llm/`
[`impact_analyzer.py`](../app/llm/impact_analyzer.py) calls **gpt-4o** with
[`prompts/impact_analysis_v1.txt`](../prompts/impact_analysis_v1.txt) and
returns `{impact_direction, impact_strength, confidence, ambiguity_score,
specificity_score}` as strict JSON. `reasoning_analyzer.py` then calls
**gpt-4o-mini** with [`prompts/signal_reasoning_v1.txt`](../prompts/signal_reasoning_v1.txt)
to produce the user-facing `catalyst` (≤ 120 chars), `reasoning`
(100–600 chars) and **literal substring** `article_excerpts[]` validated
client-side. Each call is logged into `llm_cost_log` with token counts
and `cost_usd`. (**Note on rule 2 of the V1 README**: the canonical
pipeline is now *two* LLM calls per event — impact + reasoning — not one.)

### Scoring — `app/scoring/`
[`heuristic_scorer.py`](../app/scoring/heuristic_scorer.py) is now a thin
orchestrator over pure helpers (chantier #5 refactor):

```
signal_strength = 0.15·freshness + 0.10·source_weight + 0.15·confirmation
                + 0.60·(0.65·impact_strength + 0.35·llm_confidence)
trade_quality   = 0.40·liquidity + 0.35·spread + 0.25·time_to_resolution
signal_score    = 0.75·signal_strength + 0.25·trade_quality
```

Knobs live in the frozen [`HeuristicWeights`](../app/scoring/weights.py)
dataclass (sum-to-1 invariant, raises on construction). Nine hard
rejection gates fire **before** scoring (cosine, spread, direction,
ambiguity, specificity, impact strength, price band, unclear direction,
72h dedup) — see BLUEPRINT.md §7.4. Audit context: heuristic v1 Brier
0.31 vs market-price baseline 0.03 is the open finding driving
[`docs/audit/heuristic_validation_report_2026-04-24.md`](audit/heuristic_validation_report_2026-04-24.md).

### Signal builder — `app/signal/signal_builder.py`
Builds the user-facing `Signal` row from features + LLM analysis +
score, with three labels (`confidence`, `urgency`, `tradability`),
`market_price_at_signal`, `source_tier_mix` (JSONB
`{tier_1: n, tier_2: n, ...}`) and `llm_model_version`. Two entry points
exist: the **fast path** invoked from `_try_instant_event_async` inside
`tasks_scoring.py` (per-event, latency-critical), and a **batch path**
called by the periodic `build_events` sweep — both end in the same
`_persist_signal` write.

### Measurement — `app/measurement/`
Every signal write is mirrored into `signal_predictions` with one row
per **variant**: the production `heuristic_v1` (frozen reference, reads
the composed `signal_score / 100` — see audit fix
[`baselines.py`](../app/measurement/baselines.py)) plus four
zero-LLM baselines:

| Variant                   | Predictor                                                   |
|---------------------------|-------------------------------------------------------------|
| `baseline_random`         | Coin flip seeded by `signal_id`                             |
| `baseline_market_price`   | Follow the market price (abstain at exactly 0.5)            |
| `baseline_momentum`       | 24h momentum sign of YES price                              |
| `baseline_news_sentiment` | Source-weighted sign of attached articles' direction labels |

Brier (`metrics.brier_from_outcome`), simulated P&L, and Wilson
95% CIs are computed at resolution time from
[`metrics.py`](../app/measurement/metrics.py) and used by
[`scripts/validate_heuristic_weights.py`](../scripts/validate_heuristic_weights.py).

### Broadcast — Redis pub/sub + WebSocket
After persistence, `_persist_signal` publishes the signal payload on the
Redis channel `signal:new` ([`tasks_scoring.py:1003`](../app/workers/tasks_scoring.py)).
[`api/websocket.py`](../app/api/websocket.py) maintains a single
async listener task per FastAPI process and fans out to every connected
WebSocket on `/ws/signals`. Telegram and Web Push fire from the same
`_persist_signal` callback for high-conviction signals.

### Outcomes tracking — `app/workers/tasks_outcomes.py`
For each new signal, four `capture_price` jobs are scheduled at
T+5m, +15m, +1h, +24h. Each capture hits the CLOB API, computes
`move_tXXX_pct`, and updates `signal_outcomes`. `catchup_outcomes`
(every 10 min) backfills stragglers; `check_resolved_markets` (every 6h)
fetches `closed=true` markets, sets `price_resolved`,
`direction_correct` (via `direction_eval.direction_matches_price_move`)
and an `outcome_label` ∈ {1, 0, NULL} on the ≥0.95 / ≤0.05 binary band.

---

## 6. Polymarket Builder Program integration

`app/polymarket/gamma_client.py` paginates the Gamma `/events` API and
flattens to `markets` rows (volume, liquidity, `clob_token_ids`, tags,
end_date). `app/polymarket/clob_client.py` enriches each market with
microstructure (`best_bid`, `best_ask`, `spread`, `last_trade_price`).

Trading uses [`py-clob-client-v2`](https://github.com/Polymarket/py-clob-client)
through [`app/trading/builder_client.py`](../app/trading/builder_client.py).
The flow is described in detail in
[`docs/specs/2026-04-22-polymarket-wallet-link-design.md`](specs/2026-04-22-polymarket-wallet-link-design.md):

1. **One-time per user.** Frontend WalletConnect → backend deploys a
   minimal Gnosis Safe proxy with the user's EOA as sole owner via
   `safe_deployer.py`. Builder wallet pays the ~$0.001 of gas. The
   `polymarket_safe_address` is persisted on `user_profiles`.
2. **Every trade.** `POST /api/trading/trade` builds a `ClobClient` with
   `key=builder_pk` (Foresight signs) and `funder=user.safe_address`
   (user's USDC settles). `OrderArgsV2.builder_code = settings.polymarket_builder_code`
   gives Polymarket the attribution. The user sees no wallet popup.

`worker-trading` then runs `poll_order_fills` (60 s) and `sync_positions`
(300 s) to materialise filled orders into the `positions` table.

---

## 7. Stack rationale

- **React 18 + TypeScript 5.6 + Vite 6** — instant HMR, ecosystem
  weight (TanStack Query 5, React Router 7, Radix UI). Strict TS catches
  shape drift between the camelCase v2 API and the
  [`types/signal.ts`](../frontend/src/types/signal.ts) domain.
- **Tailwind 3.4 + Radix UI + CVA** — design tokens for the "Cosmic
  Night" theme (obsidian palette + brand mint `#0BE0A6`), no CSS-in-JS
  runtime. WCAG AA focus rings everywhere.
- **i18next** — French primary, English fallback; default landing copy
  is FR; currency primary USD, secondary EUR.
- **FastAPI + Uvicorn** — async-first, Pydantic validation, native
  WebSocket. JWT (frontend) + API-key (B2B) middlewares share dependency
  injection with the route handlers.
- **SQLAlchemy 2.0 async + PostgreSQL 16 + pgvector** — relational rows
  and 1536-dim embeddings live in the same store; HNSW indexes on
  `markets.embedding`, `markets.embedding_v2`, and `news_clean.embedding`.
- **Celery + Redis** — six dedicated queues isolate failure modes
  (markets API outage cannot block ingestion). Beat owns schedules.
- **Alembic** — schema as code, currently **25 migrations**
  (`alembic/versions/001_initial_schema.py` → `025_rename_signal_variant_to_heuristic_v1.py`).
- **OpenAI gpt-4o + gpt-4o-mini + text-embedding-3-small** — sole LLM
  provider. Cost is policed via `llm_cost_log`. No fallback provider yet
  (open ticket, [`ISSUES_BACKLOG.md`](audit/ISSUES_BACKLOG.md) §2.2).
- **Telegram bot** — `app/telegram/` pushes entry/exit alerts using a
  long-lived bot token; webhook endpoint at `/api/telegram`.
- **Wagmi 2 + Viem 2** — Polygon wallet connect on the frontend; the
  backend signs all CLOB orders, so this is purely a one-time Safe-setup
  flow.

---

## 8. Database overview

Source of truth: [`app/db/models.py`](../app/db/models.py)
(31 ORM classes, 30 tables — full column lists in BLUEPRINT.md §5).

| Domain               | Table(s) | Stores |
|----------------------|----------|--------|
| Source registry      | `sources_registry` | One row per RSS / X / API source with tier + weight |
| Ingestion            | `news` | Raw article (URL-unique) with snapshotted `source_tier` / `source_weight` / lag |
| Processing           | `news_clean`, `article_entities` | Cleaned text, simhash, bucket, NER, 1536-dim embedding |
| Markets              | `markets` | Polymarket conditions: question, microstructure, `clob_token_ids`, embedding |
| Events               | `events`, `event_news_links` | News clusters and N-N membership w/ excerpts + relevance |
| Retrieval candidates | `event_market_candidates`, `event_market_features`, `event_market_ranking_shadow` | Top-K markets per event w/ RRF/cosine/BM25 scores; normalised features; shadow-rank experiments |
| LLM analysis         | `event_market_analysis`, `llm_cost_log` | Impact/reasoning JSON + per-call token cost |
| Signals              | `signals`, `signal_articles`, `signal_outcomes`, `signal_predictions`, `signals_pending_reasoning` | Final signal, attached articles, T+X price moves, per-variant predictions, reasoning backfill queue |
| Users                | `user_profiles`, `user_limits`, `onboarding_progress`, `quiz_attempts` | Profile + onboarding state + Learn & Trade limits |
| Trading              | `portfolios`, `positions`, `orders`, `paper_positions` | Real and paper-trading positions / orders |
| Outcomes view        | `outcome_views` | Materialised outcome aggregations for the admin dashboard |
| Agents & ops         | `agent_activities`, `daily_briefs`, `gdelt_events_raw` | Internal agent runs, generated briefs, raw GDELT inbox |
| Subscriptions / B2B  | `api_keys_b2b` | API keys, plan, usage. Stripe state lives on `user_profiles` |

---

## 9. Service topology

`docker-compose.yml` declares **12 services + 2 volumes**, all on the
default bridge network.

| Service             | Image                       | Role                                                | Port             |
|---------------------|-----------------------------|-----------------------------------------------------|------------------|
| `db`                | `pgvector/pgvector:pg16`    | PostgreSQL + pgvector (`max_connections=200`)       | 5435 → 5432      |
| `redis`             | `redis:7-alpine`            | Celery broker, cache, pub/sub                       | 6379             |
| `rsshub`            | `diygod/rsshub:latest`      | RSS proxy for X feeds, Redis-backed cache (db 5)    | 1200             |
| `app`               | local Dockerfile            | FastAPI + Uvicorn `--reload`, runs Alembic on boot  | 8001 → 8000      |
| `beat`              | local                       | Celery Beat scheduler                               | —                |
| `worker-ingestion`  | local                       | Queue `ingestion` (RSS, X inbox, WorldNews, GDELT)  | —                |
| `worker-pipeline`   | local (replicas: 2)         | Queue `pipeline` (clean, NER, embed, build_events)  | —                |
| `worker-scoring`    | local                       | Queue `scoring` (hybrid search, LLM, signal builder) | —                |
| `worker-markets`    | local                       | Queue `markets` (Gamma + CLOB, isolated)            | —                |
| `worker-outcomes`   | local                       | Queue `default` (price captures, resolutions)       | —                |
| `worker-trading`    | local                       | Queue `trading` (orders, sync, risk, briefs)        | —                |
| `frontend`          | local Dockerfile (Vite)     | Production-built SPA served by nginx                | 3000 → 80        |

Healthchecks on `db`, `redis`, `app`. Volumes: `postgres_data`,
`redis_data`. Production at <https://getforesight.io> mirrors this
topology with managed Postgres + Redis and pinned worker counts.

---

## 10. What's NOT in scope yet

These are filed in [`docs/audit/ISSUES_BACKLOG.md`](audit/ISSUES_BACKLOG.md)
and tracked in `docs/specs/`. Do not infer them from this
diagram; they are deliberately deferred.

- **ML retraining of the heuristic.** A LightGBM `signal_score_v2` is
  blocked until 1000 labeled signals + per-direction stratified
  evaluation. Tuner script and gate already exist
  ([`scripts/tune_heuristic_weights.py`](../scripts/tune_heuristic_weights.py),
  [`docs/runbooks/promote_heuristic_candidate.md`](runbooks/promote_heuristic_candidate.md))
  but no candidate has cleared the gate.
- **Mobile app.** No native client; PWA install is the current path.
- **Multi-market sourcing.** Polymarket only — no Kalshi, no Manifold,
  no Metaculus prediction integration on the trading side (Metaculus
  RSS is consumed for news only).
- **Multi-LLM consensus / shadow bias experiments.** Chantier #4
  (Claude Haiku + Mistral parallel runs) blocked behind the J+10
  measurement gate. Pure-OpenAI for now.
- **Feature flags / A/B framework.** Only environment-variable overrides
  (`HEURISTIC_SHADOW_ENABLED`, `HEURISTIC_W_*`).
- **WebSocket horizontal scaling.** `/ws/signals` is mono-pod; the Redis
  pub/sub is in place but the frontend has no reconnect-with-resume on
  multi-pod failover.
- **CGU / mentions légales / age gate / cooling-off.** Required before
  any FR public launch — see ISSUES_BACKLOG §3.2 and §3.3.

---

**Maintainer:** @vcapton-jpg · **Last update:** 2026-04-25
