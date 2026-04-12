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

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/health | GET | Health check |
| /api/signals | GET | List signals |
| /api/signals/:id | GET | Signal detail |
| /api/markets | GET | List markets |
| /api/events | GET | List events |
| /api/analytics/accuracy | GET | Accuracy stats |
| /api/analytics/costs | GET | LLM costs |
| /ws/signals | WS | Real-time signals |

## Tech Stack

- **Backend**: Python, FastAPI, Celery, SQLAlchemy
- **Database**: PostgreSQL 16, pgvector
- **Queue**: Redis
- **AI**: OpenAI GPT-4o-mini, spaCy
- **Frontend**: React, TypeScript, Vite

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

