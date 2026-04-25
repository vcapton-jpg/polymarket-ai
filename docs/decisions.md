# Architecture Decisions — Foresight

> Living document. Append new decisions; never rewrite past ones. Supersede with a new DEC and mark the old one `Superseded by DEC-XXX`.

## How to add a decision

1. Pick the next free DEC number.
2. Use the template below.
3. Date is the day the decision was *taken*, not the day documented.
4. Keep `Rationale` to 3-6 bullets — if you need more, write a spec in `docs/specs/`.

## Index

- [DEC-001 — Brand name "Foresight" (after Signal → Presage → Foresight)](#dec-001--brand-name-foresight-after-signal--presage--foresight)
- [DEC-002 — French first, English ready (i18n architecture)](#dec-002--french-first-english-ready-i18n-architecture)
- [DEC-003 — USD primary, EUR secondary (Polymarket native)](#dec-003--usd-primary-eur-secondary-polymarket-native)
- [DEC-004 — No-card 7-day Pro trial with auto-downgrade](#dec-004--no-card-7-day-pro-trial-with-auto-downgrade)
- [DEC-005 — "Prendre position" not "Investir" (legal + UX)](#dec-005--prendre-position-not-investir-legal--ux)
- [DEC-006 — Full auth gating, no demo mode](#dec-006--full-auth-gating-no-demo-mode)
- [DEC-007 — Welcome 4 steps wired via RequireOnboarding redirect](#dec-007--welcome-4-steps-wired-via-requireonboarding-redirect)
- [DEC-008 — Polymarket Builder Program (gasless via user Safe + builderCode attribution)](#dec-008--polymarket-builder-program-gasless-via-user-safe--buildercode-attribution)
- [DEC-009 — Score 90+ Pro paywall on signals + execution](#dec-009--score-90-pro-paywall-on-signals--execution)
- [DEC-010 — Honest gain/loss display in OrderForm (2-up grid)](#dec-010--honest-gainloss-display-in-orderform-2-up-grid)
- [DEC-011 — Dark-only theme in V1+V2](#dec-011--dark-only-theme-in-v1v2)
- [DEC-012 — Heuristic scorer = strength × 0.75 + trade_quality × 0.25](#dec-012--heuristic-scorer--strength--075--trade_quality--025)
- [DEC-013 — 4-baseline measurement layer + heuristic_v1 frozen reference](#dec-013--4-baseline-measurement-layer--heuristic_v1-frozen-reference)
- [DEC-014 — Schema owned by Alembic, not lifespan create_all](#dec-014--schema-owned-by-alembic-not-lifespan-create_all)
- [DEC-015 — CORS allow-list per env, not wildcard](#dec-015--cors-allow-list-per-env-not-wildcard)
- [DEC-016 — Baselines abstain on equality boundaries](#dec-016--baselines-abstain-on-equality-boundaries)

---

## DEC-001 — Brand name "Foresight" (after Signal → Presage → Foresight)

**Date:** 2026-04-14
**Status:** Accepted
**Context:** Original codename "Signal" was a generic noun and conflicted with internal vocabulary (a `signal` is also a row in the DB). A first rebrand to "Presage" landed earlier the same day (`0caaf49`) but was rejected within hours as too obscure for a French-speaking retail audience. A second rebrand to "Foresight" shipped the same evening (`f753d02`).
**Decision:** Product name is "Foresight" across all user-facing surfaces; the source-tree alias `polymarket-ai` and the legacy term `Signal` survive only in code comments and table names.
**Rationale:**
- "Signal" collides with the domain term (`signals` table, `signal_score`, `SignalBuilder`) — using it as a brand caused constant ambiguity in design and copy reviews.
- "Presage" tested poorly with the FR target audience (felt arcane, hard to spell, no clear trading association).
- "Foresight" reads as a clear English noun, transliterates fine to FR copy, and frames the product around the predictive value-add rather than the data plumbing.
- Same-day double rebrand cost was bounded (auth + payments + landing copy), and a clean cutover prevented "two brands in flight" confusion.

**Consequences:**
- DB tables (`signals`, `signal_outcomes`, `signal_predictions`) keep the legacy name — renaming would force a destructive migration with zero user value.
- LocalStorage namespace is `foresight.*` (auth, currency, language, onboarding) so any future rename pays a migration cost.
- Internal docs and `BLUEPRINT.md` use both names interchangeably ("Polymarket AI (alias 'Signal' / 'Foresight')") — accepted as low-cost ambiguity.

---

## DEC-002 — French first, English ready (i18n architecture)

**Date:** 2026-04-14
**Status:** Accepted
**Context:** Foresight's launch market is France (Albert School, FR retail traders, FR fintech regulation surface). All product copy, tutorials, and onboarding are written in French. We did not want to ship in two languages from day one, but we also did not want to retrofit i18n later.
**Decision:** i18next infrastructure is wired from V1 with `fr` as the default locale and `en` as a structured-but-mostly-empty fallback file. Missing EN keys silently fall back to FR (so no untranslated keys leak to the UI).
**Rationale:**
- FR copywriting density is 100%; EN copy lives in `frontend/src/locales/en/common.json` as a stub that backfills as features stabilize.
- i18next with `LanguageDetector` + `localStorage.foresight.language` lets us ship a working FR/EN currency+language toggle (`PreferenceToggles.tsx`) on day one without partial translations breaking the UI.
- Forcing the i18n discipline now (every literal goes through `t()`) avoids the "thousand-string scrub" that hits products which retrofit i18n at v2.
- A future US rollout requires zero infra work — only translation labor.

**Consequences:**
- Every new copy string MUST land in `fr/common.json` first; PRs adding bare JSX literals get bounced.
- The EN file lags the FR file by design — anyone hitting `/en` will see a mostly-FR app for the foreseeable future. This is documented in `frontend/src/lib/i18n.ts`.

---

## DEC-003 — USD primary, EUR secondary (Polymarket native)

**Date:** 2026-04-15
**Status:** Accepted
**Context:** Polymarket is USDC-denominated end-to-end (CLOB prices, order amounts, P&L, builder-code attribution). Our users are predominantly French and read EUR more naturally. We had to pick which currency is the source of truth on screen.
**Decision:** USD is the primary currency (default selection, source-of-truth in the order math); EUR is shown as an `≈` secondary conversion via a mocked exchange rate (`MOCK_EXCHANGE_RATE_USD_TO_EUR = 0.92`). User can flip the toggle in `PreferenceToggles.tsx` and the choice is persisted in `localStorage.foresight.currency`.
**Rationale:**
- Polymarket's CLOB returns USD prices. Treating EUR as primary would force every render to do FX math that's wrong by the time the order fires.
- Showing both ("$50 ≈ 46€") is honest about the underlying asset while staying readable for FR retail.
- USDC is functionally USD on-chain — using EUR primary would imply an FX risk that Foresight is not actually intermediating.
- Mocked rate is acceptable in V2 because users transact in $ — the EUR display is informational, not contractual.

**Consequences:**
- Order P&L, max gain, max loss are all denominated in USD inside `OrderForm.tsx`; the `formatMoney` helper converts at render time only.
- A real FX rate API (openexchangerates.org or similar) is owed when the EUR display becomes load-bearing — currently it's labelled `≈` so the rate drift is forgiven by the user contract.

---

## DEC-004 — No-card 7-day Pro trial with auto-downgrade

**Date:** 2026-04-15
**Status:** Accepted
**Context:** Standard SaaS trials require a credit card upfront, which kills retail signup conversion. We wanted Pro to be "try then decide" without billing friction.
**Decision:** New users selecting Pro at signup get 7 days of full Pro access with no card on file. `trial_ends_at = now + 7d` is written server-side (`app/api/routes/auth.py::TRIAL_DAYS = 7`); the client mirrors it in `localStorage.foresight.auth`. At expiry the client auto-downgrades to Free via `checkAndHandleTrialExpiry()` and shows `EndOfTrialModal` once per session.
**Rationale:**
- No-card removes the largest single friction point on Pro signup.
- Auto-downgrade (vs auto-charge) eliminates surprise-billing complaints — the worst case for a trial user is "I lost Pro features", never "you charged me without asking".
- Server-side `trial_ends_at` is the source of truth; client-side mirroring lets the EndOfTrialModal trigger without a network round-trip.
- The `card_attached: false` flag on AuthState makes the upsell prompt unambiguous (we know exactly when to show "add a card to keep Pro").

**Consequences:**
- Anyone can spin a fresh email and re-trial; we accept this for the launch phase and revisit if abuse becomes measurable.
- Trial-expiry UX must be reliable on every entry point — `EndOfTrialModal` listens to a session flag (`SESSION_KEYS.trialExpiryShown`) so it only fires once per tab.

---

## DEC-005 — "Prendre position" not "Investir" (legal + UX)

**Date:** 2026-04-22
**Status:** Accepted
**Context:** Polymarket markets are not regulated investment products in France. Calling the action "Investir" would imply a regulated PSI/CIF activity (under AMF) and misrepresent what the user is actually doing — taking a directional bet on an event outcome. The audit (`docs/audit/ISSUES_BACKLOG.md` §3.1) flagged this risk explicitly.
**Decision:** All user-facing copy uses "Prendre position" (or context-specific verbs like "Acheter X parts YES") for the trading action. "Investir" is banned from product copy.
**Rationale:**
- "Investir" in French regulatory context maps to AMF-regulated investment products — using it on a prediction market crosses the marketing-vs-regulation line.
- "Prendre position" is honest about what's happening: the user is committing capital to a directional view on a discrete event, not buying a security.
- The OrderForm CTA is even more concrete: "Acheter X parts YES" — names the exact instrument (CLOB shares) the user receives.
- Aligns the product copy with the eventual disclaimer requirement ("perte totale possible") that the legal audit will mandate.

**Consequences:**
- Marketing assets, FAQ, onboarding tutorial, and the homepage demo (`AnimatedSignalDemo.tsx`) all use "prendre position".
- Does NOT provide regulatory cover — the product still routes orders to a service blocked by the ANJ since late 2024 (see DEC-008 caveat). Copy honesty is necessary but not sufficient.

---

## DEC-006 — Full auth gating, no demo mode

**Date:** 2026-04-15
**Status:** Accepted
**Context:** A common growth-hack pattern is to let anonymous users browse the product and convert later. For a trading product wired to a wallet (Polymarket Builder Program, see DEC-008), anonymous browsing creates more problems than it solves: no per-user state, no wallet, no compliance trail, no conversion funnel signal.
**Decision:** Every authenticated surface (`/signals`, `/signals/:id`, `/portfolio`, `/performance`, `/apprendre`, `/welcome`, `/settings`) is wrapped in `<RequireAuth>`. Unauthenticated users are redirected to `/signup` (first-time) or `/login` (returning, via `has_ever_signed_up` flag) with a `next=` hop-back param.
**Rationale:**
- Wallet linking (DEC-008) requires a persistent user identity from the first interaction — anonymous browsing would mean "spin up a wallet, then ask the user to claim it later", which is fragile.
- Pure-Pro upsell requires knowing who the user is and what plan they're on — anonymous browsing dilutes the funnel signal.
- Activation friction is partially mitigated by DEC-004 (no-card trial) — signup is fast and reversible.
- One source of truth (`readAuth()` in `frontend/src/lib/trial.ts`) removes a class of "is the user logged in?" bugs that plagued early prototypes.

**Consequences:**
- SEO and landing-page browsing get harder — public pages (`/`, `/pricing`, `/faq`, `/cgu`) carry the marketing weight.
- First-touch UX is `/signup`, not the product. The signup form must be ruthless about friction (Google OAuth + email).

---

## DEC-007 — Welcome 4 steps wired via RequireOnboarding redirect

**Date:** 2026-04-15
**Status:** Accepted
**Context:** Earlier prototypes had an onboarding screen that users could click past without it influencing anything downstream — pure decoration. We needed onboarding answers (profile type, experience, risk reaction, budget) to actually shape the in-app sizing and copy.
**Decision:** The 4-step Welcome (`profile / experience / reaction / budget`, `frontend/src/pages/Welcome.tsx`) is enforced by `<RequireOnboarding />` in `App.tsx`: any authed user landing on a non-exempt path with `localStorage.foresight.onboarding != "done"|"skipped"` is redirected to `/welcome`. The answers feed `useProfile()`, which controls the OrderForm sizing presets and Apprendre copy.
**Rationale:**
- Active wiring: `useProfile` reads the persisted profile and changes the OrderForm `SIZING_BY_TYPE` recommendation per profile (Découvreur 10–25 USDC, Actif 25–100, Confirmé 100–500).
- A "Passer" (skip) escape hatch exists for users who don't want to answer — but it sets `onboarding=skipped`, which the OrderForm detects and shows a "Personnalise en 30 sec →" nudge instead of silently using a default.
- Forcing the redirect (vs a passive "we recommend") means we always have a profile-type signal for sizing, even if it's a coarse default.
- Steps are 4 questions, not 8 — the friction budget is small.

**Consequences:**
- The brief's earlier framing of the 4 steps as `age/CGU/budget/quiz` is incorrect — those gates are split across other flows: age + CGU live in `Signup.tsx`, the L&T budget+quiz gates were planned in `docs/plans/2026-04-23-pivot-learn-and-trade.md` but later removed (commit `20b3f2a refactor(onboarding): remove L&T trading-test gates, route to Apprendre`).
- The "Passer" path means a small fraction of users never give us a profile signal — accepted, with the OrderForm nudge as the recovery mechanism.

---

## DEC-008 — Polymarket Builder Program (gasless via user Safe + builderCode attribution)

**Date:** 2026-04-22
**Status:** Accepted
**Context:** The first iteration of `/api/trading/trade` used a single `BuilderTradeClient` wallet to sign every order — meaning Foresight's USDC funded every trade. Wrong. We needed user funds backing user trades, but we did not want to require the user to sign every transaction (kills conversion). Spec: `docs/specs/2026-04-22-polymarket-wallet-link-design.md`.
**Decision:** Adopt the Polymarket Builder Program with `py_clob_client_v2`'s `funder` pattern. The builder key signs orders; the user's deployed Gnosis Safe (one-time wallet-connect setup) provides the USDC. Every `OrderArgsV2` carries `builder_code=settings.polymarket_builder_code` for revenue attribution.
**Rationale:**
- After one-time setup, every subsequent trade is a single API call with zero wallet interaction — equivalent UX to a centralized broker.
- User USDC is in their own Safe, not Foresight's wallet — clear custody line, clear regulatory framing.
- `builder_code` attribution gives Polymarket a hook to revenue-share volume back to Foresight.
- `py_clob_client_v2` is the official supported path (v1 was deprecated mid-design).
- Polygon gas for Safe deployment is ~$0.001, paid by the builder wallet — small enough to absorb on the activation funnel.

**Consequences:**
- Critical caveat: the Builder Program does NOT provide regulatory cover in France. Polymarket has been blocked by the ANJ since late 2024; routing FR users into Polymarket trading remains a legal gray zone. A separate fintech-lawyer audit is owed before public launch (logged in `docs/audit/ISSUES_BACKLOG.md` §3.1).
- Wallet link is a one-time UX cost (MetaMask/WalletConnect modal + Safe deployment spinner) — the activation funnel must absorb it.
- Builder credentials must be rotated as a single secret (`POLYMARKET_BUILDER_CODE`, builder private key); compromise lets a third party attach Foresight's builder code to their own volume.

---

## DEC-009 — Score 90+ Pro paywall on signals + execution

**Date:** 2026-04-15
**Status:** Accepted
**Context:** We needed a Pro upsell trigger that wasn't a feature gate (Free users still get the core product) but was clearly visible in the moment of highest user intent — looking at the best signals.
**Decision:** Free users see signals scored 90+ as blurred teaser cards on `/signals` (via `<PaywallOverlay>`), and the OrderForm execution path on a 90+ signal redirects to `/pricing?plan=pro` instead of opening the Stripe flow.
**Rationale:**
- 90+ is the rarest, highest-conviction bucket — gating it creates concrete FOMO instead of abstract "Pro = better".
- Blurring (vs hiding) lets the Free user count and see the existence of premium signals — they know what they're missing.
- The execution-time block is the second touchpoint: even if a Free user somehow lands on a 90+ signal detail, the trade attempt is what triggers the upsell, not a generic "go Pro" banner.
- `<PaywallOverlay>` is a reusable component (also used to gate the 6th+ daily signal for Free users) — one paywall pattern, multiple cells.

**Consequences:**
- Score 90+ signals are rare (~5–15% of daily volume) — the paywall must coexist with enough free signal supply that Free isn't useless.
- Free users see the blurred shape but never see the catalyst text — we're explicit that this is a teaser, not a degraded version.
- If the heuristic scorer's distribution shifts (DEC-012, DEC-013), the threshold may need to move with it. Currently hard-coded as `signal.score >= 90`.

---

## DEC-010 — Honest gain/loss display in OrderForm (2-up grid)

**Date:** 2026-04-15
**Status:** Accepted
**Context:** Standard trading UIs show "potential return" and bury the loss case. For a prediction market where the loss case is "you lose 100% of your stake", that framing is dishonest. The audit (`ISSUES_BACKLOG.md` §3.3) flagged the absence of risk visibility as an ethical and potentially legal exposure.
**Decision:** The OrderForm composer shows "Gain si ✓" and "Perte si ✗" in a two-column grid of equal visual prominence. The loss case is always present, always the same size, always in the warning color — never collapsed under a "details" disclosure.
**Rationale:**
- Pre-commits the user to the binary outcome before they click — no hidden tail.
- Equal visual weight (`grid-cols-2`, `border-signal-yes/20` and `border-signal-no/20`) prevents the framing trick of making losses smaller.
- Honest framing aligns with the "Prendre position" copy (DEC-005) and the planned `cooloff` protection (after 3 consecutive losses).
- "Montants hors frais Polymarket" footnote is explicit about what the figures don't include.

**Consequences:**
- Some conversion is lost vs the win-only framing — accepted as the cost of an honest contract with the user.
- The "Perte si ✗" amount equals the stake (100% loss) — non-negotiable, this is what binary markets are.
- Future copy that adds "expected value" or "edge" framing must keep the 2-up grid intact, not replace it.

---

## DEC-011 — Dark-only theme in V1+V2

**Date:** 2026-04-15
**Status:** Accepted
**Context:** A theme system (light + dark + a "Cosmic Night" custom palette in early sketches) was on the table for V2. Maintaining two themes doubles the design surface (every token, every chart, every illustration) for a small team.
**Decision:** Foresight ships dark-only in V1 and V2. The `darkMode: "class"` switch in `tailwind.config.ts` exists in code but is permanently on; there is no light-mode CSS variant.
**Rationale:**
- The user pattern is late-night news-driven trading — dark is the natural surface for that session, not an accommodation.
- Dark-only halves the design system surface: one set of tokens, one set of chart palettes, one set of screenshot/marketing assets.
- A distinctive dark palette (deep obsidian background + signal-yes/signal-no chromatic pair) reads as a financial product, not a generic SaaS.
- Light mode adds zero product capability; if users demand it, we revisit when there's evidence.

**Consequences:**
- Brand and marketing assets ship dark — not switching is a deliberate aesthetic choice.
- Accessibility contrast must be verified inside the dark palette (no light fallback safety net) — Sprint 2 a11y work (`d0516b9`) addresses this for skip-links and tap targets.
- "Cosmic Night" as an explicit named theme did not survive into the codebase — the dark palette is just the default. Documenting the original aspiration here so future contributors don't try to "add" a theme.

---

## DEC-012 — Heuristic scorer = strength × 0.75 + trade_quality × 0.25

**Date:** 2026-04-24
**Status:** Accepted (frozen as `heuristic_v1`; weights tunable in shadow via `HEURISTIC_W_*` env)
**Context:** The original `HeuristicScorer` was a single function with hand-picked weights, not testable in isolation, and never benchmarked against anything. Audit §6.1 flagged: *"poids arbitraires jamais validés sur held-out set"*. Spec: `docs/specs/2026-04-24-heuristic-score-validation-design.md`.
**Decision:** Decompose the scorer into three layers: `compute_signal_strength` (pure function over freshness/source/confirmation/LLM features) and `compute_trade_quality` (pure function over liquidity/spread/TTR), composed as `signal_score = STRENGTH_WEIGHT × strength + TRADE_WEIGHT × quality` with `STRENGTH_WEIGHT = 0.75` and `TRADE_WEIGHT = 0.25`. Weights live in a frozen `HeuristicWeights` dataclass (`app/scoring/weights.py`) with sum-to-1 invariants.
**Rationale:**
- Pure sub-scorers are testable per-weight (monotonicity, zero-ing effect) — the test suite now pins each weight's contribution.
- 75/25 reflects the editorial priority: a trade is mostly about whether the news catalyst is real (strength), with execution-quality (liquidity/spread) as a secondary tiebreaker — matches the audit's "decoration vs alpha" framing.
- The composition lets us shadow-test alternative weights via env-driven `HEURISTIC_W_*` overrides without touching prod (`heuristic_shadow` variant in `record_baselines`).
- A coordinate-descent tuner (`scripts/tune_heuristic_weights.py`) can propose better weights, gated by a 3-check rule (Brier-CI disjoint, P&L slip ≤5%, no bucket-regression >5%) before promotion.

**Consequences:**
- The validation report (`docs/audit/heuristic_validation_report_2026-04-24.md`) shows `heuristic_v1` Brier=0.31 vs `baseline_market_price` Brier=0.03 — the v1 weights are demonstrably sub-optimal vs trivial baselines. Frozen as a reference, NOT as the final answer.
- Promotion of new weights is a manual workflow (`docs/runbooks/promote_heuristic_candidate.md`) — no auto-tuning loop in prod.
- The 75/25 split itself is a tunable parameter (`strength_weight`, `trade_weight` in HeuristicWeights), not a hard-coded constant — but the v1 frozen reference uses these values.

---

## DEC-013 — 4-baseline measurement layer + heuristic_v1 frozen reference

**Date:** 2026-04-23
**Status:** Accepted
**Context:** Pre-chantier-1, we had a winrate of 46–48% on n=22 resolved markets and no comparison. We could not say whether this number meant "the pipeline adds value" or "we're flipping coins". Spec: `docs/specs/2026-04-23-measurement-foundations-design.md`.
**Decision:** Every signal write triggers `record_baselines()` which inserts 5 rows into `signal_predictions` (same transaction, in-band): `baseline_random`, `baseline_market_price`, `baseline_momentum`, `baseline_news_sentiment`, plus the frozen `heuristic_v1`. When markets resolve, `check_resolved_markets` updates all 5 variant rows. The `/api/admin/metrics/variants` endpoint exposes Brier, Wilson CI95, simulated P&L per variant.
**Rationale:**
- Without a baseline, any winrate number is uninterpretable — Brier=0.31 is bad if a baseline scores 0.03, fine if a baseline scores 0.5.
- Baselines are pure, deterministic, and cheap (<15ms total) — running them in-band guarantees every signal has its 5 rows, no race conditions, no "missing baseline" branch in aggregation queries.
- Resolution piggy-backs on the existing `check_resolved_markets` cron (already runs every 6h, already holds the resolved price) — single UPDATE, no new infra.
- The frozen `heuristic_v1` row is the apples-to-apples reference for any future scorer change (`heuristic_shadow`, future ML models) — without it, we can't tell whether a "new" scorer is actually better or just measured differently.
- Shadow variants (LLM A/B, sourcing alternatives) are out of scope for this layer — they go async via Celery to avoid blocking signal creation.

**Consequences:**
- Migration 020 (`signal_predictions`) is immutable — a UNIQUE on `(signal_id, variant)` enforces idempotency, but means renaming a variant requires a data migration (see migration 025 which renamed `signal` → `heuristic_v1`).
- The validation report at chantier #5 closeout showed `heuristic_v1` underperforming `baseline_market_price` on Brier — this is the chantier doing its job (telling us the truth) and the trigger for tuning work.
- The 4 baselines themselves can have bugs that pollute the comparison (see DEC-016 for the abstain-on-tie fixes).

---

## DEC-014 — Schema owned by Alembic, not lifespan create_all

**Date:** 2026-04-25
**Status:** Accepted
**Context:** The FastAPI lifespan handler in `app/api/main.py` previously called `Base.metadata.create_all` at startup. This worked locally but raced concurrent boots (worker + app + beat all trying to create tables simultaneously) and silently masked drift between SQLAlchemy models and Alembic migration state — a model change without a migration would "just work" in dev and fail in prod.
**Decision:** Schema is owned exclusively by Alembic. The Docker entrypoint runs `alembic upgrade head` before `uvicorn` boots (`docker-compose.yml:56`); the lifespan handler no longer touches schema. Commit: `60ef1cf fix(api): scoped CORS allow-list per env + Alembic owns schema`.
**Rationale:**
- One source of truth for schema state — if Alembic disagrees with the models, the migration is wrong, not the runtime.
- `alembic upgrade head` is idempotent and serializable — no race when 6 services boot simultaneously.
- Forces the discipline of "model change ⇒ new migration" — drift now fails loudly at the next boot, not silently in prod.
- Removes the in-lifespan `create_all` that was already a known bad practice for any schema beyond a toy app.

**Consequences:**
- Every model change MUST land with an `alembic revision --autogenerate` — no shortcuts.
- The Docker entrypoint is now order-dependent (migrate then serve); a failed migration fails the container, which is the correct behavior.
- Local dev workflows that used to work on a fresh DB without Alembic must now run `make migrate` (or rely on the entrypoint).

---

## DEC-015 — CORS allow-list per env, not wildcard

**Date:** 2026-04-25
**Status:** Accepted
**Context:** `app/api/main.py` previously used `allow_origins=["*"]` together with `allow_credentials=True`. Browsers reject credentialed requests against a wildcard, so any cookie- or Authorization-bearing call from a real frontend would 403; beyond that, wildcard + credentials is a textbook CSRF surface. Found during the post-audit pass.
**Decision:** New `app/api/cors.py::resolve_cors_origins` returns an explicit allow-list per environment. Production is locked to `[app_base_url] + cors_extra_origins`; dev/test/staging additionally include the Vite dev ports (`5173`, `3000` × `localhost` and `127.0.0.1`). Commit: `60ef1cf fix(api): scoped CORS allow-list per env + Alembic owns schema`.
**Rationale:**
- Wildcard + credentials is broken by browser spec (the Set-Cookie / Authorization headers are dropped) — the prior config silently broke real auth flows.
- Explicit origins are auditable; wildcards are not — security review can read the allow-list and verify it.
- Dev and prod have different origin sets — encoding that in code (not in env-var hacks) keeps the dev experience smooth without leaking to prod.
- `cors_extra_origins` (comma-separated env var) gives a clean path to add staging or apex domains without code changes.

**Consequences:**
- Adding a new frontend domain requires either a deploy (to update `app_base_url`) or an env var change (`CORS_EXTRA_ORIGINS`) — no zero-touch path. Accepted as the trade for explicitness.
- A misconfigured `app_base_url` in prod will break the frontend hard (no fallback to wildcard) — fail-fast is the correct behavior here.

---

## DEC-016 — Baselines abstain on equality boundaries

**Date:** 2026-04-25
**Status:** Accepted
**Context:** `baseline_news_sentiment`, `baseline_market_price`, and `baseline_momentum` previously fell through to a `BUY_NO` branch when the underlying signal was exactly at the tie (sentiment == 0, price == 0.5, return_24h == 0). This invented a fake `(BUY_NO, 0.5)` prediction at the boundary and polluted Brier comparisons with predictions the baseline didn't actually have. Found during the post-audit pass; 13 prod rows had been polluted on `baseline_market_price`. Commits: `50e62e5`, `3643593`.
**Decision:** All three baselines now return `(None, None)` at the equality boundary — an honest abstention. The `signal_predictions` row is still inserted (with NULL direction and NULL probability) so the audit trail is preserved, but it does not contribute to Brier/winrate aggregations. 13 historical `baseline_market_price` rows were backfilled to NULL/NULL in the same fix.
**Rationale:**
- A baseline that "predicts" `(BUY_NO, 0.5)` at the tie is making the same prediction as a coin flip but reporting it as a deterministic baseline — this inflates the baseline's apparent informativeness and biases the comparison against the heuristic.
- Brier integrity matters: the whole point of DEC-013 is honest comparison. A baseline that lies at the boundary breaks the contract.
- TDD coverage was added (6 new tests pin both the abstain behavior and the non-tie paths) so the regression can't return silently.
- The pattern (abstain at tie) is universal across all three baselines — applied uniformly.

**Consequences:**
- Aggregation queries on `signal_predictions` MUST filter `WHERE predicted_direction IS NOT NULL` — already the case for the metrics endpoint.
- Some baselines (especially `baseline_momentum` once `/prices-history` returns real data) will abstain on a non-trivial fraction of signals — accepted as the cost of honest measurement.
- Future baselines added to the registry MUST decide explicitly what to do at their equality boundary (the test convention now enforces this).

---
