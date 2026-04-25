# Onboarding — New Developer in 30 Minutes

This is the "Day 1, Hour 1" guide. Three hours after reading this, you should be productive on the codebase.

If you have **only 5 minutes**, read just **§1 Day-1 Hour-1**, then get the dev server up and start touching code. Read the rest as you need it.

---

## §1 — Day 1, Hour 1: clone, install, run

Goal: a working dev server, plus the API responding to a curl.

```bash
# 1. Clone
git clone https://github.com/vcapton-jpg/polymarket-ai.git
cd polymarket-ai

# 2. Env
cp .env.example .env
# Open .env and fill at minimum:
#   - OPENAI_API_KEY (required, for impact + embeddings)
#   - POLYMARKET_PRIVATE_KEY (only if you'll exercise trading paths)
#   - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (only if you want push alerts)

# 3. Backend (everything in Docker)
make install        # uv sync + spaCy en_core_web_lg model
make dev            # docker compose up — db, redis, app, beat, 6 workers, frontend, rsshub

# 4. Wait ~30s for the stack to settle, then sanity check:
curl http://localhost:8001/api/health
# → {"status":"ok"}

# 5. Frontend dev (faster HMR than the Dockerized one)
cd frontend
npm install
npm run dev         # → http://localhost:5173
```

If `make dev` complains about `POLYMARKET_PRIVATE_KEY` or other secrets, comment them out in `docker-compose.yml`'s env list — they're not required to boot.

**You're done with Hour 1 when:** `curl /api/health` returns ok AND you see the Foresight UI at <http://localhost:5173>.

---

## §2 — Day 1, Hour 2: the tour (8 files to read)

These are the load-bearing files. After this hour, you'll know where things live.

| File | Why it matters |
|---|---|
| **[`docker-compose.yml`](../docker-compose.yml)** | The service topology in one glance — db, redis, 6 workers, beat, app, frontend, rsshub. Read top to bottom. |
| **[`app/api/main.py`](../app/api/main.py)** | FastAPI entry point. Mounts every router, adds CORS + auth middleware, defines the lifespan. |
| **[`app/db/models.py`](../app/db/models.py)** | All SQLAlchemy models (~30 tables). Skim the class names; don't memorize columns. |
| **[`app/workers/celery_app.py`](../app/workers/celery_app.py)** | Celery config + the 18+ beat schedule entries. Tells you what runs and when. |
| **[`app/signal/signal_builder.py`](../app/signal/signal_builder.py)** | The product's brain — sync `SignalBuilder.build_signal` (prod path) + async `build_signal()` (legacy). |
| **[`app/scoring/heuristic_scorer.py`](../app/scoring/heuristic_scorer.py)** | The scoring formula — strength × 0.75 + trade_quality × 0.25. See [DEC-012](./decisions.md#dec-012). |
| **[`frontend/src/App.tsx`](../frontend/src/App.tsx)** | React router + auth gating. Every page is reachable from here. |
| **[`frontend/src/pages/Signals.tsx`](../frontend/src/pages/Signals.tsx)** | The flagship page — fetches the signal list, renders the cards. Mirrors how all data-driven pages work. |

Open each in your editor, scroll once, close. You're not reading for comprehension — you're building a mental map.

---

## §3 — Day 1, Hour 3: read these 3 docs

Now that you've seen real code, the docs make sense.

1. **[`docs/architecture.md`](./architecture.md)** (~400 lines) — the system in 10,000 feet. Diagram + components + data flow.
2. **[`docs/decisions.md`](./decisions.md)** (~330 lines, 16 ADRs) — *why* we made every load-bearing choice. Especially DEC-005 (legal language), DEC-008 (Builder Program), DEC-013 (4 baselines).
3. Pick the one matching your role:
   - Frontend → **[`docs/frontend.md`](./frontend.md)** (~510 lines)
   - Backend → **[`docs/backend.md`](./backend.md)** (~320 lines)

**Don't read [`BLUEPRINT.md`](../BLUEPRINT.md) yet.** It's 846 lines of dense French and exists to settle disputes when the focused docs aren't enough. Save it for Day 2+.

---

## §4 — Required references (always open in a tab)

- **[`frontend/src/docs/voice-guide.md`](../frontend/src/docs/voice-guide.md)** — copywriting voice, French typography, CTA conventions, Polymarket partnership language. **Mandatory** if you write any user-facing string.
- **[`docs/audit/ISSUES_BACKLOG.md`](./audit/ISSUES_BACKLOG.md)** — historical audit issues, partly resolved. Useful to understand the "why" behind seemingly random refactors.
- **[`docs/runbooks/`](./runbooks/)** — read these only when you're about to promote a v2 variant to prod (`promote_embeddings_v2.md`, `promote_heuristic_candidate.md`, etc.).

---

## §5 — Patterns to follow when adding code

### Backend
- **New endpoint** → create `app/api/routes/<name>.py`, define `router = APIRouter()`, register in `app/api/main.py`. Pydantic schema in `app/api/schemas/`.
- **New Celery task** → `app/workers/tasks_<area>.py` decorated with `@celery_app.task`. Module is autodiscovered. Add to a beat entry if it should run on a schedule.
- **New SQLAlchemy model** → edit `app/db/models.py`, then `make migrate-new msg="add foo"`. Never edit `Base.metadata` at runtime — Alembic owns the schema (DEC-014).
- **TDD always** — write the failing test first, then the implementation. See `tests/unit/` for the patterns.
- **Pre-commit checks** → `make lint && make test` before pushing.

### Frontend
- **New page** → `frontend/src/pages/MyPage.tsx`, wire route in `App.tsx`. Auth wrapper if needed.
- **New component** → `frontend/src/components/<area>/MyComponent.tsx`. Default export, props typed via interface.
- **All user strings → `t()`** — i18n is mandatory, no hardcoded French. See [`docs/frontend.md` §4](./frontend.md#4-key-conventions-mandatory).
- **All money → `formatCurrency()`** — USD primary, EUR secondary (DEC-003).
- **Tailwind tokens, never raw hex.** Use `obsidian-900`, `ink`, etc. — defined in `tailwind.config.ts`.
- **French typography** — NBSP before `:`, `;`, `?`, `!`, `»` ; curly apostrophes (`'`) ; guillemets (`«` `»`). Voice guide enforces.

---

## §6 — How to ask questions / communicate

| Topic | Channel |
|---|---|
| Architecture / "why this choice" | Check `docs/decisions.md` first → if not there, ask Vadim |
| Frontend / UX | Vadim Capton (frontend + product owner) |
| Backend / scoring / measurement | Emmanuel Abbruzzese (co-dev) |
| Production incident | Vadim, by phone |
| Reading a chantier you didn't write | The plan + spec are in `docs/plans/` and `docs/specs/` — start there |

When in doubt, **read first, ask second**. The docs are dense for a reason. If the docs disagree with the code, **the code wins** — open a PR fixing the doc.

---

## §7 — Red flags, don't repeat these mistakes

These have all bitten us; the audit reports + post-audit fixes catalogue the rest:

- **Don't `Base.metadata.create_all` in lifespan** — Alembic owns the schema (DEC-014). The recent CORS + lifespan PR enforces this.
- **Don't hardcode CORS `*`** — explicit per-env allow-list via `app/api/cors.py` (DEC-015).
- **Don't trust `if x else None`** — use `is not None` for any numeric column where 0.0 is legitimate (e.g. `last_trade_price`, `spread`, `ambiguity_score`). The post-audit fix on `tasks_scoring._build_market_data` catalogues this.
- **Don't invent baseline predictions** — abstain (`None, None`) at equality boundaries (DEC-016). News_sentiment, market_price (at 0.5), and momentum (at Δ=0) all do this now.
- **Don't read `BLUEPRINT.md` cover-to-cover on Day 1.** It will overwhelm you. Use it as a reference, not a tutorial.

---

## §8 — Cheatsheet

| Want to | Run |
|---|---|
| Boot everything | `make dev` |
| Run backend tests | `make test` |
| Run a single test | `docker compose exec -T app pytest tests/unit/path::test_name -v` |
| Apply a new migration | `make migrate` |
| Create a migration | `make migrate-new msg="add foo"` |
| Frontend dev server | `cd frontend && npm run dev` |
| Frontend build | `cd frontend && npm run build` |
| Tail worker logs | `make logs` |
| Reset everything | `make clean` |
| Check beat schedule | `grep -A2 "_beat_schedule" app/workers/celery_app.py` |
| Open prod database | `docker compose exec -T db psql -U postgres signal` |

---

## §9 — Once you've shipped your first PR

You should now:

- Have read `docs/architecture.md`, `docs/decisions.md`, and the role-specific doc end-to-end
- Know how to add an endpoint, a task, a page, a component
- Be writing TDD-first
- Be respecting the i18n + currency + typography rules
- Skim `BLUEPRINT.md` once, then keep it as a reference for the dense parts

Welcome aboard. The product is shipping; let's keep it that way.
