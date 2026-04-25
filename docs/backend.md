# Foresight Backend Guide

Reader profile: Python + FastAPI + Postgres dev, first day on the codebase.

## 1. Where the backend lives

The Python backend lives in **`/app`**, not `/backend`. The folder name is a holdover from the original FastAPI scaffold (the package is mounted at `/app` inside the Docker image, see `docker-compose.yml:76`). Renaming it would break ~3000+ `from app.…` imports, the `Dockerfile`, every Celery task path string, and `alembic.ini`'s `script_location`, for zero functional benefit. Treat `/app` as "the backend" everywhere in this doc.

There is no separate `/backend` directory. The repo root contains `app/`, `alembic/`, `tests/`, `prompts/`, `docs/`, `frontend/`, `scripts/`.

## 2. Stack

Verified against `pyproject.toml` and live code.

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11 (`requires-python = ">=3.11,<3.14"`) | |
| Web framework | FastAPI ≥ 0.115 + uvicorn ≥ 0.32 | Single entry: `app/api/main.py` |
| ORM | SQLAlchemy 2.0 async + asyncpg ≥ 0.30 | `psycopg[binary,pool]` also installed for sync path used by Alembic |
| Migrations | Alembic ≥ 1.15 | 25 migrations, `alembic/versions/001_*` → `025_*` |
| Database | Postgres 16 + pgvector | Image `pgvector/pgvector:pg16`, db name `signal`, port `5435` (host) → `5432` (container) |
| Task queue | Celery ≥ 5.4 + Redis ≥ 5.2 | Redis serves both broker and result backend |
| LLM | OpenAI ≥ 1.50, default `gpt-4o-mini` (`openai_llm_model`); embeddings default `text-embedding-3-small` (1536 dims) | The brief mentioned `text-embedding-3-large` — not in use; the `news_clean.embedding`/`embedding_v2` columns are `VECTOR(1536)` |
| Validation | Pydantic v2 + `pydantic-settings` | Schemas in `app/api/schemas/` and `app/api/schemas_v2.py` |
| Tests | pytest ≥ 9 + pytest-asyncio ≥ 1.3 (`asyncio_mode = "auto"`) | |
| Package manager | `uv` | All make targets call `uv sync` / `uv run …` |
| Other | `httpx`, `tenacity`, `feedparser`, `beautifulsoup4`, `simhash`, `rank-bm25`, `spacy` (model `en_core_web_lg`), `playwright`, `py_clob_client_v2`, `web3`, `eth-account`, `python-telegram-bot`, `stripe`, `python-jose[cryptography]`, `bcrypt`, `pywebpush`, `google-auth` | |

## 3. Setup

```bash
# 1. Install Python deps + spaCy model (~600 MB)
make install                   # alias for: uv sync && uv run python -m spacy download en_core_web_lg

# 2. Bring up the full stack (db + redis + rsshub + app + 6 workers + beat + frontend)
make dev                       # docker compose up -d

# 3. Or run the API only, against dockerised db/redis
make dev-local                 # uvicorn app.api.main:app --reload on :8000

# 4. Apply migrations (auto-runs in the docker entrypoint, manual for dev-local)
make migrate                   # uv run alembic upgrade head

# 5. Seed the source registry (RSS / API tier weights)
make seed                      # uv run python -m app.scripts.seed_sources

# 6. Tests
make test                      # uv run pytest -v       (~373 test functions, 108 files)

# 7. Lint
make lint                      # uv run ruff check + ruff format
```

Required env vars (see `.env.example` for the canonical list):

- `DATABASE_URL` — `postgresql+asyncpg://postgres:postgres@db:5432/signal`
- `DATABASE_URL_SYNC` — `postgresql+psycopg://...` (used by Alembic only)
- `REDIS_URL` — `redis://redis:6379/0`
- `OPENAI_API_KEY` — required for embeddings + LLM
- `WORLDNEWS_API_KEY` — for the WorldNews ingestion task
- `BUILDER_API_KEY` / `BUILDER_API_SECRET` / `BUILDER_API_PASSPHRASE` / `BUILDER_PRIVATE_KEY` — Polymarket Builder credentials (HMAC + EOA private key, used for attribution)
- `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_TRADER`
- `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_EMAIL` — web push
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — optional
- `APP_BASE_URL` — defaults `https://getforesight.io`, drives CORS allow-list
- `SIGNAL_API_KEY` — when set, `ApiKeyMiddleware` requires `X-API-Key` on every `/api/*` call

## 4. Project structure

```
app/
├── api/              FastAPI app, routes, middleware, websocket, push, schemas
├── agents/           Background "agent team": scout, analyst, strategist, risk_manager, reporter
├── content/          Static content (quiz_questions.py)
├── core/             config.py — single Pydantic Settings object
├── db/               database.py (async engine + session factory) + models.py (31 SQLAlchemy classes)
├── eval/             Offline evaluation harness (labels, runner, metrics)
├── event_engine/     Clustering: simple_clusterer, event_builder, event_counts
├── ingestion/        Source clients: rss_scraper, gdelt_client, worldnews_client, x_scraper_import, sources_registry
├── llm/              openai_client, impact_analyzer, event_summarizer, reasoning_analyzer
├── measurement/      Variant scoring + baselines (heuristic_v1, random, market_price, momentum, news_sentiment) + Brier/Wilson/PnL metrics
├── polymarket/       clob_client (CLOB), gamma_client (Gamma API)
├── processing/       news_cleaner, ner_extractor, embedding_service, embedding_reader, freshness, bucket_classifier, text_composers
├── retrieval/        bm25_index, vector_retriever, hybrid_search (+ hybrid_search_v2), ranking_variant
├── scoring/          heuristic_scorer, strength_scorer, trade_scorer, weights, feature_builder
├── scripts/          seed_sources.py
├── services/         user_limits.py (UX gating logic)
├── signal/           signal_builder, direction_eval
├── sourcing/         article_ranker, pool_builder, prod_trace
├── telegram/         bot.py — full /signals /portfolio /brief /agents command set
├── trading/          builder_client, position_tracker, safe_deployer (Gnosis Safe)
└── workers/          celery_app + 12 task modules (one per domain: ingestion, pipeline, scoring, sourcing, outcomes, trading, risk, reports, embeddings_backfill, ranking_shadow, diagnostics)
```

## 5. API surface

All routes are mounted under `/api` from `app/api/main.py:59`:

```python
app.include_router(router, prefix="/api")           # core (signals, markets, events, analytics, health)
app.include_router(ws_router)                       # /ws/signals (no /api prefix)
app.include_router(push_router, prefix="/api")      # /api/push/{subscribe,unsubscribe}
# … then per-domain routers, each with its own internal prefix:
```

| Module | Internal prefix → final path | Purpose |
|---|---|---|
| `routes/__init__.py` (`router`) | `/api` | `/health`, `/signals`, `/markets`, `/events`, `/analytics/*`, `/pipeline/status` |
| `routes/trading.py` | `/api/trading` | Order placement, balances |
| `routes/trading_wallet.py` | `/api/trading/wallet` | EOA → Gnosis Safe link, `/connect`, `/disconnect` |
| `routes/auth.py` | `/api/auth` | `/register`, `/login`, `/google`, `/me`, `/me/profile`, `/me/preferences`, `/logout` |
| `routes/portfolio_v2.py` | `/api/portfolio` | V2 portfolio aggregation |
| `routes/performance_v2.py` | `/api/performance` | V2 perf KPIs (track record, by-bucket) |
| `routes/quota.py` | `/api/me` | `/me/quota`, `/me/quota/consume`, `/me/limits` |
| `routes/sources.py` | `/api/sources` | Source registry + per-source stats |
| `routes/paper.py` | `/api/paper` | Paper-trading sandbox (Apprendre tab) |
| `routes/outcome_views.py` | `/api/signals` | Outcome-view counters (per-signal click-through) |
| `routes/admin_metrics.py` | `/api/admin/metrics` | `/variants`, `/variants/rolling` (measurement readout) |
| `routes/agents.py` | `/api/agents` | `/status`, `/activity` |
| `routes/api_keys.py` | `/api/api-keys` | B2B API key CRUD |
| `routes/subscriptions.py` | `/api/subscriptions` | Stripe checkout + webhook |
| `routes/b2b.py` | `/api/v1` | Public B2B surface (gated by `X-API-Key`) |
| `routes/telegram_webhook.py` | `/api/telegram` | Bot webhook receiver |
| `push.py` | `/api/push` | Web-push subscribe/unsubscribe (VAPID) |
| `websocket.py` | `/ws/signals` | Real-time signal push, fed by Redis pub/sub channel `signal:new` |

Two route files (`routes/onboarding.py`, `routes/quiz.py`) are present on disk but **not registered** in `main.py` — they're scheduled for deletion after one cycle (see comment at `main.py:93–97`). Don't add new code to them.

**Auth + rate-limit middleware** (`app/api/middleware.py`):
- `RateLimitMiddleware` — 600 req/min per IP, in-memory dict (single-instance only; revisit for prod multi-replica).
- `ApiKeyMiddleware` — when `SIGNAL_API_KEY` is set, every `/api/*` path that's not in `PUBLIC_PATHS` (`/api/health`, `/docs`, `/openapi.json`, `/ws/signals`, `/api/analytics/track-record*`) needs `X-API-Key` header or `?api_key=…` query param.

**CORS** (`app/api/cors.py::resolve_cors_origins`) — explicit allow-list per env. Production = `[APP_BASE_URL] + extras`. Other envs add `localhost:5173` (Vite) and `localhost:3000` (CRA/SPA). The previous `allow_origins=["*"]` + `allow_credentials=True` combo was removed during the audit — browsers reject it and it's a CSRF surface.

**Pydantic schemas** — top-level shapes in `app/api/schemas/__init__.py`; the V2 frontend payloads (camelCase, French labels, source counts) live in `app/api/schemas_v2.py`. Translation/enrichment is centralised in `app/api/signal_mapper.py` so React stays a dumb renderer.

**WebSocket** — `app/api/websocket.py:69` exposes `/ws/signals`. On first client connect, it subscribes to Redis channel `signal:new`; every signal persisted by `tasks_scoring` is published there and broadcast to all open sockets.

## 6. Database

Schema is owned by Alembic. `alembic upgrade head` runs in the Docker entrypoint (`docker-compose.yml:56`) **before** uvicorn boots — the FastAPI lifespan no longer auto-creates tables (audit follow-up; the previous in-lifespan path raced concurrent boots and masked drift between SQLAlchemy models and migration state — see comment at `app/api/main.py:18–22`).

25 migrations, `alembic/versions/001_*` → `025_*`. Highlights:
- `001_initial_schema` — full base schema
- `003_hnsw_index_markets_embedding` — HNSW (cosine) on `markets.embedding`
- `020_signal_predictions` — measurement-layer prediction rows
- `022_add_embedding_v2_columns` — adds `embedding_v2` (Vector(1536)) to `news_clean`, `markets`, `events`
- `023_add_hnsw_index_market_embedding_v2` — second HNSW index, on `markets.embedding_v2`
- `025_rename_signal_variant_to_heuristic_v1` — final rename of the prod variant key

> Brief discrepancy: HNSW exists only on `markets.embedding` (mig 003) and `markets.embedding_v2` (mig 023). There is **no** HNSW index on `news_clean.embedding_v2` — only the column. Fine because article retrieval flows through events (which join through `event_news_links`).

Main tables — defined in `app/db/models.py` (921 lines, 31 classes):

| Table | Class @ line | Purpose |
|---|---|---|
| `news` | `News:59` | Raw ingested article |
| `news_clean` | `NewsClean:94` | Cleaned + simhash + bucket + embedding(_v2) |
| `article_entities` | `ArticleEntity:128` | NER spans |
| `markets` | `Market:144` | Polymarket markets (PK = condition_id text) |
| `events` | `Event:192` | Clustered news → event |
| `event_news_links` | `EventNewsLink:240` | N:N events ↔ news_clean (with excerpts since mig 016) |
| `event_market_candidates` | `EventMarketCandidate:267` | Hybrid-search candidates per event |
| `event_market_analysis` | `EventMarketAnalysis:293` | LLM impact output (one per event×market) |
| `event_market_features` | `EventMarketFeatures:326` | Engineered features for scoring |
| `event_market_ranking_shadow` | `EventMarketRankingShadow:360` | Shadow ranking for v2 promotion (mig 024) |
| `llm_cost_log` | `LLMCostLog:396` | Per-call cost tracking (call_type, tokens, USD) |
| `signals` | `Signal:413` | The output. Has `signal_score`, `signal_strength`, `trade_quality`, `direction`, `dedupe_key`, `reasoning`, `source_tier_mix` (JSONB) |
| `signal_outcomes` | `SignalOutcome:458` | Resolution prices at T+5m/15m/1h/24h + final |
| `signal_predictions` | `SignalPrediction:482` | Measurement-layer: one row per (signal, variant) — `predicted_probability`, `predicted_direction`, `brier_score`, `simulated_pnl_eur` (uniq on `signal_id+variant`) |
| `signal_articles` | `SignalArticle:512` | Audit trail — which articles each variant saw (mig 021) |
| `user_profiles` | `UserProfile:536` | Auth + plan + Stripe sub id + `polymarket_safe_address` (mig 013) |
| `portfolios` / `positions` / `orders` | 575 / 601 / 632 | Trading book |
| `agent_activity` | `AgentActivity:670` | Agent-team event log |
| `daily_briefs` | `DailyBrief:686` | Generated reports |
| `api_keys_b2b` | `ApiKeyB2B:707` | B2B API surface |
| `gdelt_events_raw` | `GdeltEventRaw:740` | GDELT 2.0 raw ingestion (mig 017) |
| `signal_pending_reasoning` | `SignalPendingReasoning:762` | LLM-backfill queue |
| `user_limits` / `paper_positions` / `onboarding_progress` / `quiz_attempts` | 782 / 828 / 861 / 894 | UX gating, paper trading, learn-and-trade flow |
| `outcome_views` | `OutcomeView:909` | Per-signal outcome view counter |

## 7. Workers / Celery

`app/workers/celery_app.py` — broker + backend both `redis_url`, JSON serializer, 5-minute hard task limit, `worker_prefetch_multiplier=1`.

**Queues** (one container per queue, see `docker-compose.yml:84–225`):

| Queue | Container | What runs there |
|---|---|---|
| `ingestion` | `worker-ingestion` (1 GB) | RSS, WorldNews, GDELT, X-scraper inbox |
| `pipeline` | `worker-pipeline` (×2 replicas, 1 GB) | `process_article`, `compute_embedding_batch`, `build_events` (backfill) |
| `scoring` | `worker-scoring` (2 GB) | `try_instant_event` (fast path), hybrid search, LLM impact, signal persistence, ranking shadow, embeddings backfill |
| `markets` | `worker-markets` (512 MB) | `fetch_markets`, `compute_market_percentiles` (heavy CLOB calls, isolated) |
| `default` | `worker-outcomes` (512 MB) | `tasks_outcomes.*`, hourly diagnostics |
| `trading` | `worker-trading` (512 MB) | Order fills, position sync, risk monitoring, daily/weekly reports |

Routing rules in `celery_app.py:37–51`. Beat lives in its own `beat` container (`celery_app.py:53–162`).

Most-important beat entries:

| Schedule key | Interval | Task |
|---|---|---|
| `fetch-rss-tier1` | `RSS_POLL_INTERVAL_SECONDS` (45 s) | `tasks_ingestion.fetch_rss_feeds` |
| `fetch-worldnews` | 120 s | `tasks_ingestion.fetch_worldnews` |
| `fetch-markets` | 300 s | `tasks_ingestion.fetch_markets` |
| `fetch-gdelt-every-5min` | 300 s | `tasks_ingestion.fetch_gdelt` |
| `embed-news-batch` | configurable | `tasks_pipeline.compute_embedding_batch` |
| `build-events` | configurable | `tasks_pipeline.build_events` (catches fast-path misses) |
| `retry-stuck-events` | 300 s | `tasks_scoring.retry_stuck_events` |
| `rescore-zero-signals` | 600 s | `tasks_scoring.rescore_zero_signal_events` |
| `backfill-reasoning-every-10min` | 600 s | `tasks_scoring.backfill_reasoning` |
| `poll-order-fills` | 60 s | `tasks_trading.poll_order_fills` |
| `sync-positions` | 300 s | `tasks_trading.sync_positions` |
| `monitor-risk` | 300 s | `tasks_risk.monitor_positions` |
| `daily-brief` | 86 400 s | `tasks_reports.generate_daily_brief` |
| `clustering-diversity-hourly` | 3600 s | `tasks_diagnostics.emit_diversity_distribution` |
| `catchup-outcomes` | 600 s | `tasks_outcomes.catchup_outcomes` |
| `check-resolved-markets` | 6 h | `tasks_outcomes.check_resolved_markets` |

Dispatch from a Python REPL or test:

```python
from app.workers.tasks_ingestion import fetch_rss_feeds
fetch_rss_feeds.delay()                                    # async, returns AsyncResult
fetch_rss_feeds.apply(args=[]).get()                       # sync, in-process
```

Inspect queue depth:

```bash
docker compose exec redis redis-cli llen celery            # default queue
docker compose exec redis redis-cli llen scoring           # named queue
```

Active workers:

```bash
docker compose exec app celery -A app.workers.celery_app inspect active
```

## 8. Scoring + measurement

**Heuristic scorer** — `app/scoring/heuristic_scorer.py:HeuristicScorer` produces `signal_strength` (4 weighted features: freshness, source, confirmation, llm) and `trade_quality` (3 features: liquidity, spread, time_to_resolution), then composes them via `strength_weight=0.75, trade_weight=0.25`. Weights are a `frozen dataclass` in `app/scoring/weights.py:HeuristicWeights` — sums must equal 1.0 within 1e-6 or construction raises (frozen because shared across FastAPI + Celery threads). The launch snapshot is `HeuristicWeights.frozen_v1()`.

**Measurement layer** — `app/measurement/`:
- `variant_registry.py` — `VariantRegistry` keyed on variant name (`heuristic_v1` plus baselines). Returns a `VariantPrediction(predicted_direction, predicted_probability)`.
- `baselines.py` — four baselines: `baseline_random`, `baseline_market_price`, `baseline_momentum`, `baseline_news_sentiment`. The last two abstain at neutral inputs (recent fixes; see commits `c7131b8`, `50e62e5`).
- `metrics.py` — `wilson_ci95(n,k)`, `brier_from_outcome(p, label)`, `simulated_pnl_eur(...)`.
- `pipeline.py` — runs each variant against a `ScoringContext` and writes one `SignalPrediction` row per (signal × variant), resolved later when prices land in `signal_outcomes`.

Latest readout: `docs/audit/heuristic_validation_report_2026-04-24.md`. Headline: `heuristic_v1` Brier=0.309 (n=26 brier-defined), hit_rate 0.615 [0.425, 0.776] vs `baseline_market_price` hit_rate 0.962 — the market is currently the better-calibrated baseline at horizon=t1h, which is exactly why the measurement harness exists.

Recent fix history (chantier-2.5, branch `pivot/learn-and-trade`):
- `25425fb` — async `_persist_signal` writes `signal_strength` + `trade_quality`
- `ed75777` — `heuristic_v1` reads composed `signal_score`, not raw `strength`
- `c7131b8` — `news_sentiment` abstains when sentiment == 0
- `50e62e5` — derived per-event `source_weight` + `source_tier`

## 9. LLM usage rules

- **One LLM call per pipeline step**, at the event level — never per article. The composer in `app/processing/text_composers.py` collapses the cluster into a single prompt input.
- **Versioned prompts** in `prompts/`: `impact_analysis_v1.txt`, `event_summary_v1.txt`, `signal_reasoning_v1.txt`, `daily_brief_v1.txt`, `weekly_report_v1.txt`. Bump the suffix on any change, never overwrite.
- **Models**: `gpt-4o-mini` (default `openai_llm_model`) for impact/reasoning, `gpt-4o` for the heavier `openai_impact_model` codepath, `text-embedding-3-small` (1536 dims) for embeddings.
- **Cost tracking**: every call writes a row to `llm_cost_log` (table `llm_cost_log`, model class `LLMCostLog`). Read via `GET /api/analytics/costs` for daily breakdowns; alert threshold `LLM_COST_ALERT_USD=30`.

## 10. Polymarket integration

- **`app/polymarket/`** — `clob_client.py` (CLOB REST + websocket), `gamma_client.py` (Gamma metadata API).
- **`app/trading/builder_client.py`** — wraps `py_clob_client_v2.ClobClient` with the **funder pattern**: Foresight signs orders with `BUILDER_PRIVATE_KEY`, but `funder=user_safe_address` so USDC settles from the user's Gnosis Safe. `OrderArgsV2` carries `builder_code` for attribution to Foresight's builder account.
- **`app/trading/safe_deployer.py`** — deploys a Gnosis Safe per user on first connect.
- **`app/trading/position_tracker.py`** — open-position bookkeeping.
- **Builder Program** — gasless execution, attributed via `builder_code`. The user has a single linked Safe (`user_profiles.polymarket_safe_address`, mig 013).
- **Wallet linking spec**: `docs/specs/2026-04-22-polymarket-wallet-link-design.md`. Companion plan: `docs/plans/2026-04-22-polymarket-wallet-trading.md`. Wallet-provider choice (Privy vs Magic) is open in the spec; the EOA → Safe registration flow is implemented at `app/api/routes/trading_wallet.py` (`POST /api/trading/wallet/connect`).

## 11. Telegram bot

- `app/telegram/bot.py` — full command surface: `/start`, `/signals`, `/portfolio`, `/brief`, `/agents`, `/help`. Dispatched from `app/api/routes/telegram_webhook.py` mounted at `/api/telegram/webhook`.
- High-conviction signals trigger an alert via `app/workers/tasks_scoring.py:_send_telegram_alert(signal)` (called at `tasks_scoring.py:1009`). It posts directly to `https://api.telegram.org/bot{TOKEN}/sendMessage`.
- Setup: set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env`, register the webhook URL with BotFather, then point Telegram at `https://<your-host>/api/telegram/webhook`.

## 12. Testing

- 108 test files / ~373 test functions under `tests/unit/` and `tests/integration/`.
- Async by default (`pyproject.toml: asyncio_mode = "auto"`). Sync tests use the `db_session` fixture (in-memory SQLite); async tests use `async_db_engine` + `async_db_factory`, both defined in `tests/conftest.py`. The `_reset_db_cache` autouse fixture clears `app.db.database` module-level globals so each test's per-loop engine wins (pytest-asyncio resets the loop per function).
- Run subsets with markers: `pytest -m unit`, `pytest -m integration`.
- Single test: `uv run pytest tests/unit/test_measurement_baselines.py -v`.

## 13. Common dev tasks

**Add a new endpoint**:
1. Create `app/api/routes/<name>.py` with `router = APIRouter(prefix="/<name>", tags=["<name>"])`.
2. Define request/response schemas in `app/api/schemas/__init__.py` (or `schemas_v2.py` for the V2 SPA).
3. In `app/api/main.py`, import the router and call `app.include_router(<name>_router, prefix="/api")`.
4. If it touches the DB, depend on `Depends(get_db_session)` (from `app/db/database.py`).

**Add a new Celery task**:
1. Add it to `app/workers/tasks_<area>.py`, decorated `@celery_app.task` (or `@celery_app.task(bind=True)` for retries).
2. If the area is new, append the module path to `celery_app.autodiscover_tasks([...])` in `celery_app.py:164`.
3. If the task should run in a non-default queue, add an entry to `celery_app.conf.task_routes`.
4. To schedule it, add a `_beat_schedule[<key>] = {...}` entry.

**Add a new migration**:
```bash
make migrate-new msg="add foo column to bar"      # uv run alembic revision --autogenerate -m "<msg>"
# edit alembic/versions/0NN_<slug>.py — autogenerate is a draft, not ground truth
make migrate                                      # apply
```

**Add a new SQLAlchemy model**: edit `app/db/models.py`, then `make migrate-new msg="..."`. Re-run autogenerate after import-cycle fixes.

**Promote a v2 variant**: see `docs/runbooks/promote_signal_v2.md`, `promote_heuristic_candidate.md`, `promote_embeddings_v2.md`, `promote_ranking_v2.md`.

## 14. Reference docs

- `BLUEPRINT.md` (846 lines, French) — canonical technical reference. Single source of truth for end-to-end pipeline + DB.
- `docs/audit/heuristic_validation_report_2026-04-24.md` — latest variant readout.
- `docs/audit/ISSUES_BACKLOG.md` — open audit findings.
- `docs/runbooks/promote_*.md` — promotion procedures for v2 variants (signal, embeddings, ranking, heuristic candidate).
- `docs/superpowers/plans/` — chantier execution plans (premium-redesign, polymarket-wallet-trading, measurement-foundations, signal-sourcing-traceability, embeddings-eval-harness, heuristic-score-validation, clustering-hardening, event-market-ranking-tuning).
- `docs/superpowers/specs/` — chantier design specs (matched 1:1 to the plans).
- `docs/specs/2026-04-22-polymarket-wallet-link-design.md` — wallet linking design (uses funder pattern).
- `docs/builder_program_application.md` — Polymarket Builder Program application context.
- `docs/go_to_market.md` — pricing + GTM notes.
