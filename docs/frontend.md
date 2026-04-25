# Foresight Frontend Guide

This is the operating manual for the Foresight SPA — the React 18 + TypeScript +
Vite + Tailwind 3 codebase that lives under `frontend/` and ships at
[getforesight.io](https://getforesight.io). French-first UI, dark-only "Cosmic
Night" theme, mobile-first (390 px reference). Production app, not a prototype.

If you have to read one other file, read `frontend/src/docs/voice-guide.md`.
Copy is a load-bearing part of the product.

---

## 1. Setup

**Node:** 20 LTS or newer. (No `engines` field is set in `package.json`; the
team standardises on Node 20+.)

**Package manager:** npm. The lockfile is `frontend/package-lock.json` — do
not commit a `pnpm-lock.yaml` or `yarn.lock`.

```sh
cd frontend
npm install
npm run dev
```

The dev server runs on **`http://localhost:3000`** (configured in
`frontend/vite.config.ts`). Requests to `/api/*` are proxied to
**`http://localhost:8001`** (the FastAPI backend). Run the backend separately
(see the root `README.md` / `Makefile`).

### Environment variables

All declared in `frontend/src/vite-env.d.ts`. Every browser-exposed env var must
be prefixed `VITE_` so Vite inlines it.

| Var | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | Absolute API base, e.g. `https://api.getforesight.io/api`. Leave unset in dev so the Vite proxy handles `/api`. | `/api` |
| `VITE_USE_MOCKS` | `"1"` forces the bundled `MOCK_*` datasets in `src/data/` instead of hitting the API. Dev only — ignored in production builds. | unset |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth client id used by the "Continue with Google" button on `/login` and `/signup`. | unset |
| `VITE_POLYMARKET_BUILDER_CODE` | Polymarket Builder Program code stitched into the outbound `polymarket.com` URL. | hard-coded fallback |

Create `frontend/.env.local` for local overrides — it is gitignored. Do not
put any real secret in `VITE_*` vars; everything prefixed `VITE_` ends up in
the client bundle.

---

## 2. Project structure

```
frontend/src/
├── App.tsx               # BrowserRouter, lazy routes, AnimatePresence shell
├── main.tsx              # ReactDOM root + QueryClient + UserPreferences + Toast providers
├── components/           # Atomic + composite components, grouped by domain
│   ├── auth/             # RequireAuth route guard
│   ├── gamification/     # Streaks, XP, life-decay UI bits
│   ├── homepage/         # Marketing hero + section blocks
│   ├── layout/           # AppShell, AuthShell, PublicNav, BudgetBar, banners
│   ├── learn/            # /apprendre lesson surfaces
│   ├── modals/           # Dialog wrappers (Radix dialog primitives)
│   ├── performance/      # Charts on /performance (lazy, recharts inside)
│   ├── portfolio/        # Position cards, list + filter UI
│   ├── signals/          # SignalCard, OrderForm, SignalTimeline, badges
│   ├── trading/          # Order-related primitives (sliders, stake inputs)
│   ├── ui/               # Generic primitives (Button, Input, Skeleton, Logo, …)
│   ├── welcome/          # /welcome onboarding quiz blocks
│   └── ErrorBoundary.tsx # Class component used at root + per-route
├── pages/                # Route-level pages, one .tsx per route
│   └── __tests__/        # Page-level tests (vitest + RTL)
├── lib/                  # Utilities, hooks, i18n, motion, formatters, API client
│   ├── api/              # Thin REST client + per-domain modules (auth, paper, …)
│   ├── motion.ts         # EASE_PREMIUM, DURATIONS, STAGGER, useMotionConfig
│   ├── i18n.ts           # i18next setup, SUPPORTED_LANGUAGES, fallback chain
│   ├── formatCurrency.ts # USD ↔ EUR display formatter
│   ├── typography.ts     # NBSP, guillemets(), formatFR(), formatFRUnit()
│   ├── storageKeys.ts    # Central registry of every localStorage key
│   ├── trial.ts          # AuthState read/write, trial gating
│   ├── useToasts.tsx     # ToastProvider + useToasts() hook
│   ├── userPreferences.tsx # UserPreferencesProvider (currency, language)
│   ├── WalletScope.tsx   # Lazy wagmi wrapper (kept off the eager bundle)
│   └── __tests__/        # Lib unit tests
├── hooks/                # Cross-page React hooks (useAuth, useCountUp, …)
├── locales/              # i18n strings
│   ├── fr/common.json    # Source-of-truth translations (FR is authoritative)
│   └── en/common.json    # English; mostly empty, falls back to FR
├── styles/
│   └── globals.css       # Tailwind layers, font imports, focus-ring, grain overlay
├── types/
│   └── signal.ts         # Signal, Position, UserProfile, OrderDraft, …
├── data/                 # Static seed data (MOCK_SIGNALS, MOCK_POSITIONS, …)
├── docs/
│   └── voice-guide.md    # Copywriting voice & FR typography rules — READ THIS
├── test-setup.ts         # Vitest setup (jsdom, jest-dom matchers)
└── vite-env.d.ts         # ImportMetaEnv typings
```

Path alias: `@/*` resolves to `src/*` (configured in both `tsconfig.json` and
`vite.config.ts`). Always import as `@/lib/motion`, never as
`../../lib/motion`.

---

## 3. Design system

### Tokens

Single source of truth: **`frontend/tailwind.config.ts`**. CSS variables for
shadcn-flavoured aliases live in `frontend/src/styles/globals.css` under
`:root`. Never write a hex literal in component code.

**Color palette (verified against `tailwind.config.ts`):**

- `obsidian-{950,900,850,800,750,700,650,600}` — base surface scale, darkest
  to lightest. `obsidian-900` is the page background.
- `brand-{50…900}` — mint cyan, `brand-500 #0BE0A6` is the primary.
- `signal-{yes,no,amber,alert}` — direction + state colours
  (`#4ADE80`, `#F87171`, `#FBBF24`, `#FB7185`).
- `tier-{1,2,3}` — source-tier badges (mint / sky / violet).
- `ink` (default `#F5F6F8`), `ink-muted`, `ink-dim`, `ink-readable`,
  `ink-faint` — text scale, dark to dim. Use `ink-readable` (`#8A8D99`) for
  WCAG-AA informational body text.
- `line` (default `#1F1F28`), `line-strong`, `line-subtle` — hairline
  separators.
- `chart-{yes,no,amber,brand,sky,orange,purple}` — recharts palette.
- `telegram` `#229ED9`, `polymarket` `#2D7CFE` — brand accents.
- shadcn HSL aliases (`background`, `card`, `primary`, `destructive`, …) —
  for Radix primitives that expect CSS-var theming.

### Typography

Three font families:

- **Satoshi** (`font-display`) — display headings (h1–h5 default to this via
  the `globals.css` base layer). Self-hosted via Fontshare CDN.
- **Inter** (`font-sans`) — body. Self-hosted via `@fontsource/inter`,
  weights 400/500/600/700.
- **JetBrains Mono** (`font-mono`) — numbers, code, eyebrows. Always combine
  with `tabular-nums` (the `.num` utility class does this for you).

Bespoke type scale in Tailwind: `display-1`, `display-2`, `display-3`,
`eyebrow`, `label-{xs,sm}`, `body-{sm,md,lg}`, `title-{sm,md}`. Prefer these
over raw `text-*` sizes.

### French typography expectations

These are non-negotiable. Use the helpers in `frontend/src/lib/typography.ts`:

- `NBSP` (` `) before `:`, `;`, `?`, `!`, and inside `« ` ` »`.
- Curly apostrophe `’` (`’`), never the straight `'`.
- Guillemets `« … »`, never `"…"`. Wrap with `guillemets("vendre")`.
- Thin-space thousands separator. Use `formatFR(61247)` → `"61 247"`.
- En-dash `–` for ranges (`formatFRRange`), em-dash `—` for parentheticals.
- NBSP between value + unit: `formatFRUnit(68, "s")` → `"68 s"`.

When you write JSX with literal French strings, embed NBSPs as Unicode
escapes inside JS strings (`{"Essai 7 jours"}`) — JSX text
collapses regular spaces in some contexts.

### Motion

`frontend/src/lib/motion.ts` is the only place easing curves and durations
live. Never hardcode `[0.22, 1, 0.36, 1]` or `0.4` — import.

```ts
import { EASE_PREMIUM, DURATIONS, STAGGER, useMotionConfig, useStagger, fadeInUp } from "@/lib/motion"
```

- `EASE_PREMIUM = [0.22, 1, 0.36, 1]` — the only easing curve used by the app.
- `DURATIONS = { quick: 0.18, default: 0.3, expressive: 0.5 }`.
- `STAGGER = { default: 0.06, hero: 0.1 }`.
- `useMotionConfig("default")` returns a `{ duration, ease }` object with
  `duration: 0` under `prefers-reduced-motion`. Always go through this hook
  rather than reading `useReducedMotion()` yourself.
- `fadeInUp` and `fadeIn` are reusable variant objects.

`globals.css` also installs a global `prefers-reduced-motion` reset that
caps every animation/transition at `0.01ms` — but that is the safety net,
not an excuse to skip `useMotionConfig`.

### Color philosophy: Cosmic Night = dark only

There is no light theme and there is not going to be one. The `darkMode:
"class"` in Tailwind is dormant — `<html>` has `color-scheme: dark` and the
body is hardcoded `bg-obsidian-900`. Rationale: the product is a real-time
trading dashboard; high-contrast obsidian + mint cyan reads as a Bloomberg
terminal, not a SaaS app. Don't add a theme toggle.

---

## 4. Key conventions (mandatory)

### 4.1 i18n — every user-facing string goes through `t()`

```tsx
import { useTranslation } from "react-i18next"

export function MyComponent() {
  const { t } = useTranslation()
  return <h1>{t("nav.items.signals")}</h1>
}
```

Strings live in `frontend/src/locales/fr/common.json` (authoritative) and
`frontend/src/locales/en/common.json` (mostly empty — falls back to FR via
`fallbackLng: "fr"` in `lib/i18n.ts`). Adding a new key: add it to **fr**
first, then mirror in **en**.

> **Reality check:** large parts of the existing pages (e.g. `Pricing.tsx`,
> `Apprendre.tsx`) still hardcode FR strings. That is technical debt — new
> code must use `t()` and existing screens are being migrated.

### 4.2 Money formatting — `formatCurrency()`

Money in state is always USD (Polymarket trades USDC). Convert at render
time via `frontend/src/lib/formatCurrency.ts`:

```ts
import { formatCurrency } from "@/lib/formatCurrency"

formatCurrency(50, "USD")                       // "$50"
formatCurrency(50, "EUR")                       // "€46"
formatCurrency(-12, "USD", { signed: true })    // "−$12"
formatCurrency(47, "USD", { signed: true })     // "+$47"
```

The user's currency comes from `useUserPreferences()`. Default is USD; the
EUR rate is mocked at `0.92`. A real FX feed is a backend concern.

### 4.3 Tokens, never raw hex

```tsx
// ✅ good
<div className="bg-obsidian-850 text-ink-muted border border-line/60" />

// ❌ wrong
<div style={{ background: "#0B0B11", color: "#A1A3AC" }} />
```

The tailwind config is the only file that references hex literals. If a
colour you need isn't there, add it to the config — don't inline it.

### 4.4 French typography — use the helpers

See §3. Common offenders to grep for:

- Straight apostrophe in FR strings → swap for `’`.
- Regular space before `:`, `?`, `!`, `;` → use ` `.
- `"…"` around a quoted term → use `« … »` with internal NBSP.
- Hardcoded `61 247` thousand separator → use `formatFR()` so it stays a
  thin space and survives copy edits.

### 4.5 Container vs presentational components

- **`components/`** — presentational, prop-driven, zero or near-zero side
  effects. Receive data, render markup. Example: `SignalCard` takes a
  `Signal` prop and renders it.
- **`pages/`** — container surfaces. Mount React Query hooks, read
  `useUserPreferences` / `useAuth`, compose feature components, own routing.
- We do not use a `*Container.tsx` suffix; the `pages/` vs `components/`
  split is the line.

### 4.6 Mobile-first, 390 px reference

Reference viewport: **iPhone 14, 390 × 844**. Every page must look right
there before scaling up. Touch targets ≥ 44 × 44 px. `AppShell` switches to
the slide-out drawer at `lg` (1024 px); `<lg` you get the topbar + drawer
pattern. Test in DevTools narrow viewport — many bugs only surface on
390 px.

### 4.7 WCAG — minimum AA contrast

Body text: 4.5 : 1 against background. Large text (≥ 18 pt or 14 pt bold):
3 : 1. The Cosmic Night palette is tight — `ink-readable` (`#8A8D99`)
exists specifically because `ink-dim` (`#6B6E79`) fails AA on small
informational text. When in doubt, run the colour through a contrast checker
and prefer `ink-muted` (`#A1A3AC`) for body copy.

The focus ring is `ring-brand-400` with `ring-offset-2 ring-offset-obsidian-900`
(`globals.css` line 106) — meets the 3 : 1 ring contrast requirement.

---

## 5. Available scripts

From `frontend/package.json`:

| Script | Command | When to run |
|---|---|---|
| `npm run dev` | `vite` | Local development. Starts Vite on `:3000` with HMR + the `/api → :8001` proxy. |
| `npm run build` | `tsc -b && vite build` | Production build. Type-checks the project then emits to `frontend/dist/`. CI runs this on every PR. |
| `npm run preview` | `vite preview` | Serves `dist/` locally on `:4173` to smoke-test the production bundle (no proxy — set `VITE_API_URL` to a real backend). |
| `npm run lint` | `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0` | Lint check. Zero warnings allowed. Run before pushing. |

**No `test` script exists in `package.json`** even though `vitest` is
installed and tests live under `src/**/__tests__/`. Run them directly:

```sh
cd frontend
npx vitest          # watch mode
npx vitest run      # one-shot, suitable for CI
```

(Adding the `test` script to `package.json` is on the todo list.)

---

## 6. How to add a new page

1. **Create the file** under `frontend/src/pages/`, named `MyPage.tsx`. Use
   PascalCase. The page should default-export a single React component.

   ```tsx
   import { AppShell } from "@/components/layout/AppShell"

   export default function MyPage() {
     return (
       <AppShell breadcrumb={[{ label: "Mon écran" }]}>
         <section className="container-page py-8">{/* … */}</section>
       </AppShell>
     )
   }
   ```

2. **Wire the route** in `frontend/src/App.tsx`. Add a lazy import alongside
   the existing block (lines 11–28):

   ```tsx
   const MyPage = lazy(() => import("./pages/MyPage"))
   ```

   Then add a `<Route>` inside `<AnimatedRoutes>`. Mirror the existing
   pattern: every route is wrapped in `RouteBoundary` and `RouteTransition`,
   and authed surfaces additionally wrap in `RequireAuth`:

   ```tsx
   <Route
     path="/my-page"
     element={
       <RouteBoundary scope="My page">
         <RequireAuth>
           <RouteTransition><MyPage /></RouteTransition>
         </RequireAuth>
       </RouteBoundary>
     }
   />
   ```

   `scope` is a short human label used in the in-DOM error fallback. If your
   route should bypass the onboarding gate, add it to
   `ONBOARDING_EXEMPT_PATHS` (App.tsx line 39).

3. **Layout wrappers.** Authed surfaces wrap content in `<AppShell>`
   (`components/layout/AppShell.tsx`) — gives you the sidebar, topbar,
   trial banner, toast viewport. Public marketing pages use `<PublicNav />`
   + `<Footer />` directly. Auth screens (login/signup) use
   `<AuthShell>`.

4. **Add a nav link.** If the page belongs in the sidebar, add an entry to
   `useNavGroups()` in `AppShell.tsx` (line 60). Pick the right group
   (`Feed`, `Guide`, `Analyse`, `Compte`).

5. **i18n strings.** Add page-title and any literal copy to
   `frontend/src/locales/fr/common.json` under a new key namespace
   (`"myPage": { "title": "…" }`). Mirror an empty entry in `en/common.json`
   so the migration audit picks it up.

---

## 7. How to add a new component

- **Where.** Pick the closest domain folder under `components/`. New
  generic primitives go in `components/ui/`. New signal-specific bits go in
  `components/signals/`. Don't dump everything in `ui/`.
- **Naming.** PascalCase, one component per file, filename matches the
  exported component (`SignalCard.tsx` → `export function SignalCard`).
- **Props.** Type via a local `type Props = { … }` (the codebase prefers
  `type` over `interface` — see `SignalCard.tsx` line 12 for the canonical
  example). Optional props get defaults inline:
  `function Foo({ variant = "default" }: FooProps)`.
- **Export style.** Named export for everything except pages. Pages
  default-export so `React.lazy(() => import("./pages/X"))` works.
  `Button` is the one exception in `ui/` — it uses `forwardRef` + named
  export plus a separately exported `buttonVariants` (see
  `components/ui/Button.tsx`).
- **Storybook.** Not used. There are no `*.stories.tsx` files. If you want
  to preview a component in isolation, add it to `pages/SignalVariants.tsx`
  (the dev-only preview page mounted at `/signal-variants`).
- **Tests.** Colocated under `__tests__/` siblings to the component
  (e.g. `components/signals/__tests__/OrderForm.test.tsx`). Use Vitest
  + `@testing-library/react`. Setup file is `src/test-setup.ts`.

---

## 8. API integration

**Client:** `frontend/src/lib/api/client.ts`. Four exports:
`apiGet<T>`, `apiPost<T>`, `apiPut<T>`, `apiDelete<T>`. All return
`Promise<T>` and throw `ApiError` (with `.status` and `.body`) on non-2xx.

```ts
import { apiGet } from "@/lib/api/client"
import type { MeResponse } from "@/lib/api/auth"

const me = await apiGet<MeResponse>("/auth/me")
```

Per-domain modules (thin wrappers around the four primitives) live in
`frontend/src/lib/api/`:

- `auth.ts` — login, register, Google, `fetchMe`, `putProfile`, `putPreferences`
- `paper.ts` — paper-trading portfolio
- `portfolio.ts` — real positions
- `performance.ts` — `/performance` aggregates
- `trading.ts`, `wallet.ts`, `quota.ts`, `limits.ts`, `subscriptions.ts`

**Base URL:** `import.meta.env.VITE_API_URL ?? "/api"`. In dev the Vite
proxy in `vite.config.ts` forwards `/api` to `:8001`. In prod nginx routes
it (see `frontend/nginx.conf`).

**Auth:** Bearer token from `localStorage[STORAGE_KEYS.token]`
(`"foresight.token"`). The client reads it on every call — no memoisation
— so login/logout are reflected immediately. Token is set via
`setToken()` in `lib/api/auth.ts` after a successful login. A 401 on
`fetchMe()` clears the token and falls through to the `RequireAuth` guard.

**Server state:** TanStack Query is mounted in `main.tsx` with
`staleTime: 60_000`, `retry: 1`, `refetchOnWindowFocus: false`. Wrap fetches
in `useQuery` (see `hooks/usePerformance.ts` for the pattern). The
60-second staleTime is what stops navigation flashing a loading state;
override per-query when you genuinely need fresher data.

**Error UX:** two layers.

1. **Per-route `<ErrorBoundary>`** wraps every route in `App.tsx` so a
   render-time throw shows a scoped fallback inside the otherwise intact
   shell. Root-level boundary in `main.tsx` is the last-resort net.
2. **Toasts** for transient async errors. Import `useToasts()` from
   `lib/useToasts.tsx` and call `push({ kind: "error", message: "…" })`.
   The viewport (`<ToastViewport />`) is mounted at the shell level.

**WebSockets:** not currently wired in the frontend. The Pricing page
mentions a "REST + WebSocket" API tier, but that is API-product copy, not
an in-app subscription. Live signals refresh today via React Query
polling (per-page opt-in to `refetchInterval`).

---

## 9. Common gotchas

- **`prefers-reduced-motion`.** Always go through `useMotionConfig()` /
  `useStagger()` (`lib/motion.ts`) rather than reading `useReducedMotion()`
  raw, and never set a hardcoded duration. The `globals.css` global reset
  is the safety net, but Framer animations driven by JS values bypass CSS
  and need the hook.
- **390 px first.** A layout that "works at desktop" almost always breaks
  at 390 px because `lg:` breakpoint logic flips the sidebar to a drawer.
  Open DevTools, set the viewport to 390 × 844, and walk the screen before
  declaring done.
- **WCAG contrast on Cosmic Night.** Ratios are tight. `ink-dim`
  (`#6B6E79`) on `obsidian-900` fails AA for body text — use
  `ink-readable` (`#8A8D99`) or `ink-muted` (`#A1A3AC`). Always check new
  colour pairs.
- **i18n.** Never hardcode a French string in new code. Always
  `t("namespace.key")`. The codebase has legacy hardcoded strings — do not
  copy that pattern, migrate when you touch the file.
- **Currency.** USD is the canonical unit in state. EUR is a display-time
  conversion. Do not store EUR amounts. The mocked rate (`0.92`) lives in
  `formatCurrency.ts` — when the backend ships real FX, swap that constant
  for a value off `useUserPreferences()`.
- **localStorage keys.** Never inline a string like `"foresight.token"`.
  Always `STORAGE_KEYS.token` from `lib/storageKeys.ts`. This module is the
  one place renames happen.
- **Wallet code is lazy.** wagmi + viem are NOT mounted at the root —
  `<WalletScope>` (`lib/WalletScope.tsx`) wraps the two surfaces that
  need them (OrderForm, Settings wallet section) so wagmi tree-splits into
  those lazy chunks. Don't import wagmi at the page level.
- **Vendor chunking.** `vite.config.ts` has explicit `manualChunks` for
  React, TanStack Query, Framer Motion, i18next, Recharts, wagmi. If you
  add a new heavy dependency, decide whether it gets its own chunk or
  rides with the importing page chunk.
- **Lint.** `--max-warnings 0`. Lint failures block PRs. There is no
  Prettier — ESLint owns formatting via the `react`/`react-hooks` plugin
  defaults and the `@typescript-eslint` rules.
- **Skip-link.** Every page must expose `<main id="main">` because the
  global "Aller au contenu" skip-link in `App.tsx` targets `#main`.
  `AppShell` already does this for you.

---

## 10. Where to dig deeper

- **`frontend/src/docs/voice-guide.md`** — copywriting voice, French
  typography rules, Polymarket-partnership wording, anglicisms allowed vs
  banned. Read this before writing any user-facing string.
- **`BLUEPRINT.md`** (repo root) — full system blueprint. Sections 13 and
  14 cover the frontend pages/routes and component/data layer in detail.
- **`frontend/tailwind.config.ts`** — every design token. Cite this file
  when reviewing colour or spacing PRs.
- **`frontend/src/lib/motion.ts`** — motion contract. If a component
  introduces a new duration, push it into this file rather than inlining.
- **`frontend/src/lib/storageKeys.ts`** — every localStorage / sessionStorage
  key. Touchstone for any auth, onboarding, or persistence change.
- **`frontend/src/types/signal.ts`** — domain types (`Signal`, `Position`,
  `OrderDraft`, `PerformanceStats`, `UserPreferences`). The shape of the
  product, in one file.
- **`docs/architecture.md`** — _not yet written._ When it lands, it will
  cover the full backend ↔ frontend system view.
- **`docs/decisions.md`** — _not yet written._ Will host product/UX
  decisions (DEC-002 i18n strategy, DEC-005 "Prendre position" wording,
  etc.).
