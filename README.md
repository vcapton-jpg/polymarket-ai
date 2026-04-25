# Foresight

> Know before the market does — Foresight surfaces the news that just made a Polymarket prediction-market contract wrong, and lets you act on it in one click.

[![Status](https://img.shields.io/badge/status-production-green)](https://getforesight.io) · Live at **[getforesight.io](https://getforesight.io)** · French first, English-ready · USD primary, EUR secondary

## Status

- **V2** shipped (production) — full pipeline live: ingestion → clustering → LLM impact → heuristic score → signal → broadcast → Polymarket Builder order
- **Chantiers #1-#6** + post-audit fixes shipped on `main` (measurement layer, sourcing audit, embeddings v2, ranking tuning, heuristic validation, clustering hardening, scoring/CORS/lifespan hardening)
- **V3** documentation pass in progress (this README + `docs/`)

## Quick start

```bash
# 1. Clone + bootstrap
git clone https://github.com/vcapton-jpg/polymarket-ai.git
cd polymarket-ai
cp .env.example .env   # then fill in OPENAI_API_KEY at minimum

# 2. Backend (Docker — runs Postgres+Redis+API+workers+frontend together)
make install           # uv sync + spaCy model
make dev               # docker compose up

# 3. Frontend dev (faster HMR — outside Docker)
cd frontend && npm install && npm run dev    # → http://localhost:5173
```

API at `http://localhost:8001/api`, frontend at `http://localhost:5173`. The API container runs `alembic upgrade head` before uvicorn boots — no manual schema setup.

## Project structure

```
polymarket-ai/
├── frontend/             React 18 + TS + Vite + Tailwind 3 SPA
├── app/                  Python backend (FastAPI + Celery + scoring/measurement)
├── alembic/              25 DB migrations (Postgres + pgvector)
├── tests/                pytest (~376 unit + integration)
├── prompts/              Versioned LLM prompts (impact, reasoning, summary)
├── scripts/              One-shot ops (backfills, eval, tuning)
├── docs/                 Documentation (this is where you go next)
│   ├── architecture.md       10,000-foot view of the system
│   ├── frontend.md           Frontend dev guide
│   ├── backend.md            Backend dev guide
│   ├── decisions.md          16 ADRs (product + technical)
│   ├── onboarding-new-dev.md 30-min ramp-up for new contributors
│   ├── plans/                Chantier execution plans
│   ├── specs/                Chantier design specs
│   ├── runbooks/             Promotion runbooks (v2 variants → prod)
│   └── audit/                Historical audit reports
├── data/                 Runtime inboxes (X scraper)
├── static/               Apple Pay domain verification
├── docker-compose.yml    12 services (db, redis, app, beat, 6 workers, frontend, rsshub)
├── Dockerfile            Backend image
├── Makefile              Dev helpers (install/dev/test/lint/migrate/seed)
├── pyproject.toml        Python deps (uv)
├── alembic.ini           Migration config
└── BLUEPRINT.md          846-line French technical reference (canonical, dense)
```

> **Why `app/` and not `backend/`?** Convention from the FastAPI scaffold. Renaming would break ~3000 imports for zero functional benefit. See [`app/README.md`](./app/README.md).

## Tech stack

**Frontend:** React 18, TypeScript, Vite 6, Tailwind 3, Framer Motion, react-router-dom · French-first via `react-i18next`

**Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic, Celery, Postgres 16 + pgvector, Redis, OpenAI gpt-4o-mini + text-embedding-3-small · `uv` for dep management

**Infra:** Docker Compose (12 services), GitLab CI, Cloudflare tunnel for mobile dev

## Documentation

| You are… | Read |
|---|---|
| New to the project | [`docs/onboarding-new-dev.md`](./docs/onboarding-new-dev.md) — 30 minutes to productive |
| Looking at the system as a whole | [`docs/architecture.md`](./docs/architecture.md) |
| Building a frontend feature | [`docs/frontend.md`](./docs/frontend.md) |
| Building a backend feature | [`docs/backend.md`](./docs/backend.md) |
| Wondering "why this choice?" | [`docs/decisions.md`](./docs/decisions.md) — 16 ADRs |
| Promoting a v2 variant to prod | [`docs/runbooks/`](./docs/runbooks/) |
| Reading a chantier's plan or spec | [`docs/plans/`](./docs/plans/), [`docs/specs/`](./docs/specs/) |
| Auditing past issues | [`docs/audit/`](./docs/audit/) |
| Anything else, deep dive | [`BLUEPRINT.md`](./BLUEPRINT.md) — French, exhaustive |

## Polymarket Builder Program

Foresight is a Polymarket Builder Program partner. Orders execute **gaslessly** from the user's Polymarket Safe wallet, with `builderCode` attribution. Caveat: the Builder Program does **not** provide regulatory cover in France (Polymarket has been blocked by the ANJ since end-2024). See [`docs/specs/2026-04-22-polymarket-wallet-link-design.md`](./docs/specs/2026-04-22-polymarket-wallet-link-design.md).

## Common commands

```bash
# Backend
make dev               # docker compose up
make dev-local         # uvicorn outside Docker (port 8000)
make test              # pytest -v
make lint              # ruff check + format
make migrate           # alembic upgrade head
make migrate-new msg="…"   # generate a new migration
make seed              # populate sources table

# Frontend (from frontend/)
npm run dev            # vite dev server (port 5173)
npm run build          # production build
npm run lint           # eslint + tsc --noEmit
npx vitest             # tests (no `npm test` script defined yet)

# Cleanup
make clean             # docker compose down -v + clear __pycache__
```

## Team

- **Vadim Capton** — frontend & product · [vcapton-jpg](https://github.com/vcapton-jpg)
- **Emmanuel Abbruzzese** — backend co-dev

## Branch & release strategy

- `main` — production. Always deployable.
- `pivot/learn-and-trade` — current working branch (kept in sync with main during the V3 cleanup).
- `archive/*` — frozen branches preserved as tags. Recover with `git checkout archive/<name>-2026-04-25`.

Branches retired in the 2026-04-25 V3 cleanup (recoverable from tags `archive/dev-2026-04-25`, `archive/feat-v2-frontend-2026-04-25`, `archive/main-pre-v3-2026-04-25`):
- `dev` (12 commits, all in main)
- `feat/v2-frontend` (73 commits, all in main)
- `a`, `claude/jovial-benz-dc3565` (no unique work)

## License

Private — Albert School project.
