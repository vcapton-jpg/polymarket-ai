import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { scoreTone } from "@/lib/utils"
import { EASE_PREMIUM } from "@/lib/motion"

/* ───────────── Live Pill — pulsating "LIVE" indicator ───────────── */

export function LivePill({ className, label = "LIVE" }: { className?: string; label?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-signal-no/30 bg-signal-no/10 px-1.5 py-0.5",
        "text-label-xs font-mono font-medium tracking-[0.18em] text-signal-no",
        className,
      )}
    >
      <span className="relative inline-flex h-1 w-1">
        <span className="absolute inset-0 animate-ping motion-reduce:animate-none rounded-full bg-signal-no opacity-60" />
        <span className="relative inline-flex h-1 w-1 rounded-full bg-signal-no" />
      </span>
      {label}
    </span>
  )
}

/* ───────────── Direction Badge — BUY YES / BUY NO ───────────── */

export function DirectionBadge({
  direction,
  className,
  size = "md",
}: {
  direction: "YES" | "NO"
  className?: string
  size?: "sm" | "md" | "lg"
}) {
  const isYes = direction === "YES"
  const sizeClass = {
    sm: "h-6 px-2 text-label-xs",
    md: "h-7 px-2.5 text-xs",
    lg: "h-8 px-3 text-body-sm",
  }[size]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-mono font-semibold tracking-[0.08em]",
        sizeClass,
        isYes
          ? "border-signal-yes/40 bg-signal-yes/10 text-signal-yes"
          : "border-signal-no/40 bg-signal-no/10 text-signal-no",
        className,
      )}
    >
      <span aria-hidden>{isYes ? "▲" : "▼"}</span>
      BUY {direction}
    </span>
  )
}

/* ───────────── Tier Badge — source tier 1/2/3 ───────────── */

export function TierBadge({ tier }: { tier: 1 | 2 | 3 }) {
  const styles = {
    1: "border-tier-1/40 bg-tier-1/10 text-tier-1",
    2: "border-tier-2/40 bg-tier-2/10 text-tier-2",
    3: "border-tier-3/40 bg-tier-3/10 text-tier-3",
  }[tier]

  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded border px-1.5 font-mono text-[0.625rem] font-semibold tracking-widest",
        styles,
      )}
    >
      T{tier}
    </span>
  )
}

/* ───────────── Score Badge — 0-100 with contextual label ───────────── */

const toneColor: Record<ReturnType<typeof scoreTone>, string> = {
  watch: "text-ink-muted border-line-strong bg-obsidian-750",
  actionable: "text-signal-amber border-signal-amber/40 bg-signal-amber/10",
  strong: "text-brand-400 border-brand-500/40 bg-brand-500/10",
  exceptional: "text-brand-300 border-brand-400/50 bg-brand-400/15",
}

export function ScoreBadge({
  score,
  label,
  size = "md",
  showBar = false,
}: {
  score: number
  label?: string
  size?: "sm" | "md" | "lg"
  showBar?: boolean
}) {
  const tone = scoreTone(score)
  const sizeCls = {
    sm: "text-label-sm px-2 py-0.5",
    md: "text-body-sm px-2.5 py-1",
    lg: "text-sm px-3 py-1.5",
  }[size]

  return (
    <div className={cn("inline-flex items-center gap-2 rounded-md border", toneColor[tone], sizeCls)}>
      <span className="num font-semibold">{score}</span>
      <span className="text-ink-muted">·</span>
      <span className="font-medium">{label ?? ""}</span>
      {showBar && (
        <div className="ml-1 h-1 w-12 overflow-hidden rounded-full bg-line-strong">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${score}%` }}
            transition={{ duration: 0.8, ease: EASE_PREMIUM }}
            className={cn(
              "h-full",
              tone === "watch" && "bg-ink-dim",
              tone === "actionable" && "bg-signal-amber",
              tone === "strong" && "bg-brand-500",
              tone === "exceptional" && "bg-brand-300",
            )}
          />
        </div>
      )}
    </div>
  )
}

/* ───────────── Category Pill ───────────── */

export function CategoryPill({ label, className }: { label: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800/80 px-2 py-1",
        "text-label-sm font-medium text-ink-muted",
        className,
      )}
    >
      {label}
    </span>
  )
}
