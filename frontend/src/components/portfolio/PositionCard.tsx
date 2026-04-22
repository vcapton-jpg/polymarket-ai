import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { ArrowUpRight, Clock, Wallet, X } from "lucide-react"
import type { Position, PositionStatus } from "@/types/signal"
import { cn, timeSinceISO, categoryFallback } from "@/lib/utils"
import { withBuilderCode } from "@/lib/polymarket"
import {
  statusFromLifePercent,
  useLifeDecay,
  minutesRemaining,
  formatMinutesRemaining,
} from "@/lib/useLifeDecay"
import { CategoryPill, DirectionBadge } from "@/components/signals/badges"
import { statusAccentClass } from "./LifeBar"
import { removeManualPosition } from "@/lib/manualPositions"
import { useUserPreferences } from "@/lib/userPreferences"

const STATUS_LABEL: Record<PositionStatus, string> = {
  tenir: "Tenir",
  surveiller: "Surveiller",
  vendre: "Prendre profit",
}
const STATUS_DOT: Record<PositionStatus, string> = {
  tenir: "bg-signal-yes",
  surveiller: "bg-signal-amber",
  vendre: "bg-signal-no",
}
const STATUS_TEXT: Record<PositionStatus, string> = {
  tenir: "text-signal-yes",
  surveiller: "text-signal-amber",
  vendre: "text-signal-no",
}
const STATUS_FILL: Record<PositionStatus, string> = {
  tenir: "bg-gradient-to-r from-signal-yes to-signal-yes/60",
  surveiller: "bg-gradient-to-r from-signal-amber to-signal-amber/60",
  vendre: "bg-gradient-to-r from-signal-no to-signal-no/60",
}

type PositionCardProps = {
  position: Position
  className?: string
  /** Hide monetary amounts (for privacy / screenshots). */
  hideStake?: boolean
}

export function PositionCard({ position, className, hideStake = false }: PositionCardProps) {
  const { signal } = position
  const { formatMoney } = useUserPreferences()
  const isYes = signal.direction === "YES"

  const live = useLifeDecay(position.lifePercent)
  const status = statusFromLifePercent(live)
  const mins = minutesRemaining(live, signal.windowHours)
  const minsLabel = formatMinutesRemaining(mins)

  const gain = position.estimatedGain
  const gainPositive = gain >= 0
  const gainFormatted = hideStake ? "•••" : formatMoney(gain, { signed: true })
  const stakeFormatted = hideStake ? "•••" : formatMoney(position.stake)

  const priceDelta = position.currentPrice - position.entryPrice
  const priceDeltaPct = position.entryPrice > 0 ? (priceDelta / position.entryPrice) * 100 : 0

  const stopLinkClick = (e: React.MouseEvent) => {
    e.stopPropagation()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className={className}
    >
      <article
        className={cn(
          "group relative isolate overflow-hidden rounded-2xl border bg-obsidian-850/60 backdrop-blur-sm",
          "transition-premium",
          statusAccentClass(status),
        )}
      >
        {/* Direction accent bar */}
        <div
          className={cn(
            "absolute left-0 top-0 h-full w-[3px]",
            isYes
              ? "bg-gradient-to-b from-signal-yes via-signal-yes/80 to-signal-yes/20"
              : "bg-gradient-to-b from-signal-no via-signal-no/80 to-signal-no/20",
          )}
          aria-hidden
        />

        <div className="relative px-5 py-4 md:px-6 md:py-5">
          {/* Top: category + entry time + direction */}
          <div className="mb-3 flex items-center justify-between gap-3">
            <CategoryPill label={categoryFallback(signal.categoryLabel)} />
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[0.6875rem] text-ink-readable">
                <Clock className="h-3 w-3" aria-hidden />
                Ouvert {timeSinceISO(position.entryDate)}
              </span>
              <DirectionBadge direction={signal.direction} size="sm" />
            </div>
          </div>

          {/* Question */}
          <h3 className="mb-4 font-display text-title-sm md:text-title-md font-semibold leading-snug tracking-tight text-ink text-balance">
            {signal.question}
          </h3>

          {/* Entry / Current / PnL row */}
          <div className="mb-4 grid grid-cols-3 gap-3 rounded-xl border border-line/80 bg-obsidian-800/40 px-4 py-3">
            <PriceCell
              label="Entrée"
              value={position.entryPrice.toFixed(2)}
              sub={stakeFormatted}
            />
            <PriceCell
              label="Actuel"
              value={position.currentPrice.toFixed(2)}
              sub={`${priceDelta >= 0 ? "+" : ""}${priceDeltaPct.toFixed(0)}%`}
              subTone={priceDelta >= 0 ? "positive" : "negative"}
              accent
            />
            <PriceCell
              label="Gain"
              value={gainFormatted}
              valueTone={gainPositive ? "positive" : "negative"}
              sub={`${gainPositive ? "+" : ""}${((gain / position.stake) * 100).toFixed(0)}%`}
              subTone={gainPositive ? "positive" : "negative"}
            />
          </div>

          {/* Recommandation */}
          <div className="mb-4 rounded-xl border border-line/70 bg-obsidian-800/30 px-4 py-3">
            <div className="mb-2.5 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={cn("relative inline-flex h-2 w-2 rounded-full", STATUS_DOT[status])} />
                <span className={cn("text-sm font-semibold", STATUS_TEXT[status])}>
                  {STATUS_LABEL[status]}
                </span>
              </div>
              <span className="num text-[0.75rem] text-ink-muted font-medium">{minsLabel}</span>
            </div>
            <div className="relative h-1.5 overflow-hidden rounded-full bg-line/70">
              <motion.div
                className={cn("h-full rounded-full", STATUS_FILL[status])}
                initial={false}
                animate={{ width: `${live}%` }}
                transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
              />
            </div>
            <div className="mt-1.5 flex justify-end">
              <span className="num text-[0.6875rem] text-ink-dim">{Math.round(live)}%</span>
            </div>
          </div>

          {/* Footer: stake + actions */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
            <div className="flex items-center gap-1.5 text-label-sm text-ink-muted">
              <Wallet className="h-3.5 w-3.5 text-brand-400" aria-hidden />
              <span>Mise</span>
              <span className="num font-semibold text-ink">{stakeFormatted}</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeManualPosition(position.id)
                }}
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800/60 px-3 text-[0.8125rem] font-medium text-ink-muted hover:border-signal-no/40 hover:text-signal-no transition-premium cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
                Fermer
              </button>
              <a
                href={withBuilderCode(signal.polymarketUrl)}
                target="_blank"
                rel="noreferrer"
                onClick={stopLinkClick}
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand-500 px-3 text-[0.8125rem] font-medium text-obsidian-900 hover:bg-brand-400 active:bg-brand-600 transition-premium cursor-pointer shadow-[0_0_0_1px_rgba(11,224,166,0.25),0_6px_20px_-8px_rgba(11,224,166,0.45)]"
              >
                Polymarket
                <ArrowUpRight className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </div>
      </article>
    </motion.div>
  )
}

/* ───────────── Sub-component ───────────── */

function PriceCell({
  label,
  value,
  valueTone,
  sub,
  subTone,
  accent,
}: {
  label: string
  value: string
  valueTone?: "positive" | "negative"
  sub?: string
  subTone?: "positive" | "negative"
  accent?: boolean
}) {
  const valueCls =
    valueTone === "positive"
      ? "text-signal-yes"
      : valueTone === "negative"
        ? "text-signal-no"
        : "text-ink"

  const subCls =
    subTone === "positive"
      ? "text-signal-yes"
      : subTone === "negative"
        ? "text-signal-no"
        : "text-ink-dim"

  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-label-xs font-mono uppercase tracking-[0.14em] text-ink-dim">
        {label}
      </span>
      <span
        className={cn(
          "num font-display text-body-md font-semibold leading-snug tracking-tight",
          valueCls,
          accent && "text-brand-300",
        )}
      >
        {value}
      </span>
      {sub && (
        <span className={cn("num text-label-xs font-medium", subCls)}>{sub}</span>
      )}
    </div>
  )
}
