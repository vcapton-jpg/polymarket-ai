/**
 * Three design explorations for SignalCard.
 * Each has a distinct philosophy — see the header comment per variant.
 * All use MOCK_SIGNALS[3] (Fed/Economy, score 92) and the same design tokens.
 */

import { ArrowRight, BookmarkPlus, Check, Clock, ExternalLink, Shield, Timer, TrendingUp, Zap } from "lucide-react"
import type { Signal } from "@/types/signal"
import { cn, timeSinceISO } from "@/lib/utils"
import { formatOpportunityWindow } from "@/lib/formatWindow"
import { DirectionBadge, CategoryPill } from "./badges"

/* ─────────────────────────────────────────────────────────────────────────── */
/* VARIANT A — "The Brief"                                                     */
/* Philosophy: catalyst is the hero. The "why" is what Polymarket can't give  */
/* you alone — so lead with it. Score and direction become support metadata,  */
/* not the headline. Window timer gets amber urgency treatment.                */
/* ─────────────────────────────────────────────────────────────────────────── */

export function SignalCardV1({ signal }: { signal: Signal }) {
  const isYes = signal.direction === "YES"

  return (
    <article className="group relative isolate overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm hover:border-brand-500/30 transition-all duration-300">
      {/* Direction accent bar */}
      <div
        className={cn(
          "absolute left-0 top-0 h-full w-[3px]",
          isYes
            ? "bg-gradient-to-b from-signal-yes via-signal-yes/60 to-transparent"
            : "bg-gradient-to-b from-signal-no via-signal-no/60 to-transparent",
        )}
        aria-hidden
      />

      <div className="px-5 py-5 md:px-6">
        {/* ── Row 1: category + time ── */}
        <div className="mb-4 flex items-center justify-between">
          <CategoryPill label={signal.categoryLabel} />
          <span className="inline-flex items-center gap-1 text-[0.6875rem] text-ink-dim">
            <Clock className="h-3 w-3" aria-hidden />
            {timeSinceISO(signal.createdAt)}
          </span>
        </div>

        {/* ── Row 2: CATALYST — the hero ── */}
        <div className="mb-4 border-l-2 border-brand-500/70 pl-4">
          <p className="mb-1 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-brand-400">
            Ce qu'on a détecté
          </p>
          <p className="text-[1rem] font-medium leading-snug text-ink">
            {signal.catalyst}
          </p>
        </div>

        {/* ── Row 3: question ── */}
        <h3 className="mb-4 font-display text-[1.125rem] font-semibold leading-snug tracking-tight text-ink/80">
          {signal.question}
        </h3>

        {/* ── Row 4: score chip + direction + market% ── */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-brand-400/40 bg-brand-400/10 px-3 py-1.5 font-display text-[1.25rem] font-semibold leading-none text-brand-300">
            {signal.score}
            <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-brand-400/70">
              / 100
            </span>
          </span>
          <DirectionBadge direction={signal.direction} size="md" />
          <span className="inline-flex items-center gap-1 rounded-md border border-line-strong bg-obsidian-800/60 px-2.5 py-1 text-[0.75rem]">
            <span className="text-ink-readable">Marché</span>
            <span className={cn("num font-semibold", isYes ? "text-signal-yes" : "text-signal-no")}>
              {Math.round(signal.marketProbability * 100)}%
            </span>
          </span>
        </div>

        {/* ── Footer: urgency + sources + CTA ── */}
        <div className="flex items-center justify-between gap-3 border-t border-line/60 pt-4">
          <div className="flex items-center gap-3">
            {/* Window — amber when short */}
            <span className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-mono text-[0.6875rem] font-medium",
              signal.windowHours <= 6
                ? "border-signal-amber/40 bg-signal-amber/10 text-signal-amber"
                : "border-line text-ink-dim",
            )}>
              <Timer className="h-3 w-3" aria-hidden />
              {formatOpportunityWindow(signal.windowHours)}
            </span>
            <span className="text-[0.6875rem] text-ink-dim">
              <span className="num font-medium text-ink">{signal.sources.length}</span> sources
            </span>
          </div>
          <button
            type="button"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-4 text-[0.8125rem] font-semibold text-obsidian-900 hover:bg-brand-400 transition-colors shadow-[0_0_0_1px_rgba(11,224,166,0.3),0_6px_20px_-8px_rgba(11,224,166,0.5)]"
          >
            Prendre position
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </article>
  )
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* VARIANT B — "Score Column"                                                  */
/* Philosophy: score is the authority anchor — make it unmissable. Left       */
/* column = score + direction stacked. Right column = all context. Catalyst   */
/* gets its own full-width row below with no box — just styled prose.         */
/* ─────────────────────────────────────────────────────────────────────────── */

export function SignalCardV2({ signal }: { signal: Signal }) {
  const isYes = signal.direction === "YES"
  const scoreColor =
    signal.score >= 85 ? "text-brand-300 border-brand-400/40 bg-brand-400/10"
    : signal.score >= 70 ? "text-brand-400 border-brand-500/30 bg-brand-500/8"
    : "text-signal-amber border-signal-amber/30 bg-signal-amber/8"

  return (
    <article className="group relative isolate overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm hover:border-brand-500/30 transition-all duration-300">
      <div
        className={cn(
          "absolute left-0 top-0 h-full w-[3px]",
          isYes ? "bg-signal-yes/60" : "bg-signal-no/60",
        )}
        aria-hidden
      />
      {/* Ambient top glow */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-500/20 to-transparent"
        aria-hidden
      />

      <div className="px-5 py-5 md:px-6">
        {/* ── Row 1: category + time ── */}
        <div className="mb-4 flex items-center justify-between">
          <CategoryPill label={signal.categoryLabel} />
          <span className="inline-flex items-center gap-1 text-[0.6875rem] text-ink-dim">
            <Clock className="h-3 w-3" aria-hidden />
            {timeSinceISO(signal.createdAt)}
          </span>
        </div>

        {/* ── Row 2: score column + meta column ── */}
        <div className="mb-5 grid grid-cols-[auto_1fr] gap-5 items-start">
          {/* Left — score pillar */}
          <div className={cn(
            "flex flex-col items-center justify-center rounded-xl border px-5 py-3 min-w-[88px]",
            scoreColor,
          )}>
            <span className="num font-display text-[2.5rem] font-semibold leading-none tracking-tight">
              {signal.score}
            </span>
            <span className="mt-0.5 font-mono text-[0.5625rem] uppercase tracking-[0.16em] opacity-70">
              conviction
            </span>
          </div>

          {/* Right — meta stack */}
          <div className="flex flex-col gap-2.5">
            <DirectionBadge direction={signal.direction} size="lg" />
            <div className="flex flex-wrap items-center gap-1.5 text-[0.8125rem]">
              <span className="text-ink-muted">Marché :</span>
              <span className={cn("num font-semibold", isYes ? "text-signal-yes" : "text-signal-no")}>
                {Math.round(signal.marketProbability * 100)}%
              </span>
              <span className="text-ink-dim">·</span>
              <span className={cn(
                "inline-flex items-center gap-1 font-mono text-[0.75rem] font-medium",
                signal.windowHours <= 6 ? "text-signal-amber" : "text-ink-muted",
              )}>
                <Timer className="h-3 w-3" aria-hidden />
                {formatOpportunityWindow(signal.windowHours)}
              </span>
            </div>
            <h3 className="font-display text-[0.9375rem] font-semibold leading-snug tracking-tight text-ink">
              {signal.question}
            </h3>
          </div>
        </div>

        {/* ── Row 3: catalyst prose — no box, accent left line ── */}
        <div className="mb-5 rounded-lg bg-obsidian-800/50 px-4 py-3.5">
          <div className="flex gap-3">
            <Zap className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden />
            <div>
              <p className="mb-0.5 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-brand-400/80">
                Déclencheur détecté
              </p>
              <p className="text-[0.9375rem] leading-relaxed text-ink/90">
                {signal.catalyst}
              </p>
            </div>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-[0.75rem] text-ink-dim">
            <span className="flex items-center gap-1">
              <Shield className="h-3 w-3 text-brand-400" aria-hidden />
              <span className="num font-medium text-ink">{signal.sources.length}</span> sources Tier-1
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-dim hover:text-ink hover:bg-obsidian-700 transition-colors"
              aria-label="Sauvegarder"
            >
              <BookmarkPlus className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-4 text-[0.8125rem] font-semibold text-obsidian-900 hover:bg-brand-400 transition-colors shadow-[0_0_0_1px_rgba(11,224,166,0.3),0_6px_20px_-8px_rgba(11,224,166,0.5)]"
            >
              Prendre position
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* VARIANT C — "Edge"                                                          */
/* Philosophy: maximum information density, minimum chrome. Everything that   */
/* matters fits in 2 rows. No section boxes. Typographic hierarchy only.      */
/* The score becomes a semantic accent color on the question itself.           */
/* Sources become trust logos. Designed for power users who scan fast.        */
/* ─────────────────────────────────────────────────────────────────────────── */

export function SignalCardV3({ signal }: { signal: Signal }) {
  const isYes = signal.direction === "YES"
  const tier1Sources = signal.sources.filter((s) => s.tier === 1)

  return (
    <article className="group relative isolate overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm hover:border-brand-500/30 transition-all duration-300">
      {/* Full left border with gradient → subtle */}
      <div
        className={cn(
          "absolute left-0 top-0 h-full w-[3px]",
          isYes
            ? "bg-gradient-to-b from-signal-yes via-signal-yes/40 to-signal-yes/10"
            : "bg-gradient-to-b from-signal-no via-signal-no/40 to-signal-no/10",
        )}
        aria-hidden
      />

      <div className="px-5 py-5 md:px-6">

        {/* ── Row 1: one dense meta line ── */}
        <div className="mb-3.5 flex flex-wrap items-center gap-2">
          <CategoryPill label={signal.categoryLabel} />
          <DirectionBadge direction={signal.direction} size="sm" />
          <span className={cn(
            "num inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[0.75rem] font-semibold",
            signal.score >= 85
              ? "border-brand-400/40 bg-brand-400/10 text-brand-300"
              : "border-signal-amber/40 bg-signal-amber/10 text-signal-amber",
          )}>
            {signal.score}
          </span>
          <span className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[0.75rem]",
            signal.windowHours <= 6
              ? "border-signal-amber/30 text-signal-amber"
              : "border-line text-ink-dim",
          )}>
            <Timer className="h-3 w-3" aria-hidden />
            {formatOpportunityWindow(signal.windowHours)}
          </span>
          <span className="ml-auto text-[0.6875rem] text-ink-dim">
            {timeSinceISO(signal.createdAt)}
          </span>
        </div>

        {/* ── Row 2: question — large, no label ── */}
        <h3 className="mb-3 font-display text-[1.25rem] font-semibold leading-snug tracking-tight text-ink">
          {signal.question}
        </h3>

        {/* ── Row 3: catalyst — inline, no box ── */}
        <p className="mb-4 text-[0.9375rem] leading-relaxed text-ink-readable">
          <span className="mr-2 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-brand-400">
            Détecté
          </span>
          {signal.catalyst}
        </p>

        {/* ── Row 4: source chips + market + CTA ── */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 border-t border-line/50 pt-3.5">
          {/* Source trust chips */}
          <div className="flex flex-wrap items-center gap-1.5">
            {tier1Sources.slice(0, 3).map((s) => (
              <span
                key={s.name}
                className="inline-flex items-center gap-1 rounded-full border border-line bg-obsidian-800/60 px-2 py-0.5 text-[0.625rem] font-mono text-ink-dim"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500/60" aria-hidden />
                {s.name.split(" ")[0]}
              </span>
            ))}
            {signal.sources.length > 3 && (
              <span className="text-[0.625rem] text-ink-dim">
                +{signal.sources.length - 3}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[0.75rem] text-ink-muted">
              Marché{" "}
              <span className={cn("num font-semibold", isYes ? "text-signal-yes" : "text-signal-no")}>
                {Math.round(signal.marketProbability * 100)}%
              </span>
            </span>
            <button
              type="button"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-4 text-[0.8125rem] font-semibold text-obsidian-900 hover:bg-brand-400 transition-colors shadow-[0_0_0_1px_rgba(11,224,166,0.3),0_6px_20px_-8px_rgba(11,224,166,0.5)]"
            >
              Prendre position
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* VARIANT D — "Conviction Banner"  (bonus — most opinionated)                */
/* Philosophy: context-aware accent. The card FEELS different at score 92 vs  */
/* score 55. Color temperature shifts with conviction. Catalyst replaces the  */
/* scoreLabel entirely. Zero redundancy. Single-column, flow reading.         */
/* ─────────────────────────────────────────────────────────────────────────── */

export function SignalCardV4({ signal }: { signal: Signal }) {
  const isYes = signal.direction === "YES"

  // Conviction level drives the entire visual tone
  const conviction =
    signal.score >= 85 ? "exceptional"
    : signal.score >= 70 ? "strong"
    : signal.score >= 55 ? "actionable"
    : "watch"

  const convictionStyles = {
    exceptional: {
      border: "border-brand-400/50",
      bar: "from-brand-400 to-brand-500/30",
      badge: "border-brand-400/40 bg-brand-400/12 text-brand-300",
      glow: "from-brand-500/12",
      label: "Conviction exceptionnelle",
    },
    strong: {
      border: "border-brand-500/35",
      bar: "from-brand-500 to-brand-500/20",
      badge: "border-brand-500/35 bg-brand-500/10 text-brand-400",
      glow: "from-brand-500/8",
      label: "Signal fort",
    },
    actionable: {
      border: "border-signal-amber/35",
      bar: "from-signal-amber to-signal-amber/20",
      badge: "border-signal-amber/35 bg-signal-amber/10 text-signal-amber",
      glow: "from-signal-amber/6",
      label: "Actionnable",
    },
    watch: {
      border: "border-line-strong",
      bar: "from-ink-dim/40 to-transparent",
      badge: "border-line-strong bg-obsidian-800 text-ink-muted",
      glow: "from-transparent",
      label: "À surveiller",
    },
  }[conviction]

  return (
    <article
      className={cn(
        "group relative isolate overflow-hidden rounded-2xl border bg-obsidian-850/60 backdrop-blur-sm transition-all duration-300",
        convictionStyles.border,
        "hover:shadow-elevated",
      )}
    >
      {/* Left conviction bar */}
      <div
        className={cn("absolute left-0 top-0 h-full w-[3px] bg-gradient-to-b", convictionStyles.bar)}
        aria-hidden
      />
      {/* Top ambient glow — conviction-tinted */}
      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b to-transparent opacity-60",
          convictionStyles.glow,
        )}
        aria-hidden
      />

      <div className="relative px-5 py-5 md:px-6">
        {/* ── Row 1: conviction badge + category + time ── */}
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 font-mono text-[0.6875rem] font-semibold uppercase tracking-wide",
              convictionStyles.badge,
            )}>
              <TrendingUp className="h-3 w-3" aria-hidden />
              {convictionStyles.label}
            </span>
            <CategoryPill label={signal.categoryLabel} />
          </div>
          <span className="text-[0.6875rem] text-ink-dim">
            {timeSinceISO(signal.createdAt)}
          </span>
        </div>

        {/* ── Row 2: question — the biggest text ── */}
        <h3 className="mb-3 font-display text-[1.25rem] font-semibold leading-snug tracking-tight text-ink">
          {signal.question}
        </h3>

        {/* ── Row 3: direction + market + score inline ── */}
        <div className="mb-4 flex flex-wrap items-center gap-2 text-[0.8125rem]">
          <DirectionBadge direction={signal.direction} size="md" />
          <span className="text-ink-muted">
            Marché :{" "}
            <span className={cn("num font-semibold", isYes ? "text-signal-yes" : "text-signal-no")}>
              {Math.round(signal.marketProbability * 100)}%
            </span>
          </span>
          <span className="text-ink-dim">·</span>
          <span className={cn(
            "inline-flex items-center gap-1 font-mono text-[0.75rem] font-medium",
            signal.windowHours <= 6 ? "text-signal-amber" : "text-ink-muted",
          )}>
            <Timer className="h-3 w-3" aria-hidden />
            Agir avant {formatOpportunityWindow(signal.windowHours)}
          </span>
        </div>

        {/* ── Row 4: catalyst ── */}
        <div className="mb-5 flex gap-3 rounded-lg border border-line/60 bg-obsidian-800/40 px-4 py-3.5">
          <Zap className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" aria-hidden />
          <div>
            <p className="mb-0.5 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-ink-dim">
              Ce qu'on a détecté
            </p>
            <p className="text-[0.9375rem] leading-relaxed text-ink/90">
              {signal.catalyst}
            </p>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between gap-3">
          {/* Sources as trust row */}
          <div className="flex items-center gap-1.5 text-[0.75rem] text-ink-dim">
            <Check className="h-3.5 w-3.5 text-brand-400" aria-hidden />
            <span>
              <span className="num font-medium text-ink">{signal.sources.length}</span> sources vérifiées
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1 rounded-md px-2.5 text-[0.75rem] text-ink-dim border border-line hover:border-line-strong hover:text-ink transition-colors"
              aria-label="Voir les sources"
            >
              <ExternalLink className="h-3 w-3" />
              Sources
            </button>
            <button
              type="button"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-4 text-[0.8125rem] font-semibold text-obsidian-900 hover:bg-brand-400 transition-colors shadow-[0_0_0_1px_rgba(11,224,166,0.3),0_6px_20px_-8px_rgba(11,224,166,0.5)]"
            >
              Prendre position
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}
