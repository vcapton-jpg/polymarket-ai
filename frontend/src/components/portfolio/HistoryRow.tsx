import { ArrowUpRight, Check, X, Clock } from "lucide-react"
import type { Position } from "@/types/signal"
import { cn, categoryFallback } from "@/lib/utils"
import { withBuilderCode } from "@/lib/polymarket"
import { SourceBadge } from "./SourceBadge"
import { useUserPreferences } from "@/lib/userPreferences"

type HistoryRowProps = {
  position: Position
  className?: string
  /** Hide monetary amounts (for privacy / screenshots). */
  hideStake?: boolean
}

export function HistoryRow({ position, className, hideStake = false }: HistoryRowProps) {
  const { signal, correctPrediction, resolved } = position
  const { formatMoney, language } = useUserPreferences()
  const gain = position.estimatedGain
  const gainPositive = gain >= 0
  const gainFormatted = hideStake ? "•••" : formatMoney(gain, { signed: true })

  const date = new Date(position.entryDate)
  const dateStr = date.toLocaleDateString(language === "fr" ? "fr-FR" : "en-US", {
    day: "2-digit",
    month: "short",
  })

  return (
    <div
      className={cn(
        "grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 rounded-lg border border-line/70 bg-obsidian-800/30 px-4 py-3 text-body-sm",
        "hover:border-line-strong hover:bg-obsidian-800/50 transition-premium",
        className,
      )}
    >
      <OutcomePill correct={correctPrediction} resolved={resolved} />

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-label-xs text-ink-readable">
            {categoryFallback(signal.categoryLabel)}
          </span>
          <span className="text-ink-readable">·</span>
          <span className="num font-mono text-label-xs text-ink-readable">{dateStr}</span>
          <SourceBadge source={position.source} size="xs" />
        </div>
        <p className="mt-0.5 truncate font-medium text-ink">{signal.question}</p>
      </div>

      <span className="num font-mono text-label-sm text-ink-muted hidden sm:inline">
        Score {signal.score}
      </span>

      <span
        className={cn(
          "num inline-flex items-center font-display text-[0.9375rem] font-semibold tabular-nums",
          gainPositive ? "text-signal-yes" : "text-signal-no",
        )}
      >
        {gainFormatted}
      </span>

      <a
        href={withBuilderCode(signal.polymarketUrl)}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex h-7 items-center gap-1 rounded-md border border-line-strong px-2 text-label-xs text-ink-muted hover:border-brand-500/40 hover:text-brand-300 transition-premium cursor-pointer"
        aria-label="Voir sur Polymarket"
      >
        Voir
        <ArrowUpRight className="h-3 w-3" />
      </a>
    </div>
  )
}

function OutcomePill({
  correct,
  resolved,
}: {
  correct: boolean | null
  resolved: boolean
}) {
  if (!resolved || correct === null) {
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-signal-amber/30 bg-signal-amber/10 text-signal-amber">
        <Clock className="h-3.5 w-3.5" aria-hidden />
      </span>
    )
  }
  if (correct) {
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-signal-yes/30 bg-signal-yes/10 text-signal-yes">
        <Check className="h-3.5 w-3.5" aria-hidden />
      </span>
    )
  }
  return (
    <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-signal-no/30 bg-signal-no/10 text-signal-no">
      <X className="h-3.5 w-3.5" aria-hidden />
    </span>
  )
}
