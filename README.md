# Foresight

> Know before the market does — Foresight surfaces the news that just made a Polymarket prediction-market contract wrong, and lets you act on it in one click.

![Status](https://img.shields.io/badge/status-production--ready-blue) · French first, English-ready · USD primary, EUR secondary

## Status

The pipeline is **production-ready**: full chain live in dev (ingestion →
clustering → LLM impact → heuristic score → two-layer dedupe → signal
broadcast → Polymarket Builder order), runbook + preflight check shipped
for the VPS cutover ([`scripts/deploy/`](./scripts/deploy/)). No public
URL pinned yet — the domain is still being chosen.

Recent work (since the May 2026 audit cycle):

- **8 PRs closed a 6-day OOM outage** (#37–#44) — asyncpg cross-loop
  bug, OpenAI timeouts, `NullPool`, worker recycling, SQLAlchemy echo
  trigger, NER singleton.
- **9 PRs hardened security + perf** (#45–#56) — Pydantic trade
  validation, Telegram webhook auth, JWT secret gate, ghost HNSW
  index drop, missing FK indexes, N+1 storms killed, LLM wrapper
  singletons, shared httpx client.
- **5 PRs cleaned architecture + tests** (#57–#62) — layering, hooks,
  dead code drop, Celery `send_task`, OpenAPI codegen, migration
  safety runbook.
- **4 PRs fixed live bugs + shipped deploy infra** (#63–#66) —
  thematic dedup (closed live duplicate observed in prod-like dev),
  production deploy runbook + preflight, README + `.env.example` sync.

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
├── alembic/              30 DB migrations (Postgres + pgvector) + MIGRATION_SAFETY.md runbook
├── tests/                104 test files (pytest, unit + integration)
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
├── docker-compose.yml    13 services (db, redis, app, beat, 7 workers, frontend, rsshub)
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

**Infra:** Docker Compose (13 services), Cloudflare tunnel for mobile dev. Repo on GitHub; `.gitlab-ci.yml` is legacy and not currently exercised — CI re-wiring (GitHub Actions) is a follow-up.

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
npm run gen:api        # regenerate src/types/api.generated.ts from /openapi.json
npx vitest             # tests (no `npm test` script defined yet)

# Cleanup
make clean             # docker compose down -v + clear __pycache__
```

## Production deploy

Full runbook in [`scripts/deploy/README.md`](scripts/deploy/README.md): VPS
provisioning (Hetzner CPX31 ~€14/mo), Caddy reverse proxy + automatic
Let's Encrypt TLS, daily Postgres backups, systemd auto-start, and a
pre-flight check that refuses to boot with default secrets.

```bash
# Before pointing a domain at the VPS — validate the .env
bash scripts/deploy/preflight-check.sh
```

The pre-flight catches the failure modes the audit cycle closed (default
JWT secret, weak DB password, empty Telegram webhook secret,
`DB_ECHO=true`, wildcard CORS in production, leaked OpenAI key, stale
`.env.backup*` files in repo root). Output is safe to share — no secret
values are printed.

## Database migrations

Schema is owned by Alembic; `alembic upgrade head` runs in the API
container's entrypoint before uvicorn boots. New migration writers
should follow [`alembic/MIGRATION_SAFETY.md`](alembic/MIGRATION_SAFETY.md)
(copy-paste templates for index/NOT-NULL/FK/drop, the
`CHECK NOT VALID + VALIDATE` pattern, and the past patterns to avoid).

## Team

- **Vadim Capton** — frontend & product · [vcapton-jpg](https://github.com/vcapton-jpg)
- **Emmanuel Abbruzzese** — backend co-dev

## Branch & release strategy

- `main` — production. Always deployable. All PRs are squash-merged so
  the history stays linear; feature branches are deleted from the remote
  after merge.
- `archive/*` — frozen branches preserved as recoverable points. Recover
  with `git checkout archive/<name>-YYYY-MM-DD`.

Workflow:
1. Branch off `origin/main` (`git checkout -b feat/<short-name> origin/main`)
2. Open a PR; squash-merge into `main`
3. Local + remote feature branches are pruned afterward — `git fetch
   --prune origin` keeps the local view tidy.

## License

Private — Albert School project.
