# Foresight Frontend Premium Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing Foresight frontend into a premium, Finary-inspired fintech interface while preserving all backend API connections.

**Architecture:** Incremental refactor — update the design system foundation first (Tailwind tokens, fonts, global CSS), then rebuild UI primitives, then layout, then pages. Backend API layer and hooks stay untouched. Every change must keep `npm run build` green.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, React Query, React Router v6. New font: Satoshi (via Fontshare CDN).

**Spec Reference:** `docs/superpowers/specs/2026-04-15-frontend-premium-redesign.md`

**Working directory:** `/Users/vadim/polymarket-ai/frontend/` — all paths below are relative to this unless noted.

**Verification strategy:** This frontend has no automated test suite. Verification per task = TypeScript compiles cleanly (`npm run build`) + no console errors. At milestone checkpoints we also verify the dev server renders (`npm run dev`).

---

## Phase Overview

| Phase | Scope | Tasks |
|-------|-------|-------|
| 1 | Design System Foundation | 1-3 |
| 2 | UI Primitives | 4-9 |
| 3 | Layout Components | 10-12 |
| 4 | Signal Components | 13-14 |
| 5 | Landing Page | 15-19 |
| 6 | App Pages | 20-29 |
| 7 | Final Verification | 30 |

---

## PHASE 1 — Design System Foundation

### Task 1: Update Tailwind config with new design tokens

**Files:**
- Modify: `tailwind.config.js` (complete rewrite)

- [ ] **Step 1: Replace `tailwind.config.js` with the new token system**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#050A12",
          card: "#0C1222",
          raised: "#111A2E",
          hover: "#152140",
          glass: "rgba(12,18,34,0.7)",
        },
        edge: {
          DEFAULT: "rgba(255,255,255,0.08)",
          subtle: "rgba(255,255,255,0.06)",
          accent: "rgba(232,168,67,0.25)",
          glow: "rgba(232,168,67,0.15)",
          teal: "rgba(14,198,214,0.2)",
        },
        accent: {
          DEFAULT: "#E8A843",
          bright: "#F5C55A",
          muted: "rgba(232,168,67,0.12)",
          glow: "rgba(232,168,67,0.15)",
        },
        teal: {
          DEFAULT: "#0EC6D6",
          bright: "#3DD8E6",
          muted: "rgba(14,198,214,0.12)",
          glow: "rgba(14,198,214,0.12)",
        },
        success: { DEFAULT: "#34D399", muted: "rgba(52,211,153,0.12)" },
        danger: { DEFAULT: "#F87171", muted: "rgba(248,113,113,0.12)" },
        warning: "#E8A843",
        info: "#0EC6D6",
        txt: {
          primary: "#F1F3F7",
          secondary: "#8B95A8",
          muted: "#4A5568",
        },
        cat: {
          geo: "#F87171",
          politics: "#818CF8",
          economics: "#34D399",
          crypto: "#FBBF24",
          sports: "#60A5FA",
          science: "#A78BFA",
          other: "#8B95A8",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        display: ["Satoshi", "Inter", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      letterSpacing: {
        display: "-0.02em",
        tight: "-0.01em",
        wide: "0.08em",
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        "2xl": "24px",
        pill: "9999px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)",
        "card-hover": "0 12px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(232,168,67,0.18)",
        glow: "0 0 24px rgba(232,168,67,0.15)",
        "glow-lg": "0 0 64px rgba(232,168,67,0.20)",
        "glow-teal": "0 0 24px rgba(14,198,214,0.15)",
        "inner-glow": "inset 0 1px 0 rgba(255,255,255,0.04)",
      },
      animation: {
        "pulse-live": "pulse-live 2s ease-in-out infinite",
        shimmer: "shimmer 1.8s infinite",
        "score-fill": "score-fill 0.6s cubic-bezier(0.25,0.1,0.25,1) forwards",
        "slide-down": "slide-down 0.35s cubic-bezier(0.25,0.1,0.25,1)",
        "slide-up": "slide-up 0.4s cubic-bezier(0.25,0.1,0.25,1) forwards",
        "flash-gold": "flash-gold 1.5s ease-out",
        "fade-up": "fade-up 0.4s cubic-bezier(0.25,0.1,0.25,1) forwards",
        "scale-in": "scale-in 0.3s cubic-bezier(0.25,0.1,0.25,1) forwards",
        "glow-pulse": "glow-pulse 2.5s ease-in-out infinite",
        "scroll-x": "scroll-x 40s linear infinite",
        "dot-flow": "dot-flow 3s linear infinite",
      },
      keyframes: {
        "pulse-live": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.5", transform: "scale(0.9)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "score-fill": {
          from: { width: "0%" },
          to: { width: "var(--score-width)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "flash-gold": {
          "0%": { boxShadow: "0 0 0 2px rgba(232,168,67,0.6), 0 0 32px rgba(232,168,67,0.3)" },
          "100%": { boxShadow: "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 24px rgba(232,168,67,0.12)" },
          "50%": { boxShadow: "0 0 40px rgba(232,168,67,0.24)" },
        },
        "scroll-x": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "dot-flow": {
          "0%": { transform: "translateX(0)", opacity: "0" },
          "10%": { opacity: "1" },
          "90%": { opacity: "1" },
          "100%": { transform: "translateX(100%)", opacity: "0" },
        },
      },
      backgroundImage: {
        "gradient-gold-teal":
          "linear-gradient(135deg, #E8A843 0%, #F5C55A 50%, #0EC6D6 100%)",
        "gradient-hero-radial":
          "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(232,168,67,0.18) 0%, transparent 60%)",
        "gradient-card-radial":
          "radial-gradient(ellipse at 0% 0%, rgba(232,168,67,0.08) 0%, transparent 50%)",
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 2: Build to verify TS + Tailwind still compile**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build completes without errors. Warnings about unused classes are acceptable.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add tailwind.config.js
git commit -m "feat(frontend): new Finary-inspired design tokens in Tailwind"
```

---

### Task 2: Update global CSS (fonts, body, utilities)

**Files:**
- Modify: `src/index.css` (complete rewrite)

- [ ] **Step 1: Replace `src/index.css` with the new global styles**

```css
/* Satoshi from Fontshare */
@import url('https://api.fontshare.com/v2/css?f[]=satoshi@700,800&display=swap');
/* Inter + JetBrains Mono */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: dark;
  }

  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
  }

  body {
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #050A12;
    color: #F1F3F7;
    line-height: 1.6;
    min-height: 100vh;
    position: relative;
    overflow-x: hidden;
  }

  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background:
      radial-gradient(ellipse 60% 50% at 15% 10%, rgba(232,168,67,0.05) 0%, transparent 50%),
      radial-gradient(ellipse 50% 40% at 85% 90%, rgba(14,198,214,0.04) 0%, transparent 50%);
  }

  ::selection {
    background: #E8A843;
    color: #050A12;
  }

  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.06);
    border-radius: 100px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: rgba(232,168,67,0.3);
  }

  input, select, textarea {
    font-family: "Inter", sans-serif;
    font-size: 0.9375rem;
    background: #0C1222;
    color: #F1F3F7;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 12px 16px;
    outline: none;
    transition: border-color 200ms cubic-bezier(0.25,0.1,0.25,1),
                box-shadow 200ms cubic-bezier(0.25,0.1,0.25,1),
                background 200ms cubic-bezier(0.25,0.1,0.25,1);
  }

  input:focus, select:focus, textarea:focus {
    border-color: rgba(232,168,67,0.45);
    box-shadow: 0 0 0 4px rgba(232,168,67,0.08);
    background: #111A2E;
  }

  input::placeholder, textarea::placeholder {
    color: #4A5568;
  }

  select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0l5 6 5-6' fill='%238B95A8'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 14px center;
    padding-right: 36px;
  }

  h1, h2, h3, h4 {
    font-family: "Satoshi", "Inter", sans-serif;
    letter-spacing: -0.02em;
    line-height: 1.15;
  }
}

@layer components {
  .card {
    background: #0C1222;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    transition: border-color 300ms cubic-bezier(0.25,0.1,0.25,1),
                box-shadow 300ms cubic-bezier(0.25,0.1,0.25,1),
                transform 300ms cubic-bezier(0.25,0.1,0.25,1);
  }

  .card-hover:hover {
    border-color: rgba(232,168,67,0.25);
    box-shadow: 0 12px 32px rgba(0,0,0,0.5), 0 0 32px rgba(232,168,67,0.08);
    transform: translateY(-2px);
  }

  .glass {
    background: rgba(12,18,34,0.7);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.06);
  }

  .text-gradient-gold-teal {
    background: linear-gradient(135deg, #E8A843 0%, #F5C55A 50%, #0EC6D6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .text-gradient-gold {
    background: linear-gradient(135deg, #E8A843 0%, #F5C55A 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 12px;
    background: #E8A843;
    color: #050A12;
    font-weight: 600;
    font-size: 0.9375rem;
    border: none;
    cursor: pointer;
    transition: all 150ms cubic-bezier(0.25,0.1,0.25,1);
  }

  .btn-primary:hover {
    background: #F5C55A;
    box-shadow: 0 0 24px rgba(232,168,67,0.3);
    transform: translateY(-1px);
  }

  .btn-primary:active {
    transform: scale(0.97);
  }

  .btn-outline {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 12px;
    background: transparent;
    color: #E8A843;
    font-weight: 600;
    font-size: 0.9375rem;
    border: 1px solid rgba(232,168,67,0.5);
    cursor: pointer;
    transition: all 150ms cubic-bezier(0.25,0.1,0.25,1);
  }

  .btn-outline:hover {
    background: rgba(232,168,67,0.08);
    border-color: #E8A843;
  }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 20px;
    border-radius: 12px;
    background: transparent;
    color: #8B95A8;
    font-weight: 500;
    font-size: 0.9375rem;
    border: none;
    cursor: pointer;
    transition: all 150ms cubic-bezier(0.25,0.1,0.25,1);
  }

  .btn-ghost:hover {
    background: #111A2E;
    color: #F1F3F7;
  }

  .hero-radial {
    background: radial-gradient(ellipse 80% 60% at 50% 30%, rgba(232,168,67,0.18) 0%, transparent 60%);
  }

  .section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
  }
}

@layer utilities {
  .font-tabular { font-variant-numeric: tabular-nums; }
  .text-balance { text-wrap: balance; }
  .will-change-transform { will-change: transform; }
}

@media (max-width: 768px) {
  body {
    -webkit-user-select: none;
    user-select: none;
    -webkit-touch-callout: none;
    overscroll-behavior-y: contain;
  }
}

@media (display-mode: standalone) {
  body {
    padding-top: env(safe-area-inset-top, 0px);
  }
}
```

- [ ] **Step 2: Build to verify everything compiles**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/index.css
git commit -m "feat(frontend): global CSS with Satoshi font + premium utility classes"
```

---

### Task 3: Update index.html (fonts + meta)

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Update the `<head>` font preconnects to include Fontshare**

Replace lines 10-12 with:

```html
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link rel="preconnect" href="https://api.fontshare.com" crossorigin />
    <link rel="preconnect" href="https://cdn.fontshare.com" crossorigin />
    <link href="https://api.fontshare.com/v2/css?f[]=satoshi@700,800&display=swap" rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Build to verify**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add index.html
git commit -m "feat(frontend): preload Satoshi font from Fontshare"
```

---

## PHASE 2 — UI Primitives

### Task 4: Redesign Button component

**Files:**
- Modify: `src/components/ui/Button.tsx` (complete rewrite)

- [ ] **Step 1: Replace `Button.tsx` with new pill-shaped variants**

```tsx
import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
  icon?: ReactNode
  iconPosition?: "left" | "right"
  isLoading?: boolean
  fullWidth?: boolean
}

const variants: Record<string, string> = {
  primary:
    "bg-accent text-surface-0 hover:bg-accent-bright hover:shadow-glow hover:-translate-y-px active:translate-y-0 active:scale-[0.97]",
  secondary:
    "bg-transparent text-accent border border-accent/50 hover:bg-accent/8 hover:border-accent active:scale-[0.97]",
  ghost:
    "bg-transparent text-txt-secondary hover:bg-surface-raised hover:text-txt-primary active:scale-[0.97]",
  danger:
    "bg-danger/15 text-danger border border-danger/30 hover:bg-danger/25 active:scale-[0.97]",
}

const sizes: Record<string, string> = {
  sm: "px-4 py-2 text-xs rounded-md",
  md: "px-5 py-2.5 text-sm rounded-[12px]",
  lg: "px-7 py-3.5 text-base rounded-[14px]",
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" className="opacity-90" />
    </svg>
  )
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  iconPosition = "left",
  children,
  className,
  isLoading = false,
  fullWidth = false,
  disabled,
  ...rest
}: Props) {
  const isDisabled = disabled || isLoading
  return (
    <button
      type="button"
      disabled={isDisabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-semibold transition-all duration-150",
        "disabled:pointer-events-none disabled:opacity-50",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        variants[variant],
        sizes[size],
        fullWidth && "w-full",
        className,
      )}
      aria-busy={isLoading || undefined}
      {...rest}
    >
      {isLoading && <Spinner />}
      {!isLoading && icon && iconPosition === "left" && icon}
      {children}
      {!isLoading && icon && iconPosition === "right" && icon}
    </button>
  )
}
```

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/Button.tsx
git commit -m "feat(frontend): redesign Button with pill variants"
```

---

### Task 5: Redesign Card component

**Files:**
- Modify: `src/components/ui/Card.tsx`

- [ ] **Step 1: Replace `Card.tsx` with clean solid card**

```tsx
import type { CSSProperties, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props {
  children: ReactNode
  className?: string
  style?: CSSProperties
  hover?: boolean
  padding?: "sm" | "md" | "lg" | "none"
  as?: "div" | "article" | "section"
}

const paddings: Record<string, string> = {
  none: "",
  sm: "p-4",
  md: "p-5 md:p-6",
  lg: "p-6 md:p-8",
}

export function Card({
  children,
  className,
  style,
  hover = false,
  padding = "md",
  as: Component = "div",
}: Props) {
  return (
    <Component
      className={cn(
        "card",
        hover && "card-hover",
        paddings[padding],
        className,
      )}
      style={style}
    >
      {children}
    </Component>
  )
}
```

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/Card.tsx
git commit -m "feat(frontend): redesign Card with solid premium surface"
```

---

### Task 6: Redesign Badge, CategoryBadge, DirectionBadge

**Files:**
- Modify: `src/components/ui/Badge.tsx`
- Modify: `src/components/ui/CategoryBadge.tsx`
- Modify: `src/components/ui/DirectionBadge.tsx`

- [ ] **Step 1: Replace `Badge.tsx` with refined pill badge**

```tsx
import type { CSSProperties, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props {
  children?: ReactNode
  label?: string
  color?: string
  bg?: string
  size?: "xs" | "sm" | "md"
  variant?: "filled" | "outline" | "soft"
  style?: CSSProperties
  className?: string
}

export function Badge({
  children,
  label,
  color,
  bg,
  size = "sm",
  variant = "soft",
  style,
  className,
}: Props) {
  const pad =
    size === "xs"
      ? "px-2 py-0.5 text-[10px]"
      : size === "sm"
      ? "px-2.5 py-1 text-[11px]"
      : "px-3 py-1.5 text-xs"

  const baseColor = color ?? "#8B95A8"

  let bgColor = bg
  let borderColor = "transparent"
  if (!bgColor) {
    if (variant === "filled") {
      bgColor = baseColor
    } else if (variant === "outline") {
      bgColor = "transparent"
      borderColor = `${baseColor}40`
    } else {
      bgColor = `${baseColor}18`
      borderColor = `${baseColor}26`
    }
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-semibold uppercase tracking-wider whitespace-nowrap",
        pad,
        className,
      )}
      style={{
        color: variant === "filled" ? "#050A12" : baseColor,
        background: bgColor,
        border: `1px solid ${borderColor}`,
        ...style,
      }}
    >
      {children ?? label}
    </span>
  )
}
```

- [ ] **Step 2: Read existing CategoryBadge**

Run: `cat /Users/vadim/polymarket-ai/frontend/src/components/ui/CategoryBadge.tsx`

- [ ] **Step 3: Update CategoryBadge to use new Badge variants**

Keep the same exports and props signature. Internally it should use the new `Badge` with `size="sm"` `variant="soft"` and render emoji + label. Preserve the existing imports from `constants.ts` (`BUCKETS`, `inferBucketFromQuestion`).

Example shape:
```tsx
import { Badge } from "./Badge"
import { BUCKETS, inferBucketFromQuestion } from "../../lib/constants"

interface Props {
  bucket?: string
  question?: string
  size?: "xs" | "sm" | "md"
  className?: string
}

export function CategoryBadge({ bucket, question, size = "sm", className }: Props) {
  const resolvedBucket = bucket ?? (question ? inferBucketFromQuestion(question) : "other")
  const meta = BUCKETS.find((b) => b.id === resolvedBucket) ?? BUCKETS[BUCKETS.length - 1]
  return (
    <Badge size={size} color={meta.color} className={className}>
      <span>{meta.emoji}</span>
      <span>{meta.label}</span>
    </Badge>
  )
}
```

Ensure the actual props/imports match what the codebase exposes — if `CategoryBadge` currently accepts different props, adjust to keep the public API identical to avoid downstream breakage.

- [ ] **Step 4: Update DirectionBadge to use new pill styling**

```tsx
import { cn } from "../../lib/utils"

interface Props {
  direction: "BUY_YES" | "BUY_NO" | "YES" | "NO" | string
  size?: "xs" | "sm" | "md"
  className?: string
  animated?: boolean
}

export function DirectionBadge({ direction, size = "sm", className, animated = false }: Props) {
  const isYes = direction === "BUY_YES" || direction === "YES"
  const label = isYes ? "BUY YES" : "BUY NO"
  const pad =
    size === "xs"
      ? "px-2 py-0.5 text-[10px]"
      : size === "sm"
      ? "px-2.5 py-1 text-[11px]"
      : "px-3 py-1.5 text-xs"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-bold uppercase tracking-wider",
        pad,
        isYes
          ? "bg-success/15 text-success border border-success/25"
          : "bg-danger/15 text-danger border border-danger/25",
        animated && "animate-pulse-live",
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", isYes ? "bg-success" : "bg-danger")} />
      {label}
    </span>
  )
}
```

- [ ] **Step 5: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds. If TypeScript errors surface in callers, inspect them and update callers to match the new prop shapes (but prefer keeping old prop names backward-compatible).

- [ ] **Step 6: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/Badge.tsx src/components/ui/CategoryBadge.tsx src/components/ui/DirectionBadge.tsx
git commit -m "feat(frontend): redesign Badge + CategoryBadge + DirectionBadge"
```

---

### Task 7: Redesign MetricCard + StatCard with sparkline support

**Files:**
- Modify: `src/components/ui/MetricCard.tsx`
- Modify: `src/components/ui/StatCard.tsx`

- [ ] **Step 1: Read existing files**

Run:
```
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/MetricCard.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/StatCard.tsx
```

- [ ] **Step 2: Rewrite MetricCard**

Keep the existing exports/props signature but upgrade visual. The component should accept: `label` (string), `value` (string | number), `icon?` (ReactNode), `sublabel?` (string), `trend?` ("up" | "down" | "flat"), `sparkline?` (number[]), `accent?` ("gold" | "teal" | "success" | "danger"), `className?`.

Visual spec:
- `Card` container with `padding="md"`, `hover={false}`
- Top row: icon (if present, 20px, accent color) + `label` in `text-txt-secondary text-xs uppercase tracking-wider font-semibold`
- Main value: Satoshi 700 (`font-display`) or JetBrains Mono 600 (`font-mono`) at `text-3xl md:text-4xl`, color `text-txt-primary`. Use `font-mono` for numeric values, `font-display` for short words.
- Sublabel (if present): `text-txt-muted text-xs` below value
- Sparkline (if present): render a tiny inline SVG polyline (width 80, height 24) in `stroke-accent` or `stroke-teal` based on `accent` prop. Normalize values to the 0-24 range.
- Trend indicator (if `trend` provided without sparkline): small arrow in success/danger color

- [ ] **Step 3: Rewrite StatCard**

Similar to MetricCard but more compact (smaller value, one line per stat). Accept `label` (string), `value` (string | number), `change?` (string — e.g. "+12.4%"), `changeKind?` ("positive" | "negative" | "neutral"), `className?`. Keep existing exports.

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/MetricCard.tsx src/components/ui/StatCard.tsx
git commit -m "feat(frontend): premium MetricCard + StatCard with sparklines"
```

---

### Task 8: Redesign ScoreBar + ScoreRing

**Files:**
- Modify: `src/components/ui/ScoreBar.tsx`
- Modify: `src/components/ui/ScoreRing.tsx`

- [ ] **Step 1: Read existing files**

Run:
```
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/ScoreBar.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/ScoreRing.tsx
```

- [ ] **Step 2: Rewrite ScoreBar**

Preserve props: `score` (0-100), optional `signalStrength` (0-100), optional `tradeQuality` (0-100), optional `showDetails` (boolean), `className?`.

Visual spec:
- Main bar height 6px, `rounded-full`, background `bg-surface-raised`
- Fill uses `animate-score-fill` keyframe, gradient background: gold if score>=70, `accent` solid if 50-69, muted `#8B95A8` below 50
- Numeric score displayed to the right in `font-mono font-semibold text-sm`
- If `showDetails` and sub-scores provided: render two thinner bars (3px) below with labels "Signal" + "Trade" in `text-[10px] text-txt-muted uppercase tracking-wider`
- Use `--score-width` CSS variable inline style for animated fill (`style={{ ['--score-width' as string]: \`${score}%\` }}`)

- [ ] **Step 3: Rewrite ScoreRing**

Preserve props: `score` (0-100), `size?` (default 64), `strokeWidth?` (default 5), `showLabel?` (boolean), `className?`.

Visual spec:
- SVG circle, track `stroke-surface-raised`, progress stroke colored by score tier (same logic as ScoreBar fill)
- `stroke-dasharray`/`stroke-dashoffset` animated via CSS transition `stroke-dashoffset 800ms cubic-bezier(0.25,0.1,0.25,1)`
- Center label: score number in `font-mono font-bold`, size scales with `size` prop

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/ScoreBar.tsx src/components/ui/ScoreRing.tsx
git commit -m "feat(frontend): premium ScoreBar + ScoreRing with smooth fills"
```

---

### Task 9: Redesign DataTable + EmptyState + Skeleton

**Files:**
- Modify: `src/components/ui/DataTable.tsx`
- Modify: `src/components/ui/EmptyState.tsx`
- Modify: `src/components/ui/Skeleton.tsx`

- [ ] **Step 1: Read existing files**

Run:
```
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/DataTable.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/EmptyState.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/ui/Skeleton.tsx
```

- [ ] **Step 2: Update DataTable styling**

Keep props/API identical. Visual updates only:
- Header row: `bg-surface-card` with `border-b border-edge-subtle`, labels in `text-txt-muted text-[11px] uppercase tracking-wider font-semibold`
- Body rows: alternating `bg-transparent` / `bg-surface-card/40`, `hover:bg-surface-raised` with 150ms transition
- Cell padding: `px-4 py-3`
- Table rounded-2xl overflow-hidden wrapper with `border border-edge-subtle`
- Sort indicators in `text-accent` when active

- [ ] **Step 3: Update EmptyState**

Preserve props. Visual spec:
- Centered column, `py-16`
- Icon circle (64px) with `bg-surface-raised` and centered accent icon (24px)
- Title in `font-display font-bold text-lg text-txt-primary mt-5`
- Description in `text-txt-secondary text-sm max-w-sm text-center mt-2`
- Optional CTA button below

- [ ] **Step 4: Update Skeleton**

Preserve props. Replace animation with subtle shimmer using `bg-surface-raised` base + gold shimmer overlay:
- Base: `bg-surface-raised rounded-md`
- Overlay pseudo-element or inner div with `shimmer` animation + `linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)`
- Accept `height`, `width`, `className`, `circle?` (boolean) props

- [ ] **Step 5: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/ui/DataTable.tsx src/components/ui/EmptyState.tsx src/components/ui/Skeleton.tsx
git commit -m "feat(frontend): refine DataTable + EmptyState + Skeleton styling"
```

---

## PHASE 3 — Layout Components

### Task 10: Redesign Sidebar

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Read existing file**

Run: `cat /Users/vadim/polymarket-ai/frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 2: Rewrite Sidebar with grouped nav, new styling**

Keep the existing exports and route definitions compatible with `App.tsx`. Visual spec per the design doc section 3.1:
- Width: `w-[260px]` fixed, `bg-surface-0`, `border-r border-edge-subtle`
- Logo block at top: `Foresight` in `font-display font-bold text-[20px]` + optional BETA pill (`variant="soft" color="#0EC6D6"`)
- Navigation groups with labels in `text-txt-muted text-[11px] uppercase tracking-wide font-semibold px-3 mb-2 mt-6` (first group has `mt-4`)
  - TRADING: Dashboard, Opportunités, Marchés, Portfolio
  - INTELLIGENCE: Performance, Track Record, Briefs
  - IA: Agents, Workspace
  - COMPTE: Paramètres, Abonnement (links to `/pricing` if that's the abonnement page)
- Each nav link:
  - Container: `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150`
  - Icon: 18px from `lucide-react` (pick appropriate icons)
  - Inactive: `text-txt-secondary hover:text-txt-primary hover:bg-surface-card`
  - Active: `bg-surface-raised text-txt-primary relative` with a `before:` pseudo-element creating a 2px `bg-accent` left border at `left-0 top-2 bottom-2 rounded-r`
- User card at bottom (absolute bottom, `p-4 border-t border-edge-subtle`):
  - Avatar: 36px circle with `bg-gradient-to-br from-accent to-teal` + initial letter in dark
  - Email truncated + plan badge next to avatar
  - Logout button: ghost icon button right-aligned
- Use `NavLink` from `react-router-dom` for active state management. Use `useAuth` for the user info.

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/layout/Sidebar.tsx
git commit -m "feat(frontend): redesign Sidebar with grouped navigation"
```

---

### Task 11: Redesign MobileNav

**Files:**
- Modify: `src/components/layout/MobileNav.tsx`

- [ ] **Step 1: Read existing file**

Run: `cat /Users/vadim/polymarket-ai/frontend/src/components/layout/MobileNav.tsx`

- [ ] **Step 2: Rewrite MobileNav**

Visual spec per design doc section 3.2:
- Fixed bottom: `fixed bottom-0 inset-x-0 h-[72px] glass z-40`
- 5 items: Dashboard, Opportunités, Performance, Agents, Plus (menu)
- Each item: column `flex flex-col items-center justify-center gap-1 flex-1`
- Icon 20px + label `text-[10px] uppercase tracking-wider font-semibold`
- Active state: icon+label in `text-accent` with a small 4px `bg-accent rounded-full` dot underneath
- Inactive: `text-txt-muted`
- Safe-area padding: `pb-[env(safe-area-inset-bottom)]`
- "Plus" item opens a drawer. For the drawer: use framer-motion's `AnimatePresence` + `motion.div` with slide-up from bottom, overlay dark on click outside. Contents: list of remaining routes (Marchés, Portfolio, Track Record, Briefs, Workspace, Learn, Paramètres, Abonnement). Each as big touch-friendly row with icon + label.

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/layout/MobileNav.tsx
git commit -m "feat(frontend): redesign MobileNav with glass bottom bar + drawer"
```

---

### Task 12: Refine AppLayout + PageHeader

**Files:**
- Modify: `src/components/layout/AppLayout.tsx`
- Modify: `src/components/layout/PageHeader.tsx`

- [ ] **Step 1: Read existing files**

Run:
```
cat /Users/vadim/polymarket-ai/frontend/src/components/layout/AppLayout.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/layout/PageHeader.tsx
```

- [ ] **Step 2: Rewrite AppLayout**

Structure:
- Root: `min-h-screen flex bg-surface-0 text-txt-primary`
- Desktop sidebar: rendered when `!isMobile`, width 260px
- Main content area: `flex-1 min-w-0`
  - Inner wrapper: `max-w-[1120px] mx-auto px-6 md:px-8 py-7 pb-24 md:pb-10`
  - Uses `Outlet` from react-router-dom
  - Wrap outlet with AnimatePresence + motion.div for page transitions: `initial={{ opacity: 0, y: 8 }}` `animate={{ opacity: 1, y: 0 }}` `exit={{ opacity: 0, y: -8 }}` `transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}`
  - Key the motion.div on `location.pathname` (from `useLocation`)
- Mobile nav: rendered when `isMobile`

- [ ] **Step 3: Rewrite PageHeader**

Props: `title` (string), `subtitle?` (string), `actions?` (ReactNode), `className?`.

Structure:
- Container: `flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-6 pb-5 border-b border-edge-subtle`
- Left: title `h1` in `font-display font-bold text-[28px] text-txt-primary leading-tight tracking-tight` + subtitle `p` in `text-txt-secondary text-[15px] mt-1.5`
- Right: actions container `flex items-center gap-2`

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/layout/AppLayout.tsx src/components/layout/PageHeader.tsx
git commit -m "feat(frontend): polish AppLayout transitions + PageHeader"
```

---

## PHASE 4 — Signal Components

### Task 13: Redesign SignalCard (core component)

**Files:**
- Modify: `src/components/signals/SignalCard.tsx`

- [ ] **Step 1: Read existing file**

Run: `cat /Users/vadim/polymarket-ai/frontend/src/components/signals/SignalCard.tsx`

- [ ] **Step 2: Rewrite SignalCard**

Preserve the existing props signature (the component is heavily used). Visual spec per design doc section 4.2 (SignalCard):

Structure:
- Wrapper: `Card` with `padding="none"`, `hover={true}`, custom className
- Category color 3px left border: implemented as `before:` pseudo via inline style OR an absolute div (`absolute left-0 top-4 bottom-4 w-[3px] rounded-r-full` with bg = bucket color)
- Inner padding: `pl-5 pr-5 py-4 md:pl-6 md:pr-6 md:py-5`
- **Row 1** (meta): `flex items-center gap-2 mb-3 text-xs`
  - `CategoryBadge` (size sm)
  - timestamp in `text-txt-muted` (use existing `timeAgo()` util)
  - spacer
  - `DirectionBadge`
- **Row 2** (event title): `h3` in `font-display font-semibold text-[16px] text-txt-primary leading-snug line-clamp-2 mb-1.5`
- **Row 3** (market question): `p` in `text-[13px] text-txt-secondary line-clamp-1 mb-4`
- **Row 4** (score bar): `ScoreBar` with smooth fill
- **Row 5** (footer): `flex items-center justify-between mt-4 pt-3 border-t border-edge-subtle`
  - Left cluster (metrics): YES % (mono), confidence, urgency — small stat chips in `flex items-center gap-3 text-xs`
  - Right cluster: Polymarket link (external icon) + "Trader" button (size sm, variant primary)
- Hover state: handled by `card-hover` class (border gold + lift)
- New-signal flash: if prop `isNew` (or existing equivalent) is true, apply `animate-flash-gold` on mount

Use `motion.article` from framer-motion as the root for `layout` animation support (used by parent feed when new items arrive).

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds. TypeScript should remain green — props API preserved.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/signals/SignalCard.tsx
git commit -m "feat(frontend): redesign SignalCard with premium structure"
```

---

### Task 14: Redesign SignalFilters + LiveIndicator

**Files:**
- Modify: `src/components/signals/SignalFilters.tsx`
- Modify: `src/components/signals/LiveIndicator.tsx`

- [ ] **Step 1: Read existing files**

Run:
```
cat /Users/vadim/polymarket-ai/frontend/src/components/signals/SignalFilters.tsx
cat /Users/vadim/polymarket-ai/frontend/src/components/signals/LiveIndicator.tsx
```

- [ ] **Step 2: Rewrite SignalFilters**

Keep the existing props/state management intact (filter change callbacks). Visual spec:
- Container: `Card padding="sm"` with `flex flex-wrap items-center gap-3`
- **Bucket filter**: a pill group of buttons (one per category). Active = `bg-accent/15 text-accent border-accent/30`. Inactive = `bg-transparent text-txt-secondary border-transparent hover:bg-surface-raised`. Each pill: `px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors duration-150`. Include an "All" pill.
- **Min score filter**: 4 pills — `Tous`, `60+`, `70+`, `80+`. Same pill style.
- **Direction filter**: 3-state toggle — `Tous`, `BUY YES` (success tint when active), `BUY NO` (danger tint when active).
- **Reset button** (far right): ghost button, only shown if at least one filter is non-default.

- [ ] **Step 3: Rewrite LiveIndicator**

Props: `connected` (boolean), `className?`.
Structure:
- Inline-flex badge, rounded-full, `bg-success/15 border border-success/30` when connected, `bg-danger/15 border border-danger/30` when not
- 6px animated dot (`animate-pulse-live`) + "LIVE" text in `text-[10px] uppercase tracking-wider font-bold`

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/components/signals/SignalFilters.tsx src/components/signals/LiveIndicator.tsx
git commit -m "feat(frontend): redesign SignalFilters pill group + LiveIndicator"
```

---

## MILESTONE 1 — Verify foundation + components

- [ ] **Run dev server and manually inspect pages**

```bash
cd /Users/vadim/polymarket-ai/frontend && npm run dev
```

Visit http://localhost:3001/ and at least `/dashboard` (if logged in). Verify:
- No console errors
- Fonts load (Satoshi visible on headings)
- Colors look premium
- Existing pages still render (they still use old layouts — that's expected, Phases 5-6 rebuild them)

Stop the dev server when done.

---

## PHASE 5 — Landing Page (complete rebuild)

The landing page is split into independent sections under `src/pages/Landing/`. Current `src/pages/Landing.tsx` becomes the section composer.

### Task 15: Create Landing directory + Navbar + Hero

**Files:**
- Create: `src/pages/Landing/index.tsx` (main page)
- Create: `src/pages/Landing/Navbar.tsx`
- Create: `src/pages/Landing/Hero.tsx`
- Modify: `src/pages/Landing.tsx` (re-export from new Landing/index)

- [ ] **Step 1: Create `src/pages/Landing/Navbar.tsx`**

```tsx
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { cn } from "../../lib/utils"

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <header
      className={cn(
        "fixed top-0 inset-x-0 z-50 transition-all duration-300",
        scrolled ? "glass border-b border-edge-subtle" : "bg-transparent",
      )}
    >
      <nav className="max-w-[1280px] mx-auto px-6 md:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="font-display font-bold text-[20px] tracking-tight">Foresight</span>
        </Link>
        <div className="hidden md:flex items-center gap-8 text-sm text-txt-secondary">
          <a href="#features" className="hover:text-txt-primary transition-colors">Fonctionnalités</a>
          <a href="#performance" className="hover:text-txt-primary transition-colors">Performance</a>
          <a href="#pricing" className="hover:text-txt-primary transition-colors">Pricing</a>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/auth" className="btn-ghost hidden sm:inline-flex">Se connecter</Link>
          <Link to="/auth" className="btn-primary">Commencer gratuitement</Link>
        </div>
      </nav>
    </header>
  )
}
```

- [ ] **Step 2: Create `src/pages/Landing/Hero.tsx`**

```tsx
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { useTrackRecord } from "../../hooks/useTrackRecord"

export function Hero() {
  const { data } = useTrackRecord()
  const accuracy = data?.overall_accuracy ? Math.round(data.overall_accuracy * 100) : null
  const total = data?.total_signals ?? null
  const resolved = data?.total_resolved ?? null

  return (
    <section className="relative pt-32 pb-24 md:pt-40 md:pb-32 overflow-hidden">
      <div className="hero-radial absolute inset-0 pointer-events-none" />
      <div className="relative max-w-[1280px] mx-auto px-6 md:px-8">
        <div className="max-w-[820px] mx-auto text-center">
          <h1 className="font-display font-extrabold text-[42px] md:text-[64px] leading-[1.05] tracking-tight text-balance">
            <span className="text-gradient-gold-teal">L'intelligence qui manquait</span>
            <br />
            <span className="text-txt-primary">aux marchés de prédiction</span>
          </h1>
          <p className="mt-6 text-[17px] md:text-[19px] text-txt-secondary leading-relaxed max-w-[580px] mx-auto">
            Foresight analyse les événements mondiaux en temps réel et génère des signaux de trading actionnables sur Polymarket. Propulsé par 6 agents IA.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/auth" className="btn-primary px-7 py-3.5 text-base rounded-[14px]">
              Commencer gratuitement
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/track-record" className="btn-outline px-7 py-3.5 text-base rounded-[14px]">
              Voir le track record
            </Link>
          </div>
          {(total !== null || accuracy !== null) && (
            <div className="mt-10 flex items-center justify-center gap-6 text-sm text-txt-muted">
              {total !== null && <span><span className="font-mono text-txt-secondary font-semibold">{total}</span> signaux générés</span>}
              {accuracy !== null && <><span className="text-txt-muted">·</span><span><span className="font-mono text-txt-secondary font-semibold">{accuracy}%</span> de précision</span></>}
              {resolved !== null && <><span className="text-txt-muted">·</span><span><span className="font-mono text-txt-secondary font-semibold">{resolved}</span> résolus</span></>}
            </div>
          )}
        </div>

        {/* Dashboard preview mockup */}
        <div className="mt-16 md:mt-20 relative max-w-[1040px] mx-auto">
          <div className="absolute inset-0 -top-8 bg-gradient-hero-radial blur-2xl" aria-hidden />
          <div className="relative card overflow-hidden border-edge-accent shadow-glow-lg">
            <div className="aspect-[16/10] bg-surface-card">
              {/* Placeholder preview — will be replaced with a real screenshot later */}
              <div className="h-full w-full grid grid-cols-[220px_1fr]">
                <div className="bg-surface-0 border-r border-edge-subtle p-4">
                  <div className="h-6 w-24 rounded bg-surface-raised mb-6" />
                  <div className="space-y-2">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <div key={i} className="h-8 rounded-xl bg-surface-raised/50" />
                    ))}
                  </div>
                </div>
                <div className="p-6">
                  <div className="grid grid-cols-4 gap-3 mb-6">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-20 rounded-xl bg-surface-raised" />
                    ))}
                  </div>
                  <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="h-20 rounded-xl bg-surface-raised" />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Create `src/pages/Landing/index.tsx`**

```tsx
import { Navbar } from "./Navbar"
import { Hero } from "./Hero"

export default function Landing() {
  return (
    <div className="min-h-screen bg-surface-0 text-txt-primary">
      <Navbar />
      <main>
        <Hero />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Replace `src/pages/Landing.tsx` with re-export shim**

```tsx
export { default } from "./Landing/index"
```

- [ ] **Step 5: Build + run dev**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Landing.tsx src/pages/Landing/
git commit -m "feat(landing): premium Navbar + Hero with live track record stats"
```

---

### Task 16: TrustedBy + HowItWorks sections

**Files:**
- Create: `src/pages/Landing/TrustedBy.tsx`
- Create: `src/pages/Landing/HowItWorks.tsx`
- Modify: `src/pages/Landing/index.tsx` (compose new sections)

- [ ] **Step 1: Create `src/pages/Landing/TrustedBy.tsx`**

```tsx
const BADGES = [
  "Polymarket",
  "Powered by GPT-4",
  "Reuters",
  "Bloomberg",
  "Associated Press",
  "Financial Times",
  "CoinDesk",
  "Telegraph",
]

export function TrustedBy() {
  return (
    <section className="py-16 md:py-20 overflow-hidden border-y border-edge-subtle/60">
      <div className="max-w-[1280px] mx-auto px-6 md:px-8">
        <p className="text-center text-[11px] uppercase tracking-[0.2em] text-txt-muted font-semibold mb-8">
          Powered by et sources d'intelligence
        </p>
      </div>
      <div className="relative w-full overflow-hidden">
        <div className="flex gap-12 animate-scroll-x will-change-transform" style={{ width: "max-content" }}>
          {[...BADGES, ...BADGES].map((badge, i) => (
            <div
              key={`${badge}-${i}`}
              className="flex-shrink-0 font-display font-semibold text-[20px] text-txt-muted opacity-60 whitespace-nowrap"
            >
              {badge}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Create `src/pages/Landing/HowItWorks.tsx`**

```tsx
import { motion } from "framer-motion"
import { Radar, Brain, Zap } from "lucide-react"

const STEPS = [
  {
    icon: Radar,
    title: "Nos agents scannent",
    description: "6 agents IA surveillent les sources d'information mondiales 24/7.",
    color: "#E8A843",
  },
  {
    icon: Brain,
    title: "L'analyse génère un signal",
    description: "Score de conviction, direction, timing — tout est calculé en temps réel.",
    color: "#0EC6D6",
  },
  {
    icon: Zap,
    title: "Tu trades en un clic",
    description: "Signal actionnable directement sur Polymarket avec ton edge calculé.",
    color: "#34D399",
  },
]

export function HowItWorks() {
  return (
    <section className="py-24 md:py-32">
      <div className="max-w-[1280px] mx-auto px-6 md:px-8">
        <div className="text-center max-w-[640px] mx-auto mb-16">
          <h2 className="font-display font-bold text-[36px] md:text-[44px] leading-tight tracking-tight text-balance">
            De l'événement au signal<br />en quelques secondes
          </h2>
          <p className="mt-4 text-[17px] text-txt-secondary">
            Trois étapes automatisées, une seule interface.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {STEPS.map((step, i) => {
            const Icon = step.icon
            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
                className="card p-6 md:p-8 relative overflow-hidden"
              >
                <div
                  className="absolute -top-16 -right-16 w-40 h-40 rounded-full opacity-10 blur-3xl"
                  style={{ background: step.color }}
                  aria-hidden
                />
                <div className="relative">
                  <div className="flex items-center gap-3 mb-5">
                    <span
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: `${step.color}20`, color: step.color }}
                    >
                      <Icon className="w-5 h-5" />
                    </span>
                    <span className="font-mono text-sm text-txt-muted">0{i + 1}</span>
                  </div>
                  <h3 className="font-display font-bold text-[22px] text-txt-primary mb-2">{step.title}</h3>
                  <p className="text-[15px] text-txt-secondary leading-relaxed">{step.description}</p>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Update `Landing/index.tsx` to include both sections**

```tsx
import { Navbar } from "./Navbar"
import { Hero } from "./Hero"
import { TrustedBy } from "./TrustedBy"
import { HowItWorks } from "./HowItWorks"

export default function Landing() {
  return (
    <div className="min-h-screen bg-surface-0 text-txt-primary">
      <Navbar />
      <main>
        <Hero />
        <TrustedBy />
        <HowItWorks />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Landing/
git commit -m "feat(landing): TrustedBy scroller + HowItWorks three-step section"
```

---

### Task 17: Bento Features grid

**Files:**
- Create: `src/pages/Landing/Features.tsx`
- Modify: `src/pages/Landing/index.tsx`

- [ ] **Step 1: Create `src/pages/Landing/Features.tsx`**

Implement the bento grid per design doc section 2.5. Use an asymmetric CSS grid: `grid-cols-1 md:grid-cols-3 auto-rows-[minmax(220px,auto)] gap-4 md:gap-5`.

Features to render (use `lucide-react` icons + preview components):
1. **Signaux temps réel** (md:col-span-2) — feature title, description, SignalCard preview (static dummy data), live dot indicator
2. **6 Agents IA** (md:col-span-1) — pipeline visual: 6 small circles connected by lines
3. **Analytics avancés** (md:col-span-1) — mini area chart (inline SVG polyline)
4. **Track record vérifiable** (md:col-span-2) — big percentage stat pulled from `useTrackRecord`, mini sparkline
5. **Alertes Telegram** (md:col-span-1) — icon + description
6. **Trading intégré** (md:col-span-1) — icon + description + "Polymarket" pill

Each bento card:
- Use `Card` with `padding="lg"`, `hover={true}`
- `motion.div` scroll-reveal wrapper: `initial={{ opacity: 0, y: 20 }}` `whileInView={{ opacity: 1, y: 0 }}` `viewport={{ once: true, amount: 0.3 }}` `transition={{ duration: 0.4, delay: index * 0.06 }}`
- Title in `font-display font-bold text-[22px]`
- Description in `text-txt-secondary text-[15px] leading-relaxed`
- Distinctive accent color per card (gold for primary features, teal for data features, success for outcomes)

Section header:
- Title "Tout ce qu'il faut pour avoir un edge" + subtitle "Une stack complète, conçue pour l'action rapide."
- Section id `features` for navbar anchor

- [ ] **Step 2: Compose into `Landing/index.tsx`** (add `<Features />` after `<HowItWorks />`)

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Landing/
git commit -m "feat(landing): bento features grid with asymmetric layout"
```

---

### Task 18: Performance section (live data)

**Files:**
- Create: `src/pages/Landing/Performance.tsx`
- Modify: `src/pages/Landing/index.tsx`

- [ ] **Step 1: Create `src/pages/Landing/Performance.tsx`**

This section uses `useTrackRecord()` (already exists in hooks). It renders:
- Section id `performance`
- Heading: "Des résultats, pas des promesses" + subtitle "Chaque signal est vérifié et publié — rien n'est caché."
- Three large counters in a 3-col grid (mobile: stacked):
  - Win rate (animate from 0 to `overall_accuracy * 100` using framer-motion `useSpring` + `useMotionValue`, display with 1 decimal + `%` suffix)
  - Signaux résolus (`total_resolved`, integer)
  - Total généré (`total_signals`, integer)
  - Each counter: `font-display font-extrabold text-[56px] md:text-[72px] text-gradient-gold-teal font-tabular`
  - Label below in `text-txt-secondary uppercase text-[11px] tracking-[0.2em] font-semibold mt-2`
- Below counters: recent resolved signals table (max 6 rows) from `data.recent_resolved` — columns: Date, Catégorie, Question (truncated), Résultat (green/red pill). Use existing `DirectionBadge` or a custom green/red pill for "Correct"/"Incorrect".
- CTA at bottom: `<Link to="/track-record" className="btn-outline">Voir le track record complet <ArrowRight /></Link>`

Handle loading state with `Skeleton` components. Handle empty/error state with a graceful message.

- [ ] **Step 2: Compose into `Landing/index.tsx`** (add `<Performance />` after `<Features />`)

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Landing/
git commit -m "feat(landing): performance section with live track record counters"
```

---

### Task 19: Pricing + FinalCTA + Footer

**Files:**
- Create: `src/pages/Landing/Pricing.tsx`
- Create: `src/pages/Landing/FinalCTA.tsx`
- Create: `src/pages/Landing/Footer.tsx`
- Modify: `src/pages/Landing/index.tsx`

- [ ] **Step 1: Create `src/pages/Landing/Pricing.tsx`**

Define plans as a module-level array so they're easy to edit:

```tsx
import { Check } from "lucide-react"
import { Link } from "react-router-dom"
import { cn } from "../../lib/utils"

type Plan = {
  id: "free" | "pro" | "trader"
  name: string
  price: string
  period: string
  description: string
  features: string[]
  cta: string
  highlight?: boolean
}

const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: "0€",
    period: "pour toujours",
    description: "Découvre Foresight sans engagement.",
    features: [
      "5 signaux par jour",
      "Catégories de base",
      "Track record public",
      "Support communautaire",
    ],
    cta: "Commencer",
  },
  {
    id: "pro",
    name: "Pro",
    price: "29€",
    period: "par mois",
    description: "Pour investisseurs actifs.",
    features: [
      "Signaux illimités",
      "Toutes les catégories",
      "Alertes Telegram & push",
      "Briefs quotidiens",
      "Historique complet",
      "Support prioritaire",
    ],
    cta: "Essayer Pro",
    highlight: true,
  },
  {
    id: "trader",
    name: "Trader",
    price: "99€",
    period: "par mois",
    description: "Pour traders pro et fonds.",
    features: [
      "Tout de Pro",
      "Accès API B2B",
      "Execution automatique",
      "Risk alerts avancées",
      "Analyses LLM détaillées",
      "Support dédié",
    ],
    cta: "Passer Trader",
  },
]

export function Pricing() {
  return (
    <section id="pricing" className="py-24 md:py-32">
      <div className="max-w-[1280px] mx-auto px-6 md:px-8">
        <div className="text-center max-w-[640px] mx-auto mb-14">
          <h2 className="font-display font-bold text-[36px] md:text-[44px] leading-tight tracking-tight text-balance">
            Un plan pour chaque ambition
          </h2>
          <p className="mt-4 text-[17px] text-txt-secondary">
            Annulable à tout moment. Paiement sécurisé par Stripe.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-5 max-w-[1100px] mx-auto">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={cn(
                "card p-7 md:p-8 flex flex-col relative",
                plan.highlight &&
                  "border-accent/40 shadow-glow lg:-translate-y-4",
              )}
            >
              {plan.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 text-[10px] uppercase tracking-wider font-bold bg-accent text-surface-0 rounded-full">
                  Populaire
                </span>
              )}
              <div className="mb-6">
                <h3 className="font-display font-bold text-[22px] text-txt-primary">{plan.name}</h3>
                <p className="text-sm text-txt-secondary mt-1">{plan.description}</p>
              </div>
              <div className="mb-6">
                <span className="font-display font-extrabold text-[44px] text-txt-primary">{plan.price}</span>
                <span className="text-sm text-txt-muted ml-2">{plan.period}</span>
              </div>
              <ul className="space-y-3 mb-7 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-txt-secondary">
                    <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/auth"
                className={cn(
                  "w-full text-center",
                  plan.highlight ? "btn-primary" : "btn-outline",
                )}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Create `src/pages/Landing/FinalCTA.tsx`**

```tsx
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"

export function FinalCTA() {
  return (
    <section className="py-24 md:py-32 relative overflow-hidden">
      <div className="hero-radial absolute inset-0 pointer-events-none" />
      <div className="relative max-w-[720px] mx-auto px-6 md:px-8 text-center">
        <h2 className="font-display font-extrabold text-[36px] md:text-[52px] leading-tight tracking-tight text-balance">
          <span className="text-gradient-gold-teal">Prêt à trader</span>
          <br />
          <span className="text-txt-primary">avec un avantage ?</span>
        </h2>
        <p className="mt-5 text-[17px] text-txt-secondary">
          Rejoins les investisseurs qui utilisent Foresight pour anticiper les marchés.
        </p>
        <Link to="/auth" className="btn-primary mt-9 px-8 py-4 text-base rounded-[16px] inline-flex">
          Créer mon compte gratuitement
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Create `src/pages/Landing/Footer.tsx`**

```tsx
import { Link } from "react-router-dom"

export function Footer() {
  return (
    <footer className="border-t border-edge-subtle py-14">
      <div className="max-w-[1280px] mx-auto px-6 md:px-8 grid md:grid-cols-4 gap-10">
        <div>
          <span className="font-display font-bold text-[20px] tracking-tight">Foresight</span>
          <p className="text-sm text-txt-muted mt-3 leading-relaxed">
            L'intelligence qui manquait aux marchés de prédiction.
          </p>
        </div>
        <FooterCol title="Produit" links={[
          ["Fonctionnalités", "#features"],
          ["Performance", "#performance"],
          ["Pricing", "#pricing"],
        ]} />
        <FooterCol title="Ressources" links={[
          ["Track record", "/track-record"],
          ["Learn", "/learn"],
          ["API B2B", "/pricing"],
        ]} />
        <FooterCol title="Légal" links={[
          ["Conditions d'utilisation", "#"],
          ["Confidentialité", "#"],
          ["Contact", "mailto:hello@getforesight.io"],
        ]} />
      </div>
      <div className="max-w-[1280px] mx-auto px-6 md:px-8 mt-12 pt-6 border-t border-edge-subtle flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-txt-muted">
        <span>© 2026 Foresight. Tous droits réservés.</span>
        <span>Fait en France.</span>
      </div>
    </footer>
  )
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <h4 className="font-semibold text-sm text-txt-primary mb-4">{title}</h4>
      <ul className="space-y-2.5">
        {links.map(([label, href]) => (
          <li key={label}>
            {href.startsWith("/") ? (
              <Link to={href} className="text-sm text-txt-secondary hover:text-txt-primary transition-colors">{label}</Link>
            ) : (
              <a href={href} className="text-sm text-txt-secondary hover:text-txt-primary transition-colors">{label}</a>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Compose all sections into `Landing/index.tsx`**

```tsx
import { Navbar } from "./Navbar"
import { Hero } from "./Hero"
import { TrustedBy } from "./TrustedBy"
import { HowItWorks } from "./HowItWorks"
import { Features } from "./Features"
import { Performance } from "./Performance"
import { Pricing } from "./Pricing"
import { FinalCTA } from "./FinalCTA"
import { Footer } from "./Footer"

export default function Landing() {
  return (
    <div className="min-h-screen bg-surface-0 text-txt-primary">
      <Navbar />
      <main>
        <Hero />
        <TrustedBy />
        <HowItWorks />
        <Features />
        <Performance />
        <Pricing />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 5: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Landing/
git commit -m "feat(landing): pricing + final CTA + footer sections"
```

---

## MILESTONE 2 — Full landing review

- [ ] **Run dev server and inspect the landing page end-to-end**

```bash
cd /Users/vadim/polymarket-ai/frontend && npm run dev
```

Visit http://localhost:3001/. Scroll through the entire landing:
- Navbar transitions on scroll
- Hero has live track record numbers (or loads gracefully if backend unavailable)
- TrustedBy scrolls smoothly
- HowItWorks cards reveal on scroll
- Features bento grid is asymmetric and readable
- Performance counters animate
- Pricing cards show Pro highlighted
- FinalCTA radial background visible
- Footer links work

Verify responsive: resize viewport down to 375px. Every section should reflow.

---

## Phase 6: App Pages Redesign

Every app page lives inside `<AppLayout>`. The layout (sidebar + mobile nav + top PageHeader) is built in Phase 3. Each page owns a `<PageHeader>` slot (title, description, actions) and a body. Keep existing React Query hooks and types. Only change presentation.

Shared rule for every page task:
- If the page currently imports from `../components/ui/*`, `../components/signals/*`, or layout components, re-use the redesigned versions from Phases 2–4.
- Loading states use `<Skeleton>` blocks. Empty states use `<EmptyState>`. Error states show a `<Card variant="inset">` with icon + message + retry button.
- Never touch `hooks/use*.ts` or `services/api.ts` (except to add read-only typed selectors if needed).

### Task 20: Dashboard page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Dashboard.tsx` (full rewrite, keep hook usage)

**Goal:** Bento dashboard with hero stat band + top signals + performance sparkline + activity feed.

- [ ] **Step 1: Inventory current hooks used**

```bash
cd /Users/vadim/polymarket-ai/frontend && grep -nE "use[A-Z]" src/pages/Dashboard.tsx
```

Note every hook (e.g. `useSignals`, `usePerformance`, `useTrackRecord`). These MUST be preserved.

- [ ] **Step 2: Rewrite Dashboard.tsx**

Structure:
```tsx
<AppLayout>
  <PageHeader
    title="Tableau de bord"
    description="Vue d'ensemble de tes signaux, performance et marché Polymarket."
    actions={<Button variant="secondary" icon={<RefreshCw />}>Actualiser</Button>}
  />

  {/* Hero stat band — 4 StatCard in grid */}
  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
    <StatCard label="Signaux actifs" value={activeSignals} trend="up" delta="+3" />
    <StatCard label="Win rate 30j" value={`${winRate}%`} trend={winRateTrend} />
    <StatCard label="ROI cumulé" value={`+${roi}%`} accent="gold" />
    <StatCard label="Drawdown max" value={`-${dd}%`} accent="danger" />
  </div>

  {/* Bento grid */}
  <div className="grid grid-cols-12 gap-6">
    <Card className="col-span-12 xl:col-span-8">
      {/* Performance sparkline chart (Recharts AreaChart) */}
    </Card>
    <Card className="col-span-12 xl:col-span-4">
      {/* Top 3 signaux en direct (mini SignalCard list) */}
    </Card>
    <Card className="col-span-12 lg:col-span-6">
      {/* Répartition catégories (donut) */}
    </Card>
    <Card className="col-span-12 lg:col-span-6">
      {/* Activity feed (last 8 events) */}
    </Card>
  </div>
</AppLayout>
```

Use `framer-motion` `staggerChildren` on the bento grid so cards fade+rise in sequence.

Handle all loading/empty/error states explicitly. No raw text on black surfaces without a `Card` container.

- [ ] **Step 3: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 4: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Dashboard.tsx
git commit -m "feat(dashboard): bento redesign with stat band + live signals"
```

---

### Task 21: Opportunities page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Opportunities.tsx`

**Goal:** Filterable signal stream powered by `<SignalFilters>` + `<SignalCard>` grid with `<LiveIndicator>` pill.

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title="Opportunités"
    description="Signaux en direct détectés par nos agents."
    actions={<LiveIndicator connected={wsConnected} />}
  />

  <SignalFilters
    value={filters}
    onChange={setFilters}
    categories={categories}
    className="mb-6"
  />

  {loading && (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-64" />)}
    </div>
  )}

  {!loading && signals.length === 0 && (
    <EmptyState
      icon={<Target />}
      title="Aucun signal pour ces filtres"
      description="Essaie d'élargir la confiance minimale ou de changer de catégorie."
    />
  )}

  <motion.div
    layout
    className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
  >
    <AnimatePresence mode="popLayout">
      {signals.map(s => (
        <SignalCard key={s.id} signal={s} onClick={() => navigate(`/opportunities/${s.id}`)} />
      ))}
    </AnimatePresence>
  </motion.div>
</AppLayout>
```

New signals arriving via WS should animate in with `initial={{ opacity: 0, y: -12 }}`. Removed signals animate out.

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Opportunities.tsx
git commit -m "feat(opportunities): filterable live signal grid"
```

---

### Task 22: OpportunityDetail page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/OpportunityDetail.tsx`

**Goal:** Deep dive on a single signal — 3-column layout: left (market context), center (thesis + evidence), right (trade card).

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title={signal.title}
    description={<Breadcrumbs segments={[{ label: "Opportunités", href: "/opportunities" }, { label: signal.id }]} />}
    actions={
      <>
        <Button variant="ghost" icon={<ExternalLink />}>Polymarket</Button>
        <Button variant="primary" icon={<Bookmark />}>Suivre</Button>
      </>
    }
  />

  <div className="grid grid-cols-12 gap-6">
    {/* Left column — market context */}
    <div className="col-span-12 lg:col-span-3 space-y-4">
      <Card>
        <h3>Marché</h3>
        <MarketMiniChart data={probabilityHistory} />
        <dl>
          <dt>Volume 24h</dt><dd>{volume24h}</dd>
          <dt>Liquidité</dt><dd>{liquidity}</dd>
          <dt>Fin du marché</dt><dd>{endDate}</dd>
        </dl>
      </Card>
      <Card>
        <h3>Catégorie</h3>
        <CategoryBadge category={signal.category} size="lg" />
      </Card>
    </div>

    {/* Center column — thesis */}
    <div className="col-span-12 lg:col-span-6 space-y-6">
      <Card>
        <h2>Thèse</h2>
        <p>{signal.thesis}</p>
        <ScoreBar label="Confiance agents" value={signal.confidence} />
        <ScoreBar label="Edge détecté" value={signal.edge} accent="gold" />
      </Card>
      <Card>
        <h2>Preuves</h2>
        <EvidenceList items={signal.evidence} />
      </Card>
      <Card>
        <h2>Risques identifiés</h2>
        <RiskList items={signal.risks} />
      </Card>
    </div>

    {/* Right column — trade card */}
    <div className="col-span-12 lg:col-span-3">
      <Card variant="inset" className="sticky top-24">
        <h3>Signal</h3>
        <DirectionBadge direction={signal.direction} size="lg" />
        <div className="mt-4">
          <Label>Prix d'entrée</Label>
          <NumericValue>{signal.entryPrice}</NumericValue>
        </div>
        <div>
          <Label>Cible</Label>
          <NumericValue>{signal.target}</NumericValue>
        </div>
        <div>
          <Label>Stop suggéré</Label>
          <NumericValue>{signal.stop}</NumericValue>
        </div>
        <Button variant="primary" fullWidth>Ouvrir sur Polymarket</Button>
      </Card>
    </div>
  </div>
</AppLayout>
```

If `EvidenceList`/`RiskList`/`MarketMiniChart`/`Breadcrumbs` don't exist, create them inline at the top of this file — simple presentational components, ~20 lines each, no new data fetching.

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/OpportunityDetail.tsx
git commit -m "feat(signal): premium 3-column signal detail view"
```

---

### Task 23: Performance page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Performance.tsx`

**Goal:** Analytics dashboard — equity curve, stats grid, distribution chart, signals table.

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title="Performance"
    description="Track record complet et transparent des signaux Foresight."
    actions={
      <SegmentedControl
        options={[{ label: "7j", value: "7d" }, { label: "30j", value: "30d" }, { label: "90j", value: "90d" }, { label: "Tout", value: "all" }]}
        value={period}
        onChange={setPeriod}
      />
    }
  />

  {/* Stat band */}
  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
    <MetricCard label="Win rate" value={`${winRate}%`} />
    <MetricCard label="ROI" value={`+${roi}%`} accent="gold" />
    <MetricCard label="Sharpe" value={sharpe.toFixed(2)} />
    <MetricCard label="Max drawdown" value={`-${dd}%`} accent="danger" />
  </div>

  {/* Equity curve */}
  <Card className="mb-6">
    <h3>Courbe d'équité</h3>
    <EquityChart data={equitySeries} />
  </Card>

  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
    <Card>
      <h3>Distribution des gains</h3>
      <HistogramChart data={returnsDistribution} />
    </Card>
    <Card>
      <h3>Par catégorie</h3>
      <CategoryBreakdown data={categoryStats} />
    </Card>
  </div>

  <Card>
    <h3>Signaux clôturés</h3>
    <DataTable
      columns={closedSignalColumns}
      data={closedSignals}
      onRowClick={(row) => navigate(`/opportunities/${row.id}`)}
    />
  </Card>
</AppLayout>
```

`SegmentedControl`, `EquityChart`, `HistogramChart`, `CategoryBreakdown` are new thin presentational components in this file (or `components/charts/*` if you prefer). Use Recharts with design tokens (`hsl(var(--accent-gold))`, etc.).

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Performance.tsx src/components/charts/
git commit -m "feat(performance): analytics dashboard with equity curve + distribution"
```

---

### Task 24: Portfolio page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Portfolio.tsx`

**Goal:** Personal portfolio — positions table, exposure ring, P&L header.

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title="Mon portefeuille"
    description="Tes positions Polymarket suivies par Foresight."
    actions={<Button variant="secondary" icon={<Plus />}>Ajouter une position</Button>}
  />

  {/* P&L header band */}
  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
    <MetricCard label="Valeur totale" value={formatUSD(totalValue)} mono />
    <MetricCard label="P&L non réalisé" value={formatUSD(unrealizedPnl)} accent={unrealizedPnl >= 0 ? "success" : "danger"} />
    <MetricCard label="P&L réalisé 30j" value={formatUSD(realizedPnl30)} accent="gold" />
  </div>

  <div className="grid grid-cols-12 gap-6">
    <Card className="col-span-12 lg:col-span-4">
      <h3>Répartition</h3>
      <ExposureRing data={exposureByCategory} />
    </Card>
    <Card className="col-span-12 lg:col-span-8">
      <h3>Positions ouvertes</h3>
      <DataTable
        columns={positionColumns}
        data={positions}
        onRowClick={(row) => navigate(`/opportunities/${row.signalId}`)}
      />
    </Card>
  </div>
</AppLayout>
```

Empty state if no positions: `<EmptyState icon={<Wallet />} title="Aucune position suivie" cta={<Button>Connecter mon wallet</Button>} />`.

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Portfolio.tsx
git commit -m "feat(portfolio): positions + exposure ring redesign"
```

---

### Task 25: Agents page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Agents.tsx`

**Goal:** Gallery of available AI agents — each agent is a card with icon, description, status, stats.

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title="Agents IA"
    description="Les 6 agents spécialisés qui analysent Polymarket 24/7."
  />

  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
    {agents.map(agent => (
      <motion.div
        key={agent.id}
        whileHover={{ y: -4 }}
        transition={{ duration: 0.2 }}
      >
        <Card
          onClick={() => navigate(`/agents/${agent.id}`)}
          className="cursor-pointer h-full"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-accent-gold/10 flex items-center justify-center">
              <AgentIcon agent={agent.id} className="w-6 h-6 text-accent-gold" />
            </div>
            <div>
              <h3 className="font-display text-lg">{agent.name}</h3>
              <AgentStatusBadge status={agent.status} />
            </div>
          </div>
          <p className="text-ink-soft text-sm mb-4">{agent.description}</p>
          <div className="grid grid-cols-3 gap-2 pt-4 border-t border-line-soft">
            <Stat label="Signaux 30j" value={agent.signals30d} />
            <Stat label="Win rate" value={`${agent.winRate}%`} />
            <Stat label="Latence" value={`${agent.avgLatencyMs}ms`} />
          </div>
        </Card>
      </motion.div>
    ))}
  </div>
</AppLayout>
```

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Agents.tsx
git commit -m "feat(agents): premium gallery with live status badges"
```

---

### Task 26: AgentWorkspace page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/AgentWorkspace.tsx`

**Goal:** Single-agent deep dive — live activity log, recent signals, config panel.

- [ ] **Step 1: Rewrite**

```tsx
<AppLayout>
  <PageHeader
    title={agent.name}
    description={<Breadcrumbs segments={[{ label: "Agents", href: "/agents" }, { label: agent.name }]} />}
    actions={
      <>
        <AgentStatusBadge status={agent.status} />
        <Button variant="secondary" icon={<Settings />}>Configurer</Button>
      </>
    }
  />

  <div className="grid grid-cols-12 gap-6">
    <div className="col-span-12 lg:col-span-8 space-y-6">
      <Card>
        <h3>Activité en direct</h3>
        <AgentActivityStream events={agent.recentEvents} />
      </Card>
      <Card>
        <h3>Signaux récents</h3>
        <DataTable columns={signalColumns} data={agent.recentSignals} />
      </Card>
    </div>
    <div className="col-span-12 lg:col-span-4 space-y-6">
      <Card>
        <h3>Statistiques</h3>
        <Stat label="Signaux 30j" value={agent.signals30d} />
        <Stat label="Win rate" value={`${agent.winRate}%`} />
        <Stat label="Edge moyen" value={`${agent.avgEdge}%`} />
        <Stat label="Latence moyenne" value={`${agent.avgLatencyMs}ms`} />
      </Card>
      <Card>
        <h3>Spécialisation</h3>
        <div className="flex flex-wrap gap-2">
          {agent.categories.map(c => <CategoryBadge key={c} category={c} />)}
        </div>
      </Card>
    </div>
  </div>
</AppLayout>
```

`AgentActivityStream` — simple vertical feed with timestamp + event title + optional icon. Auto-scroll to latest when new event arrives via WS.

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/AgentWorkspace.tsx
git commit -m "feat(agent): live workspace with activity stream"
```

---

### Task 27: Markets + Briefs + TrackRecord pages

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Markets.tsx`
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Briefs.tsx`
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/TrackRecord.tsx`

**Goal:** Bulk-redesign three list-style pages with consistent pattern: PageHeader + filters + DataTable/Card grid.

- [ ] **Step 1: Markets.tsx**

```tsx
<AppLayout>
  <PageHeader
    title="Marchés Polymarket"
    description="Tous les marchés suivis par Foresight, triés par volume."
    actions={<SearchInput value={q} onChange={setQ} placeholder="Chercher un marché…" />}
  />

  <div className="flex gap-3 mb-6">
    <CategoryFilter value={category} onChange={setCategory} />
    <SortSelect value={sort} onChange={setSort} options={sortOptions} />
  </div>

  <DataTable
    columns={marketColumns}
    data={markets}
    onRowClick={(row) => window.open(row.polymarketUrl, "_blank")}
  />
</AppLayout>
```

- [ ] **Step 2: Briefs.tsx**

Briefs are long-form editorial content. Use a magazine-style grid:

```tsx
<AppLayout>
  <PageHeader
    title="Briefs"
    description="Analyses longues rédigées chaque semaine par nos agents."
  />

  {/* Featured brief */}
  <Card className="mb-8 col-span-full">
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-12 md:col-span-7">
        <Badge>À la une</Badge>
        <h2 className="font-display text-3xl mt-2">{featured.title}</h2>
        <p className="text-ink-soft mt-3">{featured.excerpt}</p>
        <Button variant="primary" className="mt-6">Lire</Button>
      </div>
      <div className="col-span-12 md:col-span-5">
        <img src={featured.cover} className="rounded-xl aspect-video object-cover" />
      </div>
    </div>
  </Card>

  {/* Grid */}
  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
    {briefs.map(b => (
      <Card key={b.id} onClick={() => navigate(`/briefs/${b.slug}`)} className="cursor-pointer">
        <img src={b.cover} className="rounded-lg aspect-video object-cover mb-4" />
        <CategoryBadge category={b.category} />
        <h3 className="font-display text-xl mt-2">{b.title}</h3>
        <p className="text-ink-soft text-sm mt-2 line-clamp-3">{b.excerpt}</p>
        <div className="flex items-center gap-2 mt-4 text-xs text-ink-muted">
          <Calendar className="w-3 h-3" /> {formatDate(b.publishedAt)}
          <span className="mx-1">·</span>
          <Clock className="w-3 h-3" /> {b.readingTimeMin} min
        </div>
      </Card>
    ))}
  </div>
</AppLayout>
```

- [ ] **Step 3: TrackRecord.tsx**

Public transparency page. Reuses same components as Performance but pre-filtered to all-time + no period selector:

```tsx
<AppLayout>
  <PageHeader
    title="Track record public"
    description="Tous les signaux Foresight depuis le lancement. Aucun filtre, aucune sélection."
    actions={<Button variant="ghost" icon={<Download />}>Exporter CSV</Button>}
  />

  <MetricBand metrics={allTimeMetrics} />

  <Card className="mb-6">
    <h3>Courbe d'équité cumulée</h3>
    <EquityChart data={allTimeEquity} />
  </Card>

  <Card>
    <h3>Tous les signaux</h3>
    <DataTable
      columns={fullSignalColumns}
      data={allSignals}
      pagination
      pageSize={50}
    />
  </Card>
</AppLayout>
```

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Markets.tsx src/pages/Briefs.tsx src/pages/TrackRecord.tsx
git commit -m "feat(pages): markets + briefs + track record redesign"
```

---

### Task 28: Learn + Settings + Pricing (app) pages

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Learn.tsx`
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Settings.tsx`
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Pricing.tsx` (the app-side pricing, if distinct from landing)

**Goal:** Three utility pages — educational library, account settings, in-app upgrade.

- [ ] **Step 1: Learn.tsx**

Grid of educational cards, optional category tabs:

```tsx
<AppLayout>
  <PageHeader
    title="Learn"
    description="Comprendre Polymarket, les marchés prédictifs, et les stratégies Foresight."
  />

  <Tabs value={topic} onChange={setTopic} options={learnTopics} className="mb-6" />

  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
    {articles.map(a => (
      <Card key={a.id} onClick={() => navigate(`/learn/${a.slug}`)} className="cursor-pointer">
        <Badge>{a.level}</Badge>
        <h3 className="font-display text-lg mt-2">{a.title}</h3>
        <p className="text-ink-soft text-sm mt-2 line-clamp-2">{a.excerpt}</p>
        <div className="flex items-center gap-2 mt-4 text-xs text-ink-muted">
          <Clock className="w-3 h-3" /> {a.readingTimeMin} min
        </div>
      </Card>
    ))}
  </div>
</AppLayout>
```

- [ ] **Step 2: Settings.tsx**

Two-column settings: nav rail + active section.

```tsx
<AppLayout>
  <PageHeader title="Paramètres" description="Compte, notifications, abonnement." />

  <div className="grid grid-cols-12 gap-6">
    <nav className="col-span-12 md:col-span-3">
      <ul className="space-y-1">
        {settingsSections.map(s => (
          <li key={s.id}>
            <button
              onClick={() => setSection(s.id)}
              className={cx("w-full text-left px-3 py-2 rounded-lg", section === s.id ? "bg-surface-2 text-ink-strong" : "text-ink-soft hover:bg-surface-2/50")}
            >
              {s.label}
            </button>
          </li>
        ))}
      </ul>
    </nav>

    <div className="col-span-12 md:col-span-9 space-y-6">
      {section === "account" && <AccountSettings />}
      {section === "notifications" && <NotificationSettings />}
      {section === "subscription" && <SubscriptionSettings />}
      {section === "integrations" && <IntegrationsSettings />}
    </div>
  </div>
</AppLayout>
```

Each `*Settings` component is a simple `<Card>` with form fields using the redesigned `<Input>` / `<Toggle>` / `<Button>` primitives. Keep existing mutations.

- [ ] **Step 3: Pricing.tsx (app version)**

If this page exists as a standalone route, render the same `<Pricing />` section from the landing but inside `<AppLayout>` with a tight heading: "Passe à Pro quand tu es prêt.".

- [ ] **Step 4: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Learn.tsx src/pages/Settings.tsx src/pages/Pricing.tsx
git commit -m "feat(pages): learn + settings + pricing redesign"
```

---

### Task 29: Auth page

**Files:**
- Modify: `/Users/vadim/polymarket-ai/frontend/src/pages/Auth.tsx`

**Goal:** Marketing-grade auth screen — split layout: left brand panel (radial gradient + quote + mini track record), right form with Google OAuth + magic link.

- [ ] **Step 1: Rewrite**

```tsx
<div className="min-h-screen grid grid-cols-1 lg:grid-cols-2">
  {/* Left — brand */}
  <div className="relative hidden lg:flex flex-col justify-between p-12 bg-surface-0 overflow-hidden">
    <div className="absolute inset-0 bg-radial-gold opacity-50" />
    <div className="relative">
      <Logo />
    </div>
    <div className="relative">
      <blockquote className="font-display text-2xl text-ink-strong leading-relaxed">
        "Foresight m'a fait découvrir 3 opportunités que j'aurais ratées. Et le track record est public."
      </blockquote>
      <cite className="block mt-4 text-ink-muted text-sm not-italic">— Antoine, utilisateur Pro</cite>

      <div className="mt-12 grid grid-cols-3 gap-6">
        <Stat label="Signaux émis" value={allTimeSignals} />
        <Stat label="Win rate" value={`${allTimeWinRate}%`} />
        <Stat label="ROI cumulé" value={`+${allTimeROI}%`} accent="gold" />
      </div>
    </div>
  </div>

  {/* Right — form */}
  <div className="flex items-center justify-center p-8">
    <div className="w-full max-w-sm">
      <div className="lg:hidden mb-8"><Logo /></div>
      <h1 className="font-display text-3xl">{mode === "signin" ? "Bon retour" : "Créer un compte"}</h1>
      <p className="text-ink-soft mt-2">
        {mode === "signin" ? "Connecte-toi pour accéder à tes signaux." : "14 jours d'essai gratuit. Aucune CB."}
      </p>

      <div className="mt-8 space-y-3">
        <GoogleLoginButton />
        <Divider>ou</Divider>
        <form onSubmit={handleMagicLink} className="space-y-3">
          <Input type="email" placeholder="ton@email.com" value={email} onChange={e => setEmail(e.target.value)} />
          <Button variant="primary" fullWidth type="submit" loading={submitting}>
            {mode === "signin" ? "Recevoir un lien" : "Créer mon compte"}
          </Button>
        </form>
      </div>

      <p className="mt-8 text-sm text-ink-muted text-center">
        {mode === "signin" ? "Pas encore de compte ? " : "Déjà inscrit ? "}
        <button onClick={toggleMode} className="text-accent-gold hover:underline">
          {mode === "signin" ? "S'inscrire" : "Se connecter"}
        </button>
      </p>
    </div>
  </div>
</div>
```

Keep all existing auth hooks (`useGoogleAuth`, magic link mutation). Do not add `<AppLayout>` — auth is public-facing.

- [ ] **Step 2: Build**

Run: `cd /Users/vadim/polymarket-ai/frontend && npm run build`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add src/pages/Auth.tsx
git commit -m "feat(auth): premium split-layout sign-in with live track record"
```

---

## Phase 7: Final Verification

### Task 30: Full build + visual QA pass

**Goal:** Validate the whole app builds and looks right end-to-end.

- [ ] **Step 1: Clean install + production build**

```bash
cd /Users/vadim/polymarket-ai/frontend
rm -rf node_modules dist
npm ci
npm run build
```

Expected: build passes with zero TypeScript errors and zero unused-import warnings.

- [ ] **Step 2: Lint**

```bash
cd /Users/vadim/polymarket-ai/frontend && npm run lint
```

Expected: `--max-warnings 0` passes.

- [ ] **Step 3: Run dev server + visual walkthrough**

```bash
cd /Users/vadim/polymarket-ai/frontend && npm run dev
```

Walk through every route:
- `/` — Landing (all 7 sections scroll cleanly)
- `/auth` — split layout, gradient visible
- `/app` or `/dashboard` — Dashboard bento loads, WS reconnects
- `/opportunities` — filters work, live signals animate in
- `/opportunities/:id` — 3-column detail renders
- `/performance` — period selector swaps charts
- `/portfolio` — exposure ring + positions table
- `/agents` — gallery of 6 agent cards
- `/agents/:id` — workspace with activity stream
- `/markets` — table with search + filters
- `/briefs` — featured + grid
- `/track-record` — public metrics + equity curve
- `/learn` — article grid + tabs
- `/settings` — nav + sections
- `/pricing` — cards with Pro highlighted (if route exists)

For each page: verify no console errors, no layout breaks at 1440px / 1024px / 768px / 375px, no raw hex colors in DOM (should all be tokens).

- [ ] **Step 4: Accessibility sanity**

For 3 key pages (Landing, Opportunities, OpportunityDetail):
- Tab through — every interactive element gets a visible focus ring (gold glow)
- All buttons/links have discernible labels
- No text contrast below 4.5:1 on body text (use the design tokens — they're pre-checked)

- [ ] **Step 5: Performance quick-check**

Run `npm run build` and inspect output. Main bundle should be reasonable (< 400 kB gzipped for the landing chunk). Route-level code splitting must be preserved — `dist/assets/` should contain separate chunks per lazy-loaded route.

- [ ] **Step 6: Final commit**

```bash
cd /Users/vadim/polymarket-ai/frontend
git add -u
git commit -m "chore(frontend): final QA pass on premium redesign" --allow-empty
```

---

## Done

Every route has been redesigned inside the Finary-inspired design system while keeping backend contracts intact. Landing feels like a $10k product; app screens feel like a professional fintech terminal. Tokens are centralized in `tailwind.config.js` + `index.css`, so any future color/spacing tweak flows through the whole app.
