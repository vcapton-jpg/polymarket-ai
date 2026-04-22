# Signal - Prediction Market Intelligence Platform

Real-time signals for prediction markets. Know before the market does.

## What is Signal?

Signal is an intelligent prediction market intelligence platform that monitors world events in real-time, detects when a breaking news story creates a mispriced prediction market, and delivers a clear, actionable trading signal before the market corrects itself.

## Features

- **Real-time Ingestion**: RSS feeds, X (Twitter), World News API
- **Event Detection**: Clustering and NER for news → events
- **Hybrid Retrieval**: Vector + BM25 search
- **LLM Analysis**: GPT-4o-mini for market impact
- **Scoring**: Multi-factor heuristic scoring
- **WebSocket**: Real-time signal push

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key
- (Optional) Telegram Bot token

### 1. Clone and Setup

```bash
git clone https://github.com/your-repo/signal.git
cd signal
cp .env.example .env
```

### 2. Configure

Edit `.env` with your API keys:

```
OPENAI_API_KEY=sk-your-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot
TELEGRAM_CHAT_ID=your-chat-id
```

### 3. Run

```bash
make dev
```

This starts all services:
- FastAPI app on http://localhost:8000
- Frontend on http://localhost:3000
- PostgreSQL on port 5432
- Redis on port 6379
- Celery worker

### 4. Access

- Dashboard: http://localhost:3000
- API: http://localhost:8000/api/health

## Development

### Install Dependencies

```bash
make install
```

### Run Locally

```bash
make dev-local
```

### Tests

```bash
make test
```

### Lint

```bash
make lint
```

## Architecture

```
+-------------------------------------------------------------+
|                   Ingestion                                  |
|  RSS Scraper | X Scraper | WorldNews Client                |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                  Processing                                 |
|  Cleaner | NER | Classifier | Embeddings                    |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|               Event Engine                                 |
|  Clustering | Event Builder                                |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                 Retrieval                                   |
|  Vector | BM25 | Hybrid Search                             |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                   LLM                                       |
|  Summarizer | Impact Analyzer                              |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                  Scoring                                    |
|  Features | Heuristic Scorer                             |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                  Signal                                     |
|  Signal Builder | Outcomes Tracking                        |
+-------------------------------------------------------------+
```

## API Endpoints

All endpoints live under `/api`. Everything but `/api/health` returns JSON.
V2 endpoints (prefixed `V2` below) emit camelCase shapes matching
[`frontend/src/types/signal.ts`](frontend/src/types/signal.ts) so the client
consumes them with zero mapping.

### Public

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (+ worker status). |

### Signals (V2)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/signals` | GET | List signals. Filters: `category`, `min_score`, `direction` (YES/NO), `limit`, `offset`. |
| `/api/signals/:id` | GET | Full signal detail with `facts[]` + `sources[]`. |
| `/api/markets` | GET | List markets (legacy shape). |
| `/api/events` | GET | List events (legacy shape). |
| `/ws/signals` | WS | Real-time push for new signals. |

### Auth

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | `{ email, password, plan=free|pro }` → JWT. Pro sets `trial_ends_at = now+7d`. |
| `/api/auth/login` | POST | `{ email, password }` → JWT. |
| `/api/auth/google` | POST | `{ credential }` (Google ID token) → JWT. |
| `/api/auth/logout` | POST | Best-effort invalidate. |
| `/api/auth/me` | GET | Rich user blob (plan, trial, preferences, profile). Auto-downgrades expired Pro trials. |
| `/api/auth/me/profile` | PUT | Upsert onboarding profile (Welcome page). |
| `/api/auth/me/preferences` | PUT | Upsert currency/language/notif preferences (Settings). |

### Portfolio + performance (V2)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/portfolio` | GET | Authenticated user's positions + resolved history + KPIs, in the V2 `Position` shape. |
| `/api/performance/me` | GET | `PerformanceStats` bundle (user + platform + charts). |

### Subscriptions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/subscriptions/plans` | GET | Static plan catalog. |
| `/api/subscriptions/current` | GET | Authenticated plan + trial + card_attached. |
| `/api/subscriptions/checkout` | POST | `{ plan: pro|trader, cycle: monthly|annual }` → Stripe hosted URL. |
| `/api/subscriptions/portal` | POST | Stripe Customer Portal URL. |
| `/api/subscriptions/webhook` | POST | Stripe webhook (checkout.session.completed flips `card_attached` + clears trial). |

### Quota + trading

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/me/quota` | GET | Daily signal counter `{used, limit, resets_at}` (Redis). Pro → `limit=-1`. |
| `/api/me/quota/consume` | POST | Server-authoritative increment, no-op for Pro. |
| `/api/trading/trade` | POST | Place a CLOB order (Builder API). Requires signal_id when acting on a Foresight signal. |

## Frontend architecture

- **Stack**: React 18 + Vite + TypeScript, Tailwind, Radix UI, framer-motion, react-i18next (fr-first).
- **Routing**: `/` (Homepage) · `/pricing` · `/faq` · `/login` · `/signup` · `/welcome` · `/signals` · `/signals/:id` · `/portfolio` · `/performance` · `/apprendre` · `/apprendre/:slug` · `/settings`.
- **API client**: single file at [`frontend/src/lib/api/client.ts`](frontend/src/lib/api/client.ts) handles `VITE_API_URL` fallback and Bearer injection.
- **Auth**: JWT in `localStorage.foresight.token`. `useAuth()` hydrates from `/api/auth/me` on mount; trial/plan stay in sync without polling.
- **Mocks**: `VITE_USE_MOCKS=1` forces the bundled demo datasets (useful offline or for UI reviews). Defaults to API-first with a visible error banner when the backend is unreachable.

### Frontend commands

```bash
cd frontend
npm install                 # first-run only
npm run dev                 # Vite on :3000, proxying /api to localhost:8001
npm run build               # tsc + vite build into dist/
npm run lint
```

## Tech Stack

- **Backend**: Python, FastAPI, Celery, SQLAlchemy (async)
- **Database**: PostgreSQL 16 + pgvector
- **Queue / cache**: Redis 7
- **AI**: OpenAI GPT-4o-mini, spaCy
- **Frontend**: React 18, TypeScript, Vite 6, Tailwind 3, Radix UI

## Rules (Non-Negotiable)

1. NEVER call LLM on raw article - always processed event
2. ONE LLM call per pipeline (event + batch top-10)
3. Measure ingestion_lag_seconds from day 1
4. LOG ALL signals even score < 60 - critical for ML training
5. Create signal_outcomes from the very first signal
6. Do NOT train LightGBM before 1000 labeled signals
7. Validate retrieval manually BEFORE enabling LLM
8. Heuristic weights are hypotheses - must be recalibrated
9. Re-index embeddings ONLY if retrieval text changes
10. Use ingestion_date NOT publish_date for freshness_factor

## License

MIT

