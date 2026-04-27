import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { useTranslation } from "react-i18next"
import { ArrowUpRight, Bookmark, ChevronRight, Clock, Target, Timer } from "lucide-react"
import type { Signal } from "@/types/signal"
import { cn, timeSinceISO, categoryFallback, scoreTone, toneForLevel, type MetricTone } from "@/lib/utils"
import { formatOpportunityWindow } from "@/lib/formatWindow"
import { useMotionConfig, useStagger } from "@/lib/motion"
import { consumeQuotaOnServer } from "@/lib/dailyLimit"
import { useIsFreePlan } from "@/hooks/useAuth"
import { DirectionBadge, CategoryPill } from "./badges"

type SignalCardProps = {
  signal: Signal
  variant?: "default" | "teaser" | "compact"
  flash?: boolean
  index?: number
  className?: string
  example?: boolean
}

export function SignalCard({ signal, variant = "default", flash, index = 0, className, example }: SignalCardProps) {
  const { t } = useTranslation()
  const isYes = signal.direction === "YES"
  const isTeaser = variant === "teaser"
  const isCompact = variant === "compact"
  const scoreT = scoreTone(signal.score)
  const motionConfig = useMotionConfig("default")
  const stagger = useStagger("default")
  const isFreePlan = useIsFreePlan()

  const CardInner = (
    <article
      className={cn(
        "group relative isolate overflow-hidden rounded-2xl border bg-obsidian-850/60 backdrop-blur-sm",
        "border-line-strong hover:border-brand-500/40",
        "transition-premium",
        flash && "animate-flash",
        isTeaser && "pointer-events-none select-none",
        className,
      )}
    >
      {/* Direction accent bar (left edge) */}
      <div
        className={cn(
          "absolute left-0 top-0 h-full w-[3px]",
          isYes
            ? "bg-gradient-to-b from-signal-yes via-signal-yes/80 to-signal-yes/20"
            : "bg-gradient-to-b from-signal-no via-signal-no/80 to-signal-no/20",
        )}
        aria-hidden
      />

      {/* Subtle ambient gradient bg per direction */}
      <div
        className={cn(
          "pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full blur-3xl opacity-40",
          isYes ? "bg-signal-yes/20" : "bg-signal-no/20",
        )}
        aria-hidden
      />

      <div className="relative px-5 py-4 md:px-6 md:py-5">
        {/* Top row: category + time. Market thumbnail moved to hero row right
            slot for stronger visual anchor (was a small 40px chip up here). */}
        <div className="mb-3 flex items-start justify-between gap-3">
          <CategoryPill label={categoryFallback(signal.categoryLabel)} />
          <div className="flex flex-col items-end gap-1">
            <span className="inline-flex items-center gap-1 text-[0.6875rem] text-ink-readable whitespace-nowrap">
              <Clock className="h-3 w-3" aria-hidden />
              {timeSinceISO(signal.createdAt)}
            </span>
            {example && (
              <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-ink-dim/60 select-none">
                exemple
              </span>
            )}
          </div>
        </div>

        {/* Hero row: big score tile + meta + market thumbnail on the right */}
        <div
          className={cn(
            "mb-4 flex items-stretch gap-4 rounded-xl border px-4 py-3",
            "border-line/80 bg-obsidian-800/40",
          )}
        >
          <ScoreTile score={signal.score} tone={scoreT} label={signal.scoreLabel} signalId={signal.id} />
          <div className="flex flex-1 min-w-0 flex-col justify-center gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <DirectionBadge direction={signal.direction} size={isCompact ? "sm" : "md"} />
              <PillStat
                label="Marché"
                value={`${Math.round(signal.marketProbability * 100)}%`}
                tone={isYes ? "yes" : "no"}
              />
            </div>
            <div className="flex items-center gap-1.5 text-[0.75rem] text-ink-muted">
              <Timer className="h-3.5 w-3.5 text-brand-400" aria-hidden />
              <span>Agir avant</span>
              <span className="num font-semibold text-ink">{formatOpportunityWindow(signal.windowHours)}</span>
            </div>
          </div>
          {signal.image && (
            <img
              src={signal.image}
              alt=""
              aria-hidden
              className="h-16 w-16 shrink-0 self-center rounded-lg object-cover border border-line-strong/60"
            />
          )}
        </div>

        {/* Question */}
        <h3
          className={cn(
            "mb-4 font-display font-semibold tracking-tight text-ink text-balance",
            isCompact ? "text-base leading-snug" : "text-[1.125rem] md:text-[1.25rem] leading-tight",
          )}
        >
          {signal.question}
        </h3>

        {/* Sub-metrics */}
        {!isCompact && (
          <div className="mb-4 grid grid-cols-3 gap-x-4 gap-y-2">
            <MetricItem label="Confiance" value={signal.confidence} tone={toneForLevel(signal.confidence)} />
            <MetricItem label="Urgence" value={signal.urgency} tone={toneForLevel(signal.urgency)} />
            <MetricItem label="Tradabilité" value={signal.tradability} tone={toneForLevel(signal.tradability)} />
          </div>
        )}

        {/* Catalyst */}
        {!isCompact && (
          <div className="mb-4 rounded-lg border border-line/80 bg-obsidian-800/40 px-3.5 py-3">
            <p className="text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim mb-1">
              Ce qu’on a détecté
            </p>
            <p className="text-sm leading-relaxed text-ink/90">{signal.catalyst}</p>
          </div>
        )}

        {/* Footer row */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
          <div className="flex items-center gap-2 text-[0.75rem] text-ink-muted">
            <Target className="h-3.5 w-3.5 text-brand-400" aria-hidden />
            <span>
              <span className="num font-medium text-ink">{signal.sourcesCount ?? signal.sources.length}</span> sources
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              className="inline-flex h-10 w-10 md:h-8 md:w-8 items-center justify-center rounded-md text-ink-dim hover:text-ink hover:bg-obsidian-700 transition-premium cursor-pointer"
              aria-label={`Ajouter \u00AB\u00A0${signal.question}\u00A0\u00BB aux favoris`}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
              }}
            >
              <Bookmark className="h-4 w-4" />
            </button>
            {!isCompact && (
              <span
                aria-hidden
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand-500 px-3 text-[0.8125rem] font-medium text-obsidian-900 group-hover:bg-brand-400 transition-premium shadow-[0_0_0_1px_rgba(11,224,166,0.25),0_6px_20px_-8px_rgba(11,224,166,0.45)]"
              >
                {t("signal.cta.takePosition")}
                <ChevronRight className="h-3.5 w-3.5" />
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Teaser blur overlay — placed LAST so it sits above all content */}
      {isTeaser && (
        <>
          <div
            className="absolute inset-0 z-20 bg-obsidian-900/80 backdrop-blur-xl"
            aria-hidden
          />
          <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center p-6">
            <div className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-brand-500/40 bg-obsidian-850/95 px-4 py-2.5 text-[0.8125rem] font-medium text-brand-200 shadow-brand-glow">
              <span className="relative inline-flex h-1.5 w-1.5">
                <span className="absolute inset-0 animate-ping motion-reduce:animate-none rounded-full bg-brand-500 opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-500" />
              </span>
              Inscris-toi pour voir ce signal
              <ArrowUpRight className="h-3.5 w-3.5" />
            </div>
          </div>
        </>
      )}
    </article>
  )

  if (isTeaser) return CardInner

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ ...motionConfig, delay: index * stagger }}
    >
      <Link
        to={`/signals/${signal.id}`}
        className="block"
        aria-label={`Signal: ${signal.question}`}
        onClick={() => {
          // Increment the daily counter ONLY for Free-plan users — Pro
          // users have no cap, so accumulating their views would be wasted
          // storage + would trigger the wrong paywall banner if they later
          // downgraded. Gate at the hook-returned plan rather than reading
          // auth at click time: useAuth reactively updates on trial expiry.
          //
          // Server-side quota is the source of truth; consumeQuotaOnServer
          // optimistically updates localStorage, posts to Redis, then
          // reconciles on the response. Fire-and-forget: navigation
          // continues regardless of network outcome.
          if (!isFreePlan) return
          void consumeQuotaOnServer()
        }}
      >
        {CardInner}
      </Link>
    </motion.div>
  )
}

/* ───────────── Sub-components ───────────── */

function ScoreTile({
  score,
  tone,
  label,
  signalId,
}: {
  score: number
  tone: ReturnType<typeof scoreTone>
  label: string
  signalId: string
}) {
  const colors = {
    exceptional: "border-brand-400/50 bg-brand-400/10 text-brand-300",
    strong: "border-brand-500/40 bg-brand-500/10 text-brand-400",
    actionable: "border-signal-amber/40 bg-signal-amber/10 text-signal-amber",
    watch: "border-line-strong bg-obsidian-800 text-ink-muted",
  }[tone]

  return (
    <div
      className={cn(
        "flex shrink-0 flex-col items-center justify-center rounded-lg border px-4 py-2 min-w-[96px]",
        colors,
      )}
    >
      <motion.span
        layoutId={`score-${signalId}`}
        className="num font-display text-[2.25rem] font-semibold leading-none tracking-tight"
      >
        {score}
      </motion.span>
      <span className="mt-1 font-mono text-[0.625rem] uppercase tracking-[0.14em] opacity-80">
        {label}
      </span>
    </div>
  )
}

function PillStat({
  label,
  value,
  tone,
  icon,
  className,
}: {
  label: string
  value: string
  tone?: "yes" | "no"
  icon?: React.ReactNode
  className?: string
}) {
  const toneCls =
    tone === "yes"
      ? "text-signal-yes"
      : tone === "no"
        ? "text-signal-no"
        : "text-ink"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800/60 px-2.5 py-1 text-[0.75rem]",
        className,
      )}
    >
      {icon && <span className="text-ink-readable">{icon}</span>}
      <span className="text-ink-readable">{label}</span>
      <span className={cn("num font-semibold", toneCls)}>{value}</span>
    </span>
  )
}

function MetricItem({
  label,
  value,
  tone,
}: {
  label: string
  value: React.ReactNode
  tone?: MetricTone
}) {
  const toneCls =
    tone === "positive"
      ? "text-signal-yes"
      : tone === "warning"
        ? "text-signal-amber"
        : tone === "negative"
          ? "text-signal-no"
          : "text-ink"

  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim">{label}</span>
      <span className={cn("text-[0.8125rem] font-medium", toneCls)}>{value}</span>
    </div>
  )
}

