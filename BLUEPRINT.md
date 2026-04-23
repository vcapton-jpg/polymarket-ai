# Polymarket AI — Blueprint technique complet

> Document interne. Référence exhaustive de l'architecture, des modules, des pages, des flux de données et des seuils. Mis à jour le 2026-04-23.

---

## Table des matières

1. [Vue d'ensemble produit](#1-vue-densemble-produit)
2. [Architecture globale](#2-architecture-globale)
3. [Stack technique](#3-stack-technique)
4. [Infrastructure & services Docker](#4-infrastructure--services-docker)
5. [Base de données (modèles complets)](#5-base-de-données-modèles-complets)
6. [Pipeline de données — bout en bout](#6-pipeline-de-données--bout-en-bout)
7. [Couche intelligence signal](#7-couche-intelligence-signal)
8. [Workers Celery & planification](#8-workers-celery--planification)
9. [LLM & prompts](#9-llm--prompts)
10. [Intégration Polymarket](#10-intégration-polymarket)
11. [Outcomes tracking](#11-outcomes-tracking)
12. [API REST (toutes les routes)](#12-api-rest-toutes-les-routes)
13. [Frontend — pages & routes](#13-frontend--pages--routes)
14. [Frontend — composants & data layer](#14-frontend--composants--data-layer)
15. [Configuration clé](#15-configuration-clé)
16. [Développement & tests](#16-développement--tests)
17. [État actuel & dette](#17-état-actuel--dette)

---

## 1. Vue d'ensemble produit

**Polymarket AI (alias "Signal" / "Foresight")** est une plateforme d'intelligence temps réel sur les marchés prédictifs Polymarket.

**Proposition de valeur :** détecter qu'une news qui vient de tomber crée un mispricing sur Polymarket, et livrer un signal actionnable avant que le marché se corrige.

**Boucle principale :**
```
News (RSS/X/API) → Clustering en événements → Matching marchés Polymarket
  → Analyse LLM → Scoring hybride → Signal → Suivi d'outcome T+5m/15m/1h/24h
```

**Usagers :**
- **B2C** : traders particuliers via frontend React (feed signaux, portefeuille, éducation).
- **B2B** : API Keys (`/v1/*`) pour clients tiers.
- **Agents internes** : bot Telegram, agents automatiques (daily brief, risk monitoring).

---

## 2. Architecture globale

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOURCES EXTERNES                          │
│   RSS (via RSSHub)  │  X scraper  │  WorldNewsAPI  │  Polymarket│
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────────┐   ┌──────────────────────────┐
│    INGESTION (Celery)        │   │   MARKET FETCHER         │
│  tasks_ingestion.py          │   │   tasks_pipeline.py      │
│  - fetch_rss_feeds (90s)     │   │   - fetch_markets (15m)  │
│  - fetch_gdelt               │   │   - compute_market_pct   │
│  - ingest_x_scraper          │   └──────────┬───────────────┘
└──────────────┬───────────────┘              │
               ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              POSTGRES + pgvector (foresight-db)                  │
│  news → news_clean → events ↔ event_market_candidates            │
│                              ↘                                   │
│                             signals → signal_outcomes            │
└──────────────┬──────────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────────┐
│        PROCESSING + SCORING (Celery workers)                     │
│  1. Cleaner + NER + Embeddings (text-embedding-3-small)         │
│  2. Clustering cosine+temporel → Event                           │
│  3. Hybrid search (vector + BM25 + RRF fusion)                  │
│  4. LLM reasoning (GPT-4o-mini) → catalyst, direction, excerpts │
│  5. Heuristic scoring → signal_score ∈ [0,100]                  │
│  6. Persist Signal + schedule outcome captures                   │
└──────────────┬──────────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FASTAPI (foresight-app:8001)                   │
│  REST /api/*  │  WebSocket /ws/signals  │  Push /api/push      │
└──────────────┬──────────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────────┐
│       FRONTEND React + Vite (frontend:3000 en dev)               │
│  Pages: Signals, SignalDetail, Portfolio, Performance,           │
│         Apprendre, Settings, Landing, Pricing, FAQ, Auth         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Stack technique

### Backend
- **Python 3.11+** avec `async/await` partout
- **FastAPI** (API REST + WebSocket)
- **SQLAlchemy 2.0** async (`Mapped[...]`, `mapped_column`)
- **Alembic** (migrations DB)
- **Celery + Redis** (file de tâches)
- **PostgreSQL 16 + pgvector** (embeddings 1536-dim)
- **OpenAI SDK** (GPT-4o, GPT-4o-mini, text-embedding-3-small)
- **rank_bm25** (BM25 Okapi in-memory)
- **httpx** (clients HTTP async)
- **py-clob-client-v2** (ordres Polymarket)
- **structlog** (logs JSON)
- **Prometheus client** (métriques)

### Frontend
- **React 18.3** + **TypeScript 5.6** (strict)
- **Vite 6** + **Vitest 4**
- **React Router 7** (routes lazy avec `React.lazy`)
- **TanStack Query 5** (server state)
- **Tailwind 3.4** + **Radix UI** + **CVA** (design system)
- **Framer Motion 11** (animations, respect `prefers-reduced-motion`)
- **i18next** (FR primaire, EN fallback)
- **Wagmi 2 + Viem 2** (Web3 Polygon, MetaMask)
- **Recharts 3** (graphes)
- **Testing Library + jsdom**

### Fonts
- Satoshi (display) / Inter (sans) / JetBrains Mono (mono)

---

## 4. Infrastructure & services Docker

Défini dans `docker-compose.yml`. 12 services + 2 volumes.

| Service | Image/Build | Rôle | Port |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | PostgreSQL + pgvector | 5435→5432 |
| `redis` | `redis:7-alpine` | Broker Celery + cache | 6379 |
| `rsshub` | `diygod/rsshub` | Proxy RSS (cache Redis db=5) | 1200 |
| `app` | local `Dockerfile` | FastAPI + Uvicorn `--reload` | 8001→8000 |
| `worker-ingestion` | local | Queue `ingestion` (RSS, X, WorldNews) | — |
| `worker-pipeline` | local | Queue `pipeline` (clean, NER, embeddings, events) | — |
| `worker-scoring` | local | Queue `scoring` (hybrid search, LLM, signal) | — |
| `worker-markets` | local | Queue `markets` (Polymarket API, isolé) | — |
| `worker-outcomes` | local | Queue `default` (capture prix T+X, résolution) | — |
| `worker-trading` | local | Queue `trading` (positions, orders, briefs) | — |
| `beat` | local | Scheduler Celery Beat | — |
| `frontend` | local | Vite dev server | 3000 |

**Healthchecks** actifs sur `db`, `redis`, `app`.

**Volumes** : `postgres_data`, `redis_data`.

**Variables d'env clés (.env)** :
```
OPENAI_API_KEY=
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/signal
REDIS_URL=redis://redis:6379/0
TELEGRAM_BOT_TOKEN=
POLYMARKET_PRIVATE_KEY=
POLYMARKET_BUILDER_CODE=
STRIPE_SECRET_KEY=
GOOGLE_OAUTH_CLIENT_ID=
```

---

## 5. Base de données (modèles complets)

Source : `app/db/models.py`. Toutes les tables ci-dessous avec PK / FK / colonnes critiques.

### 5.1 Ingestion & cleaning

#### `sources_registry` — SourceRegistry
Registre des sources avec tier & pondération.
- `id` PK, `source_name` UNIQUE, `source_type` (rss/x/api), `url`, `tier` (1-3), `weight`, `active`

#### `news` — News
Article brut, une ligne par URL.
- `id` PK, `url` UNIQUE, `title`, `text`, `source_name`, `source_tier`, `source_weight`, `publish_date`, `ingestion_date`, `ingestion_lag_seconds`, `source_id` FK→sources_registry

#### `news_clean` — NewsClean
Article nettoyé + embedding.
- `id` PK, `news_id` FK→news, `clean_text`, `simhash` (dédoublonnage), `bucket` (geopolitics/politics/etc.), `word_count`, `language`, `embedding VECTOR(1536)`, `embedding_computed_at`

#### `article_entities` — ArticleEntity
Entités nommées (NER).
- `id` PK, `clean_id` FK→news_clean, `entity_type` (PERSON/ORG/GPE/…), `entity_value`

### 5.2 Marchés Polymarket

#### `markets` — Market
PK = `condition_id` texte (ID Polymarket).
- `market_id` PK, `question`, `description`, `category`, `bucket`, `tags[]`, `end_date`, `active`, `closed`, `accepting_orders`
- Microstructure : `volume`, `liquidity`, `best_bid`, `best_ask`, `spread`, `last_trade_price`, `liquidity_pct`
- `clob_token_ids` JSONB (tokens YES/NO)
- `market_retrieval_text` (texte pour BM25), `embedding VECTOR(1536)`

### 5.3 Événements & candidats

#### `events` — Event
Cluster de news.
- `id` PK, `event_title`, `event_summary`, `event_retrieval_text`, `key_entities[]`, `event_type`, `bucket`, `articles_count`, `unique_sources_count`, `first_seen`, `last_seen`, `embedding VECTOR(1536)`

#### `event_news_links` — EventNewsLink
N-N events ↔ news_clean, avec excerpt & relevance (Axis-A).
- `event_id` FK, `clean_id` FK, `key_excerpt`, `relevance_score`

#### `event_market_candidates` — EventMarketCandidate
Top-K marchés sortis du hybrid search par événement.
- `event_id` FK, `market_id` FK, `rank`, `rrf_score`, `cosine_score`, `bm25_score`, `entity_matches`

#### `event_market_analysis` — EventMarketAnalysis
Sortie du LLM #2 (impact_analyzer).
- `event_id`, `market_id`, `impact_direction`, `impact_strength`, `confidence`, `ambiguity_score`, `specificity_score`, `raw_json`

#### `event_market_features` — EventMarketFeatures
Features normalisées [0-1] pour scoring (heuristique + futur LightGBM).
- `event_id`, `market_id`, `freshness`, `source_weight`, `confirmation`, `liquidity`, `spread`, `time_to_resolution`, plus colonnes LLM dérivées

### 5.4 Signaux & outcomes

#### `signals` — Signal (sortie finale)
- `id` PK, `event_id` FK, `market_id` FK, `direction` ("BUY_YES"/"BUY_NO"), `signal_score`, `signal_strength`, `trade_quality`
- `catalyst` (≤120c), `reasoning` (100-600c), `confidence_label`, `urgency_label`, `tradability_label`
- `market_price_at_signal`, `source_tier_mix` JSONB `{tier_1: n, ...}`, `llm_model_version`
- `created_at`, `below_threshold` (bool pour ML)

#### `signal_outcomes` — SignalOutcome
- `signal_id` PK/FK
- `price_t5min`, `price_t15min`, `price_t1h`, `price_t24h` (numeric 6,4)
- `move_t5min_pct`, `move_t15min_pct`, `move_t1h_pct`, `move_t24h_pct` (numeric 7,4)
- `price_resolved`, `direction_correct` (bool), `outcome_label` (1 si ≥0.95, 0 si ≤0.05, NULL sinon)

### 5.5 Observabilité & utilisateurs

- `llm_cost_log` — chaque appel LLM : call_type, model, tokens, cost_usd
- `users`, `user_preferences`, `user_profiles` (inférés de `auth.py` + `portfolio_v2.py`)
- `api_keys` — B2B (prefix, hash, plan)
- `subscriptions` — Stripe
- `trading_positions`, `trading_orders` — persistance des trades

---

## 6. Pipeline de données — bout en bout

```
┌─ ingestion ─┐
│ RSS (90s)   │─► News (raw)
│ X scraper   │─► News (raw)
│ WorldNews   │─► News (raw)
└─────────────┘
       ▼
┌─ pipeline (Celery) ─────────────────────────────────┐
│ process_article                                      │
│  1. Clean text (strip HTML, normalize)               │
│  2. Dédupe via simhash                               │
│  3. NER → article_entities                           │
│  4. Classify → bucket                                │
│  5. Insert NewsClean                                 │
│                                                      │
│ compute_embedding_batch (120s)                       │
│  - Embed clean_text → VECTOR(1536)                   │
│                                                      │
│ build_events (300s)                                  │
│  - simple_clusterer: cosine ≥0.82 & Δt ≤120m         │
│  - event_builder: title/summary/entities/retrieval   │
└──────────────────────────────────────────────────────┘
       ▼
┌─ scoring (Celery) ──────────────────────────────────┐
│ try_instant_event (trigger immédiat par event)       │
│                                                      │
│ 1. hybrid_search_markets(event)                      │
│    - vector_retriever: pgvector top-3K (cos ≥0.45)   │
│    - bm25_index: top-3K sur market_retrieval_text    │
│    - RRF fusion: 1/(60+rank_v) + 1/(60+rank_b)       │
│    - Entity boost: +0.5 par entité matchée           │
│    → top 10 marchés                                  │
│                                                      │
│ 2. Pour chaque candidat:                             │
│    - impact_analyzer (GPT-4o)                        │
│      → impact_direction, strength, confidence,       │
│        ambiguity, specificity                        │
│    - Filtres durs:                                   │
│      · cosine < 0.52 → reject                        │
│      · spread > 0.15 → reject                        │
│      · direction ∉ {BUY_YES, BUY_NO} → reject        │
│      · ambiguity > 0.80 → reject                     │
│      · specificity < 0.4 → reject                    │
│      · YES price ∉ [0.05, 0.95] → reject             │
│                                                      │
│ 3. reasoning_analyzer (GPT-4o-mini)                  │
│    → catalyst, reasoning, excerpts (littéraux),      │
│      direction_recommendation, source_tier_mix       │
│                                                      │
│ 4. FeatureBuilder → 6 features [0-1]                 │
│ 5. HeuristicScorer                                   │
│    strength = 0.15×fresh + 0.10×src + 0.15×conf      │
│             + 0.60×(0.65×imp + 0.35×llm_conf)        │
│    quality  = 0.40×liq + 0.35×spread + 0.25×ttr      │
│    score    = 0.75×strength + 0.25×quality           │
│                                                      │
│ 6. _persist_signal                                   │
│    - Normalize direction → BUY_YES/BUY_NO            │
│    - Insert Signal                                   │
│    - Update EventNewsLink.key_excerpt + relevance    │
│    - Schedule capture_price @ T+5m/15m/1h/24h        │
└──────────────────────────────────────────────────────┘
       ▼
┌─ outcomes (Celery) ─────────────────────────────────┐
│ capture_price(signal, field) → CLOB API             │
│ catchup_outcomes (10m) → backfill manquants         │
│ check_resolved_markets (6h) → final price + label   │
└──────────────────────────────────────────────────────┘
       ▼
┌─ trading (optionnel, utilisateur actif) ────────────┐
│ place_limit_order / place_market_order (Polymarket) │
│ sync_positions, poll_order_fills                    │
└──────────────────────────────────────────────────────┘
```

---

## 7. Couche intelligence signal

### 7.1 Formule de score (détail)

```python
# Signal Strength (75% du final) — crédibilité news
strength_base = 0.15×freshness + 0.10×source_weight + 0.15×confirmation
llm_combined  = 0.65×impact_strength + 0.35×llm_confidence
signal_strength = clamp(strength_base + 0.60×llm_combined, 0, 100)

# Trade Quality (25% du final) — faisabilité d'exécution
trade_quality = clamp(0.40×liquidity + 0.35×spread + 0.25×ttr, 0, 100)

# Final
signal_score = clamp(0.75×signal_strength + 0.25×trade_quality, 0, 100)
```

### 7.2 Composants feature (tous ∈ [0,1])

| Feature | Bornes |
|---|---|
| **freshness** | ≤1h=1.0 · ≤6h=0.9 · ≤24h=0.7 · ≤72h=0.4 · >72h=0.1 |
| **source_weight** | moyenne pondérée des tiers, capé à 1.0 |
| **confirmation** | ≥3 sources=1.0 · ≥2=0.85 · 1 tier-1=0.7 · sinon=0.5 |
| **liquidity** | <1k=0.1 · <10k=0.15 · <100k=0.6-1.0 · <500k=0.7 · >500k=0.4 |
| **spread** | ≤0.2¢=1.0 · ≤0.5¢=0.8 · ≤1¢=0.5 · linéaire vers 0 |
| **time_to_resolution** | now=1.0 · <24h=0.95 · <1w=0.8 · <1mo=0.6 · <1y=0.4 |

### 7.3 Labels dérivés

| Label | Règle |
|---|---|
| **confidence** | high (score ≥80 & ≥2 sources) / medium (≥65) / low |
| **urgency** | critical (ttr≥0.8) / high (≥0.5) / medium (≥0.2) / low |
| **tradability** | excellent (0.6×liq+0.4×spread≥0.8) / good (≥0.6) / fair (≥0.4) / poor |

### 7.4 Raisons de rejet (toutes)

Loguées `[e{event_id}/m{market_id[:12]}] signals.rejected_*` :

1. `rejected_cosine` — cosine < `signal_min_cosine_score` (0.52)
2. `rejected_spread` — spread > `hard_exclusion_spread` (0.15)
3. `rejected_direction` — impact_direction ∉ {BUY_YES, BUY_NO}
4. `rejected_ambiguity` — ambiguity_score > 0.80
5. `rejected_specificity` — specificity_score < 0.4
6. `rejected_impact_strength` — impact_strength == 0
7. `rejected_price_band` — YES price ∉ [0.05, 0.95]
8. `rejected_unclear_direction` — LLM retourne "UNCLEAR" après reasoning
9. `rejected_dedupe` — même marché signalé dans les 72h

---

## 8. Workers Celery & planification

### 8.1 Queues & workers (`celery_app.py`)

| Queue | Worker | Concurrence | Rôle |
|---|---|---|---|
| `ingestion` | worker-ingestion | 1 (solo) | Fetch RSS, X, WorldNews |
| `pipeline` | worker-pipeline | 1 | Clean, NER, embeddings, events |
| `scoring` | worker-scoring | 1 | Hybrid search, LLM, signal building |
| `markets` | worker-markets | 1 | API Polymarket isolée |
| `trading` | worker-trading | 1 | Positions, orders, briefs |
| `default` | worker-outcomes | 1 | Capture prix, résolution |

### 8.2 Beat schedule (intervalles)

| Tâche | Intervalle | Module |
|---|---|---|
| `fetch_rss_feeds` | 90s | `tasks_ingestion.py` |
| `ingest_x_scraper` | 90s | `tasks_ingestion.py` |
| `fetch_gdelt` | 600s | `tasks_ingestion.py` |
| `compute_embedding_batch` | 120s | `tasks_pipeline.py` |
| `build_events` | 300s | `tasks_pipeline.py` |
| `fetch_markets` | 900s (15m) | `tasks_scoring.py` |
| `compute_market_percentiles` | 1h | `tasks_scoring.py` |
| `catchup_outcomes` | 600s (10m) | `tasks_outcomes.py` |
| `check_resolved_markets` | 6h | `tasks_outcomes.py` |
| `sync_positions` | 300s | `tasks_trading.py` |
| `poll_order_fills` | 60s | `tasks_trading.py` |
| `risk_monitoring` | 900s | `tasks_risk.py` |
| `daily_brief` | cron 08:00 | `tasks_reports.py` |
| `weekly_report` | cron dim 18:00 | `tasks_reports.py` |

---

## 9. LLM & prompts

### 9.1 Providers & modèles (`app/llm/`)

- **OpenAI uniquement**
- Reasoning : `gpt-4o-mini-2024-07-18` ($0.15/$0.60 per 1M in/out)
- Impact analysis : `gpt-4o` ($2.50/$10.00 per 1M)
- Embeddings : `text-embedding-3-small` (1536-dim)

**Tracking coût** : chaque appel logué dans `llm_cost_log` avec call_type, tokens, cost_usd.

### 9.2 Prompts (`prompts/`)

| Fichier | Usage |
|---|---|
| `signal_reasoning_v1.txt` | ReasoningAnalyzer — catalyst, reasoning, excerpts |
| `impact_analysis_v1.txt` | ImpactAnalyzer — direction, strength, ambiguity |
| `event_summary_v1.txt` | Résumé d'événement |
| `daily_brief_v1.txt` | Digest quotidien |
| `weekly_report_v1.txt` | Rapport hebdo |

### 9.3 Schéma de sortie ReasoningAnalyzer

```json
{
  "impact_score": 0.78,
  "confidence": 0.85,
  "catalyst": "≤120 chars",
  "reasoning": "100-600 chars, cite ≥1 source by name",
  "direction_recommendation": "YES" | "NO" | "UNCLEAR",
  "article_excerpts": [
    {"news_clean_id": 123, "excerpt": "literal substring", "relevance": 0.9}
  ],
  "source_tier_mix": {"tier_1": 2, "tier_2": 1}
}
```

**Validations client-side** :
- `reasoning` ∈ [100, 600] caractères
- Chaque excerpt est substring EXACTE d'un article source
- Au moins 1 excerpt valide sinon rejet
- Retry 3× avec backoff exponentiel

---

## 10. Intégration Polymarket

### 10.1 Gamma API (`app/polymarket/gamma_client.py`)

`https://gamma-api.polymarket.com`

- `fetch_all_active_markets()` — paginé `/events`, aplati
- `_parse_market()` — extract conditionId, question, volume, liquidity, price, clob_token_ids, tags
- Retry 3× backoff

### 10.2 CLOB API (`app/polymarket/clob_client.py`)

`https://clob.polymarket.com`

- `get_market(condition_id)` — prices tokens + accepting_orders
- `enrich_market()` — extract bid/ask/spread/last_trade
- `get_price_yes()` — helper

### 10.3 Trading (`app/trading/builder_client.py`)

Utilise `py-clob-client-v2` :

- `place_limit_order(token_id, side, price, size, tick_size, neg_risk)` — via OrderArgsV2
- `place_market_order(token_id, side, amount, …)` — FOK en USDC
- **Builder code** : attribution compte (`polymarket_builder_code` en settings)
- **Funder pattern** : orders settle depuis Safe Gnosis utilisateur, pas le wallet builder

---

## 11. Outcomes tracking

Logique dans `app/workers/tasks_outcomes.py`.

### 11.1 Capture intermédiaire

```
Signal créé @ T0
 ├── capture_price(signal, "price_t5min")  @ T+5m
 ├── capture_price(signal, "price_t15min") @ T+15m
 ├── capture_price(signal, "price_t1h")    @ T+1h
 └── capture_price(signal, "price_t24h")   @ T+24h

Chaque capture :
  price_now = ClobClient.get_price_yes(market_id)
  move_pct  = ((price_now - price_at_signal) / price_at_signal) * 100
  UPDATE signal_outcomes SET price_tXXX=…, move_tXXX_pct=…
```

### 11.2 Catch-up (10 min)

`catchup_outcomes()` retrouve les signaux des 48h avec champs manquants et redispatche les captures si l'âge dépasse le seuil correspondant.

### 11.3 Résolution finale (6h)

`check_resolved_markets()` :
1. Récupère 100 signaux sans `price_resolved`
2. Refetch les markets (Gamma)
3. Si `closed=true` → set `price_resolved`, `direction_correct` (via `direction_matches_price_move`), `outcome_label` (1/0/NULL selon final ≥0.95 / ≤0.05)

### 11.4 Évaluation directionnelle (`direction_eval.py`)

```python
def direction_matches_price_move(direction, base, new):
    up = new > base
    if direction in ("YES", "BUY_YES", "UP"):  return up
    if direction in ("NO",  "BUY_NO",  "DOWN"): return not up
    return False
```

---

## 12. API REST (toutes les routes)

Toutes préfixées par `/api` dans `app/api/main.py`. Sauf `ws_router` (WebSocket).

| Routeur | Prefix | Endpoints principaux |
|---|---|---|
| `websocket.py` | `/ws/signals` | WS push temps réel |
| `routes/push.py` | `/api/push` | Web push notifications |
| `routes/trading.py` | `/api/trading` | `POST /trade` — ordre CLOB |
| `routes/trading_wallet.py` | `/api/trading/wallet` | Setup wallet + Safe |
| `routes/agents.py` | `/api/agents` | Statut agents internes |
| `routes/api_keys.py` | `/api/api-keys` | CRUD clés B2B |
| `routes/subscriptions.py` | `/api/subscriptions` | Stripe plans |
| `routes/auth.py` | `/api/auth` | register, login, google OAuth, me, logout |
| `routes/portfolio_v2.py` | `/api/portfolio` | Positions actives + résolues + KPIs |
| `routes/performance_v2.py` | `/api/performance` | Stats utilisateur + plateforme |
| `routes/quota.py` | `/api/me` | Quota daily signaux |
| `routes/sources.py` | `/api/sources` | Registre de sources |
| `routes/b2b.py` | `/api/v1` | Export bulk, webhooks B2B |
| `routes/telegram_webhook.py` | `/api/telegram` | Webhook bot Telegram |
| (racine app routes) | `/api/signals`, `/api/events`, `/api/markets` | Feed public côté client |

**Middleware global** :
- CORS configuré pour `localhost:3000` + domaine prod
- Rate limiting
- API Key auth (header `X-API-Key`) pour routes B2B
- JWT auth (header `Authorization: Bearer`) pour routes utilisateur

---

## 13. Frontend — pages & routes

Racine : `frontend/src/App.tsx`. Toutes les pages **lazy-loaded**.

### 13.1 Pages publiques

| Route | Fichier | Contenu |
|---|---|---|
| `/` | `Homepage.tsx` | Landing marketing, hero, demo animée, testimonials, pricing teaser |
| `/pricing` | `Pricing.tsx` | Tableau prix (toggle monthly/yearly) |
| `/faq` | `Faq.tsx` | FAQ en accordions |
| `/signal-variants` | `SignalVariants.tsx` | Showcase dev des variantes de SignalCard |
| `/login` | `Login.tsx` | Email/password + Google Credential API |
| `/signup` | `Signup.tsx` | Inscription + choix plan |

### 13.2 Pages protégées (RequireAuth + RequireOnboarding)

| Route | Fichier | Contenu |
|---|---|---|
| `/welcome` | `Welcome.tsx` | Onboarding 4 questions profil |
| `/signals` | `Signals.tsx` | **Feed principal** — filtres, tri, recherche, quota daily |
| `/signals/:id` | `SignalDetail.tsx` | **Détail signal** — hero, `WhyThisMatters`, `SignalTimeline`, `SourcesList`, `OrderForm` |
| `/portfolio` | `Portfolio.tsx` | Positions actives + historique + KPIs + export CSV |
| `/performance` | `Performance.tsx` | Winrate, gains, breakdown catégories (Recharts) |
| `/apprendre` | `Apprendre.tsx` | Guide éducatif (index) |
| `/apprendre/:slug` | `LearnSection.tsx` | Section éducative individuelle |
| `/settings` | `Settings.tsx` | Préférences, profil, trial, subscription |

**Guards** :
- `<RequireAuth>` — redirige vers `/login` si pas de token
- `<RequireOnboarding>` — force `/welcome` sauf routes exemptées (`/`, `/welcome`, `/login`, `/signup`, `/pricing`, `/signal-variants`)

---

## 14. Frontend — composants & data layer

### 14.1 Composants par dossier

**`components/ui/`** — design system
- `Button`, `Input`, `Logo`, `Skeleton`, `FilterPill`, `PaywallChip`, `PaywallOverlay`, `CoachMark`, `InfoTooltip`, `ChartSkeleton`, `KPIStatSkeleton`

**`components/signals/`**
- `SignalCard` / `SignalCardSkeleton` / `SignalCardVariants`
- `OrderForm` (25KB — plus gros composant du front, gère sizing + wallet + fallback manuel)
- `ManualPositionModal`, `PoweredByPolymarket`, `badges.tsx`
- **Axis-A (traçabilité)** : `WhyThisMatters`, `SourcesList`, `SignalTimeline`
- Tests : `__tests__/SignalTimeline.test.tsx`, `SourcesList.test.tsx`, `WhyThisMatters.test.tsx`

**`components/portfolio/`**
- `PositionCard` / `PositionCardSkeleton`
- `KPIStat` / `KPIStatSkeleton`
- `HistoryRow`, `LifeBar`, `SourceBadge` (native/manual)

**`components/layout/`**
- `AppShell` (18.5KB) — sidebar, mobile menu, trial/offline banner, toast viewport
- `PublicNav`, `Footer` (marketing)
- `AuthShell` (login/signup wrapper)
- `TrialBanner`, `EndOfTrialModal`, `OfflineBanner`
- `PreferenceToggles` (langue/devise)

**`components/auth/`** — `RequireAuth`
**`components/homepage/`** — `AnimatedSignalDemo`
**`components/learn/`** — `LearnContent`, `LearnVisuals`, `sections.tsx`
**`components/trading/`** — `WalletSetupModal`
**`components/modals/`** — `ConfirmDeleteAccountModal`

### 14.2 Data layer

**`lib/api/client.ts`** — wrapper fetch
- Base URL : `VITE_API_URL` ou `/api`
- Header JWT depuis `localStorage.foresight.token`
- Classe `ApiError` (status + body)
- `apiGet<T>`, `apiPost<T>`, `apiPut<T>`, `apiDelete<T>`

**Modules API** :
- `auth.ts` — register, login, google, logout, me (dédup 30s)
- `portfolio.ts` — positions + résolues + KPIs
- `trading.ts` — POST trade au CLOB
- `performance.ts` — stats user + plateforme
- `subscriptions.ts` — Stripe
- `quota.ts` — quota daily
- `wallet.ts` — status wallet/Safe

**Hooks** (`hooks/`) :
- `useAuth` — état réactif, dédup, multi-tab via `storage` event
- `useRemotePositions` — React Query `/portfolio`
- `usePerformance` — React Query `/performance`
- `useCountUp` — animation incrémentielle
- `useWalletSetup` — Wagmi + Safe setup

### 14.3 Types domaine (`types/signal.ts`)

- `Signal` — id, category, question, direction (YES/NO), marketProbability, windowHours, score, scoreLabel, confidence, urgency, tradability, catalyst, facts[], sources[], reasoning, detailedSources[], timeline[]
- `Position` — signalId, signal, direction, entryPrice, currentPrice, status (tenir/surveiller/vendre), lifePercent, estimatedGain, stake, resolved, correctPrediction, source (native/manual)
- `OrderDraft`, `PerformanceStats`, `UserProfile`, `UserPreferences`, `LearnSection`

### 14.4 Styling

- **Tailwind** avec palette custom : obsidian (950-600), brand mint (#0BE0A6), signal yes/no/amber/alert, tier 1/2/3, ink (default/muted/dim)
- Dark mode `class` strategy
- Typo : Satoshi (display) / Inter (sans) / JetBrains Mono
- Animations custom : fade-up, pulse-dot, scan, shimmer, marquee
- Focus ring WCAG AA

---

## 15. Configuration clé

Source unique : `app/core/config.py` (pydantic-settings).

### 15.1 Seuils signaux

| Setting | Défaut | Rôle |
|---|---|---|
| `signal_score_threshold` | 55 | Score min pour signal actionnable |
| `signal_min_cosine_score` | 0.52 | Similarité sémantique min |
| `hard_exclusion_spread` | 0.15 | Spread max (15¢) |
| `hard_exclusion_ambiguity` | 0.80 | Ambiguïté LLM max |
| `hard_exclusion_min_specificity` | 0.4 | Spécificité LLM min |
| `signal_tradeable_yes_min` | 0.05 | Prix YES min |
| `signal_tradeable_yes_max` | 0.95 | Prix YES max |

### 15.2 Retrieval & clustering

| Setting | Défaut |
|---|---|
| `top_k_markets` | 10 |
| `rrf_k` | 60 |
| `llm_impact_max_candidates` | 3 |
| `clustering_cosine_threshold` | 0.75 (clusterer) / 0.82 (code effective) |
| `clustering_time_window_minutes` | 120 |
| `min_articles_per_event` | 1 |

### 15.3 Intervalles

| Setting | Défaut |
|---|---|
| `rss_poll_interval_seconds` | 90 |
| `market_refresh_interval_seconds` | 900 |
| `embedding_batch_interval_seconds` | 120 |
| `build_events_interval_seconds` | 300 |
| `signal_event_max_age_hours` | 6.0 |
| `signal_dedupe_window_hours` | 72.0 |

---

## 16. Développement & tests

### 16.1 Commandes

```bash
# Démarrer tout (docker-compose)
make dev

# Local Python
make dev-local       # uvicorn --reload
make install         # uv pip install
make test            # pytest
make lint            # ruff
make migrate         # alembic upgrade head

# Frontend
cd frontend
npm run dev          # Vite :3000
npm run build        # tsc + vite build
npm run lint         # ESLint 0 warnings
npm run test         # Vitest
```

### 16.2 Tests

**Backend** — `pytest` dans `tests/`
- Couverture : scoring, signal_builder, retrieval, event_engine, polymarket clients, outcomes

**Frontend** — Vitest + Testing Library + jsdom
- `SignalTimeline.test.tsx`, `SourcesList.test.tsx`, `WhyThisMatters.test.tsx`
- Setup : `src/test-setup.ts` (imports `@testing-library/jest-dom`)

### 16.3 Script utile — backfill raisonnement

```bash
docker compose exec app python -m scripts.backfill_reasoning --days 7 --dry-run
docker compose exec app python -m scripts.backfill_reasoning --days 7
```

Remplit `reasoning` + `source_tier_mix` sur les signaux pré-Axis-A (voir `scripts/backfill_reasoning.py`).

---

## 17. État actuel & dette

### 17.1 Axis-A (traçabilité signaux) — DONE

Plan `docs/superpowers/plans/2026-04-23-signal-sourcing-traceability.md` — 24 tâches terminées.

Livré :
- Backend : `reasoning`, `source_tier_mix`, `llm_model_version` sur Signal
- Backend : `key_excerpt`, `relevance_score` sur EventNewsLink
- API : champs enrichis `/api/signals/:id` (detailedSources, timeline)
- Frontend : `WhyThisMatters`, `SourcesList`, `SignalTimeline` intégrés dans `/signals/:id`
- Tests unitaires frontend

### 17.2 Audit précision signaux — findings

Sur données historiques (pipeline dark depuis 6 jours) :

- **Winrate global T+24h : 46-48%** — sous le hasard
- **Bucket score 75-89** :
  - BUY_NO : n=22, winrate **72.7%**, avg |move| 12%, 14/22 bougent ≥5%
  - BUY_YES : n=24, winrate **29.2%**, avg |move| 17%, 15/24 bougent ≥5%
- Asymétrie directionnelle forte et magnitude substantielle des deux côtés → biais LLM "pro-YES" sur marchés hésitants

### 17.3 Plan de collecte propre (en cours)

- Pipeline à relancer (dark 6 jours)
- Vérifier captures outcomes (T+5m/15m/1h/24h actifs)
- Gel du code scoring/LLM/prompt pendant ~10 jours
- Re-audit sur dataset 3-4× plus grand
- Ensuite : décider overlay contrariant BUY_YES vs prompt engineering vs pivot structurel

### 17.4 Dette connue

- Container `/app/signal/` shadowait la lib stdlib `signal` (résolu — dirs supprimés du volume)
- Task 23 (Playwright E2E) formellement reportée — dépendance non installée
- Pas d'A/B testing framework pour tester variantes scoring
- Pas de système de feature flags

---

## Annexe — Arborescence condensée

```
polymarket-ai/
├── app/
│   ├── api/                # FastAPI (main.py + routes/*)
│   ├── agents/             # Agents internes (telegram, daily brief)
│   ├── core/               # config, logging, metrics
│   ├── db/                 # models.py, database.py
│   ├── event_engine/       # simple_clusterer, event_builder
│   ├── ingestion/          # RSS, X, WorldNews, GDELT
│   ├── llm/                # openai_client, reasoning_analyzer, impact_analyzer
│   ├── polymarket/         # gamma_client, clob_client
│   ├── processing/         # cleaner, ner, classifier
│   ├── retrieval/          # hybrid_search, vector_retriever, bm25_index
│   ├── scoring/            # feature_builder, heuristic_scorer
│   ├── signal/             # signal_builder, signal_mapper, direction_eval
│   ├── telegram/           # bot handlers
│   ├── trading/            # builder_client, position_sync
│   └── workers/            # celery_app + tasks_*.py (6 fichiers)
├── frontend/
│   └── src/
│       ├── pages/          # 15 pages
│       ├── components/     # ui/ signals/ portfolio/ layout/ auth/ etc.
│       ├── hooks/          # useAuth, useRemotePositions, usePerformance…
│       ├── lib/            # api/, i18n, trial, wagmiConfig, userPreferences
│       ├── types/          # signal.ts (domaine)
│       ├── data/           # mocks
│       ├── locales/        # fr/, en/
│       └── styles/         # globals.css
├── prompts/                # 5 prompts LLM
├── scripts/                # backfill_reasoning.py + autres
├── alembic/                # migrations
├── tests/                  # pytest
├── docker-compose.yml      # 12 services
├── Dockerfile
├── pyproject.toml          # deps Python
└── Makefile
```

---

**Dernière mise à jour :** 2026-04-23
**Mainteneur :** @polyedge2026
