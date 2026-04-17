# Foresight Frontend Premium Redesign

**Date:** 2026-04-15
**Status:** Approved
**Approach:** Finary DNA + Identite Foresight (Approche B)
**Target:** Fintech moderne luxe — niveau visuel Finary.com
**User persona:** Investisseur curieux / semi-pro sur Polymarket

---

## 1. Design System

### 1.1 Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `surface-0` | `#050A12` | Background principal |
| `surface-card` | `#0C1222` | Cards, panels |
| `surface-raised` | `#111A2E` | Elements sureleves, hover states |
| `surface-glass` | `rgba(12,18,34,0.7)` + blur 20px | Overlays, modals, nav sticky |
| `accent-gold` | `#E8A843` | Accent principal |
| `accent-gold-bright` | `#F5C55A` | Hover, highlights |
| `accent-gold-glow` | `rgba(232,168,67,0.15)` | Glow derriere les elements cles |
| `accent-teal` | `#0EC6D6` | Accent secondaire — data, IA |
| `accent-teal-glow` | `rgba(14,198,214,0.12)` | Glow pour data-viz |
| `success` | `#34D399` | BUY YES, gains, positif |
| `danger` | `#F87171` | BUY NO, pertes, alertes |
| `text-primary` | `#F1F3F7` | Titres, texte principal |
| `text-secondary` | `#8B95A8` | Sous-titres, labels |
| `text-muted` | `#4A5568` | Hints, placeholders |
| `border-subtle` | `rgba(255,255,255,0.06)` | Bordures cards |
| `border-accent` | `rgba(232,168,67,0.25)` | Bordures accentuees |

Key gradients:
- **Hero gradient**: radial from center, `accent-gold-glow` to transparent
- **Text gradient**: `linear-gradient(135deg, #E8A843, #F5C55A, #0EC6D6)` for hero titles
- **Card hover**: border transitions from `border-subtle` to `border-accent` over 300ms

### 1.2 Typography

| Role | Font | Weights | Sizes |
|------|------|---------|-------|
| Display | **Satoshi** | 700, 800 | 48-72px hero, 32-40px section titles |
| Body | **Inter** | 400, 500, 600 | 14-18px body, 12-13px labels |
| Mono | **JetBrains Mono** | 400, 500 | 13-16px numbers, prices, scores |

Satoshi replaces Plus Jakarta Sans as the display font. More geometric character, similar spirit to Telegraf (Finary) with a technical edge.

### 1.3 Spacing & Layout

- Container max-width: 1280px centered
- Section padding: 80px vertical (desktop), 48px (mobile)
- Card gaps: 20-24px
- Border radius: 16px cards, 12px buttons (pill), 8px badges
- Sidebar width: 260px (desktop)

### 1.4 Base Components

**Buttons:**
- Primary: pill-shaped (radius 12px), `accent-gold` fill, dark text, hover: slight lift + glow
- Secondary: pill outline, `accent-gold` border, gold text, hover: subtle fill
- Ghost: no border, `text-secondary`, hover: `surface-raised` background

**Cards:**
- Background `surface-card`, border `border-subtle`, radius 16px
- Hover: border to `border-accent`, `accent-gold-glow` shadow, translateY -2px
- Clean and solid — no heavy glassmorphism

**Badges:**
- Pill shape with semi-transparent category color background (10% opacity) + colored text
- Smaller and more discrete than current

---

## 2. Landing Page (complete rebuild)

### 2.1 Navbar (sticky)

- Transparent background, transitions to `surface-glass` on scroll (backdrop-blur 20px)
- Logo "Foresight" left (Satoshi 700)
- Links: Fonctionnalites, Performance, Pricing (smooth scroll anchors)
- Right CTAs: "Se connecter" (ghost) + "Commencer gratuitement" (gold pill)

### 2.2 Hero Section

- Title: Satoshi 800, 56-64px, text gradient gold-to-teal
- Subtitle: Inter 400, 18px, `text-secondary`, max-width 560px
- 2 CTAs: "Commencer gratuitement" (gold pill) + "Voir le track record" (outline pill)
- Social proof line: dynamic values from `/api/analytics/track-record` (public endpoint): "{total_signals} signaux generes - {accuracy}% de precision - {resolved} resolus"
- Visual: real dashboard screenshot in a frame with radial gold glow behind
- Background: radial gold gradient, subtle and diffused

### 2.3 Trusted By

- Logo/badge strip included: "Polymarket", "Powered by GPT-4", news source icons (Reuters, AP, Bloomberg)
- Infinite horizontal scroll via CSS keyframes, 40% opacity
- Section sits between hero and "How It Works"

### 2.4 How It Works (3 steps)

- Title: "De l'evenement au signal en quelques secondes"
- 3 bento cards with number, icon, title, description:
  1. "Nos agents scannent" — 6 AI agents monitor global sources 24/7
  2. "L'analyse genere un signal" — Conviction score, direction, timing calculated
  3. "Tu trades en un clic" — Actionable signal on Polymarket
- Scroll-reveal staggered animation (100ms offset)

### 2.5 Bento Features Grid (2x3 asymmetric)

- Title: "Tout ce qu'il faut pour avoir un edge"
- Asymmetric bento grid (Finary-style):
  - **Large card (2 cols)**: "Signaux temps reel" — SignalCard preview + live indicator
  - **Standard card**: "6 Agents IA" — simplified pipeline visual
  - **Standard card**: "Analytics avances" — mini chart preview
  - **Large card (2 cols)**: "Track record verifiable" — accuracy stats + mini graph
  - **Standard card**: "Alertes Telegram"
  - **Standard card**: "Trading integre"
- Cards: `surface-card`, hover with gold border, scroll-reveal

### 2.6 Performance Section (live data)

- Title: "Des resultats, pas des promesses"
- 3 large animated counters (Satoshi 800 + JetBrains Mono): win rate, resolved signals, best streak
- Data from `/api/analytics/track-record` (public endpoint, no auth)
- Mini table below: last 5-6 resolved signals with green/red result
- CTA: "Voir le track record complet"

### 2.7 Pricing Section

- Title: "Un plan pour chaque ambition"
- 3 cards side by side, middle (Pro) highlighted with gold border + "Populaire" badge
- Modular design: features are props, easy to update
- Buttons: "Commencer" (free), "Essayer Pro" (gold), "Passer Trader" (outline)
- Note: "Annulable a tout moment. Paiement securise par Stripe."

### 2.8 Final CTA Section

- Radial gold gradient background
- Title: "Pret a trader avec un avantage ?"
- Single CTA: "Creer mon compte gratuitement" (large gold pill)

### 2.9 Footer

- 3 columns: Produit, Ressources, Legal
- Logo + "(c) 2026 Foresight"
- Social media icon links

---

## 3. App Layout & Navigation

### 3.1 Sidebar (desktop)

- Width: 260px, background `surface-0`, right border `border-subtle`
- Logo: "Foresight" Satoshi 700 20px + optional "BETA" teal badge
- Navigation groups with `text-muted` uppercase 11px tracking-wide labels:
  - TRADING: Dashboard, Opportunites, Marches, Portfolio
  - INTELLIGENCE: Performance, Track Record, Briefs
  - IA: Agents, Workspace
  - COMPTE: Parametres, Abonnement
- Active state: `surface-raised` background + 2px left border `accent-gold` + `text-primary`
- Inactive: `text-secondary`, hover to `text-primary`
- User card at bottom: initial avatar (gold-to-teal gradient circle) + truncated email + plan badge + logout

### 3.2 Mobile Nav (bottom bar)

- 5 icons max: Dashboard, Opportunites, Performance, Agents, Plus (menu)
- Background `surface-glass` with backdrop-blur
- Active icon: `accent-gold` with luminous dot below
- "Plus" opens a bottom drawer with remaining pages

### 3.3 Page Transitions

- Framer Motion AnimatePresence: fade-in + slide-up 8px, 200ms, easing `[0.25, 0.1, 0.25, 1]`

### 3.4 Page Header Pattern

- Title: Satoshi 700, 28px
- Subtitle: Inter 400, 15px, `text-secondary`
- Right-side actions (filters, contextual buttons)
- Separator: `border-subtle` line with 24px margin below

### 3.5 Content Container

- Max-width: 1120px centered in the space right of sidebar
- Padding: 32px horizontal, 28px vertical
- On wide screens (>1440px): content stays centered, does not stretch

---

## 4. Dashboard

### 4.1 KPI Zone (top)

4 MetricCards in horizontal grid (4 cols desktop, 2x2 mobile):

| Metric | Style |
|--------|-------|
| Signaux aujourd'hui | JetBrains Mono 600 32px + Zap icon teal |
| Win Rate | Percentage + mini 7-day sparkline |
| Score moyen | Number + miniature ScoreRing |
| Serie en cours | Dynamic color success/danger ("5W" / "3L") |

Cards: `surface-card`, padding 24px, radius 16px. Stagger appearance 60ms.

### 4.2 Main Zone: 2 columns (70/30)

**Left column (70%) — Signal Feed:**
- Section header: "Derniers signaux" + live badge (green pulse + "Live") + "Voir tout" link
- 5-6 SignalCards visible without scrolling
- SignalCard design:
  - 3px left border colored by category
  - Line 1: category badge (pill) + timestamp + direction badge
  - Line 2: event title, Satoshi 600 16px, max 2 lines
  - Line 3: market question, Inter 400 14px, 1 line truncated
  - Line 4: conviction score bar, smooth fill animation
  - Line 5: footer — YES % (mono) + confidence + urgency + Polymarket link + "Trader" pill
  - Hover: border to gold, slight lift, gold shadow
  - New signal (WebSocket): flash-border gold + slide-in from top
- Pagination: "Previous - Page 1/4 - Next"

**Right column (30%) — Contextual sidebar:**
1. Quick Stats: global accuracy ScoreRing + resolved count
2. Top categories: 3-4 horizontal bars colored by category
3. Agent activity: last 3 actions (icon + text + timestamp) + "Voir les agents" link

**Responsive:** <1024px single column, sidebar becomes horizontal scrollable stat band above feed.

---

## 5. Signal Pages

### 5.1 Opportunities (signal list)

- Header: "Opportunites" + counter badge
- Filter bar: `surface-card` radius 12px, 3 pill-selects (category, min score, direction) + reset ghost button
- Grid: 2 columns desktop, 1 mobile
- Extended SignalCard: more title space, larger score with tier badge, explicit "Detail" button
- Stagger 40ms. Pagination: pill-style page numbers, active in gold.
- Empty state: minimal illustration + message + reset filters CTA

### 5.2 Signal Detail (OpportunityDetail)

**Layout: 2 columns (65/35)**

**Left (65%):**
1. Header: category badge + timestamp + direction + event title (Satoshi 700 24px) + market question + Polymarket link
2. Conviction score block: large ScoreRing (120px) + tier badge + signal strength bar + trade quality bar, in `surface-card`
3. AI Analysis: agent icon teal, formatted text Inter 400 15px lh 1.7, expandable if long
4. Outcomes table (if resolved): Outcome + initial price + final price + Correct/Incorrect badge

**Right (35%):**
1. Quick trade card: `surface-raised` + `border-accent`, large YES price (mono 28px), calculated edge, "Trader sur Polymarket" gold pill, disclaimer note
2. Market metrics: volume 24h, liquidity, spread, last trade
3. Price chart: Recharts line chart, 7d/30d toggle pills, `accent-teal` line, hover tooltip

**Mobile:** single column, trade card becomes sticky bottom bar.

---

## 6. Analytics & Secondary Pages

### 6.1 Performance

- 6 KPIs in 3x2 grid, each with integrated sparkline
- Charts (2 columns):
  - Score Distribution: vertical bar chart, gradient gold-to-teal
  - Win Rate by category: horizontal colored bars
  - Signal Timeline: area chart, `accent-teal` curve, gold peaks
  - Category breakdown: donut chart (180px) with right legend
- Custom Recharts style: no visible grid, `text-muted` axes, `surface-raised` tooltips
- Charts animate on scroll-reveal
- Bottom table: Win Rate by score tier, sortable DataTable

### 6.2 Portfolio

- Stats band: portfolio value + cash + total P&L (colored) + open positions count in `surface-card`
- Tabbed (pill tabs): Positions / Orders
- Positions: card grid (not table) — market question, side badge, size, entry/current price, P&L %, mini sparkline
- Orders: clean table — date, market, direction, amount, status badge pill (Filled green, Pending gold, Failed red)
- Empty state with link to opportunities

### 6.3 Agents

- Pipeline visual: horizontal flow Scout to Reporter, connected by lines with animated CSS dots
- Agent grid (3x2): avatar circle (unique gradient), name + role, status badge (active pulse / idle), description, last action, total actions stat
- Activity feed below: vertical timeline (line + dots), icon + text + timestamp, load more

### 6.4 Workspace (Agent Chat)

- Existing thread structure kept
- Enhanced input: pill slash-command suggestions above input when typing "/"
- Agent messages: `surface-raised` background + teal avatar
- User messages: subtle `accent-gold-glow` background
- Right activity sidebar aligned with new design system

### 6.5 Other Pages

| Page | Treatment |
|------|-----------|
| Briefs | Cards with large date, summary, integrated KPIs — newsletter card style |
| Track Record | Public page — same data as landing performance section, more detailed. Shareable. |
| Learn | Redesigned accordions — icons, spacing, premium FAQ style |
| Settings | Clean form, sections separated by dividers, custom toggles (not checkboxes) |
| Pricing | Reuses landing pricing component — total coherence |
| Markets | Improved DataTable: hover rows, clickable links, category badges |

---

## 7. Animations & Micro-interactions

### 7.1 Principles

- All subtle — if user consciously notices the animation, it's too much
- All fast — 150-300ms for UI transitions, 400-600ms for scroll-reveals
- All consistent — single easing everywhere: `cubic-bezier(0.25, 0.1, 0.25, 1)`

### 7.2 Animation Catalog

| Element | Animation | Duration |
|---------|-----------|----------|
| Page transition | Fade + slide-up 8px | 200ms |
| Cards scroll-reveal | Fade-in + slide-up 16px, stagger 60ms | 400ms |
| Signal card hover | Border gold, translateY -2px, shadow glow | 200ms |
| New signal (WS) | Slide-down + flash border gold | 500ms |
| Score bars | Fill left-to-right | 600ms |
| ScoreRing | stroke-dashoffset SVG | 800ms |
| Metric counters | Number spring (Framer useSpring) | 400ms |
| Button hover | Scale 1.02 + subtle glow | 150ms |
| Button click | Scale 0.97 | 100ms |
| Tab switch | Underline slide + content crossfade | 250ms |
| Filter change | Content crossfade (no layout jump) | 200ms |
| Charts | Draw-in on scroll | 800ms |
| Agent pipeline | Dots flowing between nodes (CSS keyframes) | Infinite, slow |
| Sidebar active link | Background slide (Framer layoutId) | 150ms |
| Toast/notification | Slide-in from right + auto-dismiss | 300ms in, 200ms out |

### 7.3 What We Don't Do

- No parallax scroll
- No canvas particles in background
- No page transitions >500ms
- No initial page load animations (only scroll-reveals)
- No hover effects on mobile

### 7.4 Performance Rules

- All CSS animations use `transform` and `opacity` only (GPU-composited)
- Framer Motion reserved for layout animations and complex enter/exit
- `will-change` on frequently animated elements (signal cards, score bars)
- Lazy load images and charts outside viewport

---

## 8. Technical Constraints

### 8.1 Backend Connection (unchanged)

All existing API endpoints remain connected:
- REST: `/api/signals`, `/api/markets`, `/api/analytics/*`, `/api/trading/*`, `/api/auth/*`, `/api/subscriptions/*`, `/api/agents/*`
- WebSocket: `/ws/signals`
- Vite proxy config unchanged (port 3001 -> 8001)

### 8.2 Stack

- React 18 + TypeScript (unchanged)
- Vite (unchanged)
- Tailwind CSS with updated config (new color tokens, fonts, spacing)
- Framer Motion (already installed, used more strategically)
- Recharts (kept, restyled)
- React Router v6 (unchanged)
- React Query (unchanged, same polling intervals)

### 8.3 New Dependencies

- `@fontsource/satoshi` or Google Fonts CDN for Satoshi font
- No other new dependencies expected

### 8.4 Files Impacted

Every file in `frontend/src/` will be modified:
- `tailwind.config.js` — complete color/font/spacing overhaul
- `index.css` — new global styles, font imports, utilities
- `index.html` — updated font preloads, meta tags
- All 12 UI components in `components/ui/`
- All 4 layout components in `components/layout/`
- All 3 signal components in `components/signals/`
- All 15 pages in `pages/`
- `App.tsx` — route structure adjustments for new landing
- Hooks and lib files remain structurally unchanged (API layer untouched)
