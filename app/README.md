# Foresight — Backend

Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) + Celery + Postgres + pgvector.

> **Why not `/backend`?** This folder is named `app/` — convention kept from the FastAPI scaffold. Renaming would break 3000+ imports, the Dockerfile, `alembic.ini`, and every test for zero functional benefit. New devs: just remember `from app.x import y`.

**Full guide:** [`../docs/backend.md`](../docs/backend.md)

## Commands

```bash
make install         # uv sync + spaCy model
make migrate         # alembic upgrade head
make seed            # populate sources table
make dev             # docker compose up
make dev-local       # uvicorn outside Docker (port 8000)
make test            # pytest -v
make lint            # ruff check + format
```

## Top-level layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI routes, middleware, schemas, websocket |
| `core/` | Settings (Pydantic), config |
| `db/` | SQLAlchemy models, session factory |
| `ingestion/` | RSS, X (RSSHub), GDELT scrapers |
| `processing/` | Cleaning, simhash dedup, bucket classifier |
| `event_engine/` | News → event clustering |
| `retrieval/` | Hybrid search v1 + v2 (vector + BM25) |
| `llm/` | OpenAI client, impact analyzer, event summarizer |
| `scoring/` | Heuristic scorer (strength + trade quality) |
| `signal/` | Signal builder (sync + async paths) |
| `measurement/` | heuristic_v1 + 4 baselines, Brier, Wilson CI95 |
| `polymarket/` | CLOB client, market refresher, prices history |
| `trading/` | Order placement, positions, Builder Program |
| `telegram/` | Webhook handler + alerts |
| `workers/` | Celery tasks + beat schedule |
| `agents/` | Strategist / Analyst / Scout / Risk / Reporter agents |
| `services/` | Cross-cutting business logic (user_limits, etc.) |
| `eval/` | Eval runner + variant comparison |
| `sourcing/` | Per-signal sourcing audit (chantier #2) |
| `content/` | Static content registry |
| `scripts/` | One-shot CLI scripts |

## Quick links

- Models — [`db/models.py`](./db/models.py)
- FastAPI entry — [`api/main.py`](./api/main.py)
- Celery beat schedule — [`workers/celery_app.py`](./workers/celery_app.py)
- Scoring weights — [`scoring/weights.py`](./scoring/weights.py)
- Migrations — [`../alembic/versions/`](../alembic/versions/)
- Architecture — [`../docs/architecture.md`](../docs/architecture.md)
- Decisions — [`../docs/decisions.md`](../docs/decisions.md)
