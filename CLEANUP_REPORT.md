# Cleanup Report — Phase 1 Discovery

**Generated:** 2026-04-25
**Status:** Discovery complete — awaiting approval before any destructive operation
**Scope:** branches, root files, top-level folders

---

## ⚠️ Critical ambiguities — need your call before Phase 2

### A1. `main` is NOT production — `pivot/learn-and-trade` is

Your brief said *"main (production, keep active)"*. The git state contradicts that:

| Branch | Last commit | Commits ahead of `main` |
|---|---|---|
| `main` | 2026-04-12 (`38728be init polymarket ai project`) | 0 |
| `pivot/learn-and-trade` | 2026-04-25 (`f1edde8 fix(bucket)…`) | **224** |
| `dev` | 2026-04-17 | 12 (all also in pivot) |
| `feat/v2-frontend` | 2026-04-23 | 73 (all also in pivot) |

`main` literally hasn't been touched since the initial commit on April 12. Every shipped feature (V1 + V2 + chantiers #1–#6 + post-audit fixes) lives on `pivot/learn-and-trade`. Same picture on `origin`.

**Decision needed (pick one):**

1. **Promote `pivot/learn-and-trade` → `main`** (recommended). One fast-forward merge: `git checkout main && git merge --ff-only pivot/learn-and-trade && git push`. Tag the old `main` first (`archive/main-pre-v3-2026-04-25`) for paranoia. After this, `main` becomes the real production line and the rest of the cleanup proceeds normally.
2. **Keep `pivot/learn-and-trade` as the production branch**, retire `main`. Means changing the GitHub default branch and all CI/CD assumptions. Heavier.

Until you decide, I cannot classify `main` correctly.

### A2. `/backend` folder doesn't exist — backend code lives in `/app`

Your brief assumes the layout `frontend/` + `backend/`. Reality:

```
polymarket-ai/
├── frontend/    ← React, exists
├── app/         ← Python (FastAPI + workers + scoring + …) ← THIS is the backend
├── alembic/     ← migrations
├── tests/       ← pytest
└── …
```

There is no `/backend` directory. The Python codebase is `/app` (FastAPI + Celery workers + scoring + measurement + 25 Alembic migrations + ~83 tests passing).

**Decision needed:**

1. **Rename `app/` → `backend/`** (matches your brief, but is a massive refactor: `Dockerfile`, `docker-compose.yml`, `alembic.ini`, `pyproject.toml`, all imports `from app.…`, every test, every script, the runtime config. Estimate: 1 hour of mechanical changes + 1 hour of test-suite verification. Doable but invasive).
2. **Create an empty `backend/` stub** (your brief says "keep, even if empty/stub") and document in `docs/backend.md` that the live code is in `/app`. Trivial. Confusing for new devs.
3. **Document `/app` as the backend** in `docs/backend.md` and `README.md`, no rename. Honest, zero risk. My recommendation if you want to ship docs fast.

### A3. `CONTRIBUITING.md` is misspelled (should be `CONTRIBUTING.md`)

86-line file with V1-era contribution rules + folder structure that no longer matches reality. Three options:

1. Rename → `CONTRIBUTING.md` and rewrite to reflect current architecture.
2. Move to `_archive/` and skip having a CONTRIBUTING for now (Phase 3 docs/onboarding-new-dev.md fills the gap).
3. Move to `docs/CONTRIBUTING.md` (modernized).

---

## 1. Branch inventory

### Local branches

| Branch | Last commit | vs main | vs pivot | Classification | Rationale |
|---|---|---|---|---|---|
| **`main`** | 2026-04-12 (init) | — | -224 | **PENDING A1** | Stuck at init commit — see A1 above |
| **`pivot/learn-and-trade`** ⭐ | 2026-04-25 (HEAD) | +224 | — | **KEEP ACTIVE** | Current working branch. All V1+V2+chantiers work lives here |
| `dev` | 2026-04-17 | +12 | 0 | **ARCHIVE → DELETE** | Fully merged into pivot/learn-and-trade (0 unique commits). Pre-pivot frontend OAuth work is preserved in pivot's history. |
| `feat/v2-frontend` | 2026-04-23 | +73 | 0 | **ARCHIVE → DELETE** | Fully merged into pivot/learn-and-trade (0 unique commits). V2 frontend redesign is in pivot's history. |
| `a` | 2026-04-25 | +224 | 0 | **DELETE** (no archive) | Identical to `pivot/learn-and-trade` (0 commits in either direction). Looks like a typo/throwaway local branch — no unique work to preserve. Local-only (not on origin). |
| `claude/jovial-benz-dc3565` | 2026-04-12 | 0 | -224 | **DELETE** (no archive) | Claude Code worktree leftover. Identical to main (0 unique commits). Local-only. |

### Remote branches (origin)

| Branch | Same as local? | Action |
|---|---|---|
| `origin/main` | yes | leave alone until A1 resolved |
| `origin/pivot/learn-and-trade` | yes | KEEP |
| `origin/dev` | yes | DELETE after archive tag pushed |
| `origin/feat/v2-frontend` | yes | DELETE after archive tag pushed |

### Proposed archive tags (Phase 2)

```
archive/dev-2026-04-25                  → snapshot of dev branch
archive/feat-v2-frontend-2026-04-25     → snapshot of feat/v2-frontend
archive/main-pre-v3-2026-04-25          → only if A1 option 1 chosen (snapshot init main)
```

**Recovery:** `git checkout archive/<name>-2026-04-25` at any future date.

---

## 2. Root-level files inventory

### Tracked files at root

| File | Size | Last touched | Classification | Rationale |
|---|---|---|---|---|
| `README.md` | 235 lines | 2026-04-22 | **REWRITE in Phase 3** | Stale — still says "Signal" not "Foresight", lists V1 pipeline rules, no quickstart for current product |
| `BLUEPRINT.md` | 846 lines | 2026-04-25 | **MOVE to `docs/architecture-detailed.md`** (or keep at root, your call) | Living technical reference, still actively maintained. Too long for root README. |
| `AUTHORS.md` | 4 lines | 2026-04-12 | **MERGE into README** then **DELETE** | Just lists you + Emmanuel — folds into the new README "Team" section |
| `CONTRIBUITING.md` | 86 lines | 2026-04-12 | **PENDING A3** | Misspelled name + V1-era content |
| `LICENSE` | MIT | 2026-04-12 | **KEEP** | Standard, consider switching to "Private — Albert School" per your brief; also pending your call |
| `Dockerfile` | 24 lines | 2026-04-24 | **KEEP** | Active runtime |
| `Makefile` | 47 lines | 2026-04-22 | **KEEP** | Active dev helpers (`install/dev/test/lint/migrate/seed`) |
| `docker-compose.yml` | — | 2026-04-25 | **KEEP** | Active. Just edited it for Alembic upgrade in entrypoint |
| `pyproject.toml` | 56 lines | 2026-04-22 | **KEEP** | Active Python deps |
| `uv.lock` | huge | 2026-04-22 | **KEEP** | Lockfile for `uv` |
| `alembic.ini` | 19 lines | 2026-04-12 | **KEEP** | Alembic config |
| `.gitignore` | 50 lines | 2026-04-22 | **KEEP, audit in Phase 2** | Already covers `.DS_Store`, `node_modules`, `.env`, `.playwright-mcp/`, `.claude/worktrees/`. Spot-fix: doesn't ignore `.claude/` (just the worktrees subfolder). |
| `.dockerignore` | — | 2026-04-12 | **KEEP** | |
| `.env` | — | 2026-04-25 | **NOT TRACKED** (correctly gitignored) | |
| `.env.example` | — | 2026-04-22 | **KEEP** | Template, no secrets |
| `.gitlab-ci.yml` | 14 lines | 2026-04-12 | **KEEP** | CI config |

### Untracked files at root

| Path | Classification | Rationale |
|---|---|---|
| `.claude/` | **GITIGNORE** in Phase 2 | Claude Code session metadata, never to be tracked. `.gitignore` only excludes `.claude/worktrees/`; widen to `.claude/` |
| `.playwright-mcp/` | Already gitignored | Untracked runtime, fine |
| `.venv/` | Already gitignored | Local Python venv, fine |

### Loose .py / .json / .txt scratch files at root

**None found.** No `scratch_*`, `temp_*`, `tmp_*`, `*.log`, `*.json`, or stray `.py` files at the project root. Clean.

---

## 3. Top-level folders inventory

### Folders to keep as-is

| Folder | Purpose | Action |
|---|---|---|
| `frontend/` | React + Vite + Tailwind production app | **KEEP** |
| `app/` (or rename to `backend/`?) | Python backend — see A2 above | **PENDING A2** |
| `alembic/` | DB migrations (25 versions) | **KEEP** — referenced from `alembic.ini` and entrypoint |
| `tests/` | pytest suite (unit + integration, ~376 passing) | **KEEP** |
| `prompts/` | Versioned LLM prompt templates | **KEEP** — actively loaded by `app/llm/*.py` |
| `scripts/` | One-shot ops scripts (backfills, eval, tuning) | **KEEP** — referenced from cron and runbooks |
| `data/` | Runtime inboxes for X scraper (`x_scraper_inbox/`, `x_scraper_processed/`) | **KEEP** — wired in `app/core/config.py:153-154` |
| `static/` | One file: Apple Pay domain verification for Stripe | **KEEP** — served by `app/api/main.py:100-109` |
| `docs/` | Documentation (audit reports, runbooks, plans, specs, eval baselines) | **KEEP, restructure in Phase 3** |

### Folders worth flagging

| Folder | Note |
|---|---|
| `docs/eval_labels/` | **Empty.** Just an empty directory. Either delete or add a `.gitkeep` with a one-line README explaining what it's for. |
| `docs/eval_baselines/` | Single JSON file (`embeddings_2026-04-24_v1.json`). Fine, but verify it's referenced from a runbook before deciding. |
| `docs/superpowers/` | Plans + specs from chantiers #1–#6. **KEEP**, but in Phase 3 move under `docs/plans/` and `docs/specs/` (the `superpowers/` subfolder name is an implementation detail of the workflow, not a doc-tree concept). |
| `docs/audit/` | Two files: `ISSUES_BACKLOG.md` and `heuristic_validation_report_2026-04-24.md`. Your brief says Phase 3.7 will populate this with 8 agent reports. **KEEP**, will be filled in Phase 3. |
| `docs/runbooks/` | 4 promotion runbooks (`promote_*.md`). **KEEP**, useful prod ops. |

### Folders nested under `app/` that look unfamiliar

| Folder | Note |
|---|---|
| `app/agents/` | 6 Python files (`analyst.py`, `risk_manager.py`, `scout.py`, `strategist.py`, `reporter.py`, `base.py`, `registry.py`). Not part of any flow I've touched. Worth confirming whether this is live (Phase 2 `git log app/agents/` check) or dormant. **Flag for your review — do you remember what this is?** |
| All others (`api`, `core`, `db`, `event_engine`, `ingestion`, `llm`, `measurement`, `polymarket`, `processing`, `retrieval`, `scoring`, `services`, `signal`, `sourcing`, `telegram`, `trading`, `workers`, `eval`, `content`, `scripts`) | All actively wired. **KEEP**. |

---

## 4. Summary by classification

| Classification | Branches | Root files | Folders | Total |
|---|---|---|---|---|
| **KEEP ACTIVE** | 1 (pivot/learn-and-trade) | 13 | 9 | 23 items |
| **ARCHIVE → DELETE branches** | 2 (dev, feat/v2-frontend) | — | — | 2 items |
| **DELETE (no archive)** | 2 (a, claude/jovial-benz-dc3565) | — | — | 2 items |
| **REWRITE / MOVE** in Phase 3 | — | 3 (README, BLUEPRINT, AUTHORS) | — | 3 items |
| **PENDING DECISION** | 1 (main) | 1 (CONTRIBUITING) | 1 (app vs backend) | 3 items |
| **GITIGNORE** | — | 1 (`.claude/`) | — | 1 item |
| **EMPTY / TO REVIEW** | — | — | 2 (docs/eval_labels, app/agents) | 2 items |

---

## 5. Phase 2 plan (will execute after your approval)

Once A1 + A2 + A3 are resolved, Phase 2 will:

1. **Tag archives** (push to origin):
   - `archive/dev-2026-04-25`
   - `archive/feat-v2-frontend-2026-04-25`
   - (optionally) `archive/main-pre-v3-2026-04-25` if A1 option 1 chosen
2. **Delete branches** (local + origin):
   - `dev`, `feat/v2-frontend`, `a`, `claude/jovial-benz-dc3565`
3. **Create archive branch** `archive/legacy-files-2026-04-25` containing any files that need preserving (probably `AUTHORS.md` + the old `CONTRIBUITING.md` if you choose option 2 there). Push to origin.
4. **On the production branch**, delete files classified DELETE, commit (`cleanup: remove obsolete files post-V2`), push.
5. **Widen `.gitignore`** to cover bare `.claude/`.
6. **Show you the cleaned `tree -L 2`** before Phase 3.

---

## 6. Three explicit questions for you

1. **A1 — `main` strategy**: do you want me to fast-forward `main` to `pivot/learn-and-trade` (option 1, simplest)? Or keep `pivot/learn-and-trade` as production and retire `main` (option 2)?
2. **A2 — `/backend` folder**: rename `app/` → `backend/` (option 1, invasive), create empty stub (option 2, confusing), or document `/app` as the backend in docs (option 3, my recommendation)?
3. **A3 — `CONTRIBUITING.md`**: rename + rewrite, archive + delete, or move to `docs/CONTRIBUTING.md`?

Plus a smaller one:

4. **`app/agents/`**: do you remember what these 6 agent files are? (`analyst.py`, `risk_manager.py`, `scout.py`, `strategist.py`, `reporter.py`). I can grep the codebase to find references if you don't.

---

**No destructive operation will run before you approve Phase 2.**
