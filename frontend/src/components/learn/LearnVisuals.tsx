import { motion, useReducedMotion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS, STAGGER } from "@/lib/motion"
import type { LucideIcon } from "lucide-react"
import { Info, Sparkles } from "lucide-react"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/* ───────────── Narrative text blocks ───────────── */

export function Lede({ children }: { children: ReactNode }) {
  return (
    <p className="text-[1rem] leading-[1.7] text-ink md:text-body-lg">
      {children}
    </p>
  )
}

export function Paragraph({ children }: { children: ReactNode }) {
  return <p className="text-[0.9375rem] leading-[1.7] text-ink-muted">{children}</p>
}

export function PrimaryCallout({
  children,
  icon: Icon = Sparkles,
  tone = "brand",
}: {
  children: ReactNode
  icon?: LucideIcon
  tone?: "brand" | "warning" | "danger"
}) {
  const toneClass =
    tone === "brand"
      ? "border-brand-500/30 bg-brand-500/5 text-brand-300"
      : tone === "warning"
        ? "border-signal-amber/30 bg-signal-amber/5 text-signal-amber"
        : "border-signal-no/30 bg-signal-no/5 text-signal-no"
  return (
    <div
      className={cn(
        "flex gap-3 rounded-2xl border px-5 py-4 md:px-6",
        toneClass,
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="text-[0.9375rem] leading-relaxed text-ink">{children}</div>
    </div>
  )
}

/* ───────────── Example cards (Tier-1/2/3, sell conditions, etc.) ───────────── */

export function ExampleGrid({
  children,
  columns = 3,
}: {
  children: ReactNode
  columns?: 2 | 3 | 4
}) {
  const colsClass =
    columns === 2
      ? "md:grid-cols-2"
      : columns === 3
        ? "md:grid-cols-3"
        : "md:grid-cols-2 lg:grid-cols-4"
  return <div className={cn("grid gap-3 md:gap-4", colsClass)}>{children}</div>
}

export function ExampleCard({
  eyebrow,
  title,
  body,
  accent,
  icon: Icon,
  footer,
}: {
  eyebrow?: string
  title: string
  body: ReactNode
  accent?: string
  icon?: LucideIcon
  footer?: ReactNode
}) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="flex h-full flex-col rounded-2xl border border-line-strong bg-obsidian-850/60 px-5 py-4"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        {eyebrow && (
          <span
            className="font-mono text-label-xs uppercase tracking-[0.14em]"
            style={accent ? { color: accent } : { color: "var(--tw-ink-dim)" }}
          >
            {eyebrow}
          </span>
        )}
        {Icon && <Icon className="h-4 w-4 text-ink-dim" aria-hidden />}
      </div>
      <h3 className="mb-1.5 font-display text-[1rem] font-semibold text-ink">
        {title}
      </h3>
      <div className="text-body-md leading-relaxed text-ink-muted">{body}</div>
      {footer && (
        <div className="mt-3 border-t border-line/60 pt-3 text-body-sm text-ink-muted">
          {footer}
        </div>
      )}
    </motion.article>
  )
}

/* ───────────── Animated horizontal frise ───────────── */

type FriseStep = {
  label: string
  description?: string
}

/**
 * Horizontal "news → signal → decision → exit" frise. Steps illuminate
 * sequentially using framer-motion. The effect respects
 * `prefers-reduced-motion` automatically because framer-motion reads the
 * same media query and collapses animations when set.
 */
export function AnimatedFrise({ steps }: { steps: FriseStep[] }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="rounded-2xl border border-line-strong bg-obsidian-850/60 p-5 md:p-6"
    >
      <ol className="flex flex-col gap-3 md:flex-row md:items-stretch md:gap-2">
        {steps.map((step, i) => (
          <motion.li
            key={step.label}
            initial={{ opacity: 0.35 }}
            animate={{ opacity: 1 }}
            transition={{
              delay: reduced ? 0 : i * 0.35,
              duration: reduced ? 0 : DURATIONS.expressive,
              ease: EASE_PREMIUM,
              repeat: reduced ? 0 : Infinity,
              repeatType: "reverse",
              repeatDelay: reduced ? 0 : steps.length * 0.5,
            }}
            className="relative flex-1 rounded-xl border border-line/70 bg-obsidian-800/60 px-4 py-3"
          >
            <div className="mb-1 flex items-center gap-2">
              <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/20 text-[0.625rem] font-semibold text-brand-300 ring-1 ring-brand-500/40">
                {i + 1}
              </span>
              <span className="font-display text-body-md font-semibold text-ink">
                {step.label}
              </span>
            </div>
            {step.description && (
              <p className="text-body-sm leading-relaxed text-ink-muted">
                {step.description}
              </p>
            )}
            {i < steps.length - 1 && (
              <span
                aria-hidden
                className="absolute right-[-6px] top-1/2 hidden h-px w-3 -translate-y-1/2 bg-line-strong md:block"
              />
            )}
          </motion.li>
        ))}
      </ol>
    </motion.div>
  )
}

/* ───────────── Expert technical appendix ───────────── */

export function ExpertAppendix({
  title = "Appendice technique",
  children,
}: {
  title?: string
  children: ReactNode
}) {
  return (
    <aside className="rounded-2xl border border-line/80 bg-obsidian-900/70 px-5 py-4 md:px-6">
      <div className="mb-2 flex items-center gap-2">
        <Info className="h-3.5 w-3.5 text-ink-dim" aria-hidden />
        <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
          {title} · Confirmé
        </span>
      </div>
      <div className="space-y-2 text-body-md leading-relaxed text-ink-muted">
        {children}
      </div>
    </aside>
  )
}

/* ───────────── Score bars (section ⑤) ───────────── */

export type ScoreBar = {
  label: string
  description: string
  weight: number // 0..1 — used for visual width
  color: string // accent color
  /** Only shown to Confirmé profiles via the appendix. */
  technicalWeight?: string
}

export function ScoreBars({ bars }: { bars: ScoreBar[] }) {
  const reduced = useReducedMotion()
  // Sequence each bar's parts: row fade-in, then bar-fill. The container drives
  // stagger only once on viewport entry.
  const container = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduced ? 0 : STAGGER.default,
        delayChildren: reduced ? 0 : 0.05,
      },
    },
  }
  const row = {
    hidden: { opacity: 0, x: -6 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: DURATIONS.default, ease: EASE_PREMIUM },
    },
  }
  return (
    <motion.ul
      className="space-y-3"
      variants={container}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.25 }}
    >
      {bars.map((bar) => (
        <motion.li
          key={bar.label}
          variants={row}
          className="rounded-xl border border-line/60 bg-obsidian-850/50 px-4 py-3"
        >
          <div className="mb-1 flex items-center justify-between gap-3">
            <span className="font-display text-[0.9375rem] font-semibold text-ink">
              {bar.label}
            </span>
            <span className="num font-mono text-label-xs text-ink-dim">
              {Math.round(bar.weight * 100)}%
            </span>
          </div>
          <p className="mb-2 text-body-sm leading-relaxed text-ink-muted">
            {bar.description}
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-obsidian-800">
            <motion.div
              initial={{ width: 0 }}
              whileInView={{ width: `${bar.weight * 100}%` }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{
                duration: reduced ? 0 : DURATIONS.expressive + 0.3,
                ease: EASE_PREMIUM,
              }}
              className="h-full rounded-full"
              style={{ backgroundColor: bar.color }}
            />
          </div>
        </motion.li>
      ))}
    </motion.ul>
  )
}

/* ───────────── Looping life bar (section ⑥) ───────────── */

/**
 * Life bar that visually depletes from full → 0 over 4 seconds and loops.
 * Matches the spec at README-V2 line 726: "visuel animé qui boucle
 * toutes les 4 secondes pour montrer la dégradation".
 */
export function LoopingLifeBar() {
  return (
    <div className="rounded-2xl border border-line-strong bg-obsidian-850/60 px-5 py-5 md:px-6 md:py-6">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
          Barre de vie · démo animée
        </span>
        <span className="num font-mono text-label-xs text-ink-dim">4s boucle</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-obsidian-800">
        <motion.div
          // Hex values mirror tailwind tokens chart-yes / chart-amber / chart-no
          // (framer-motion animate requires raw color values).
          initial={{ width: "100%", backgroundColor: "#4ADE80" }}
          animate={{
            width: ["100%", "70%", "40%", "15%", "0%"],
            backgroundColor: ["#4ADE80", "#4ADE80", "#FBBF24", "#F87171", "#F87171"],
          }}
          transition={{
            duration: 4,
            ease: "linear",
            repeat: Infinity,
            repeatType: "loop",
          }}
          className="h-full rounded-full"
        />
      </div>
      <div className="mt-2 grid grid-cols-3 text-center text-label-xs text-ink-dim">
        <span>Frais</span>
        <span>Se dégrade</span>
        <span>Expiré</span>
      </div>
    </div>
  )
}
