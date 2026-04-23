import { Flame } from "lucide-react"

type Props = { days: number }

/**
 * Shows the user's current daily-engagement streak (in days). Returns
 * null when there's no streak — an empty dot would be worse than
 * nothing. Streaks are based on outcome views / paper trades, not on
 * real trading, to stay educational.
 */
export function StreakIndicator({ days }: Props) {
  if (days === 0) return null
  return (
    <div
      className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-200"
      aria-label={`Série en cours : ${days} jour${days > 1 ? "s" : ""}`}
    >
      <Flame className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
      <span className="font-semibold">{`${days} jour${days > 1 ? "s" : ""}`}</span>
    </div>
  )
}
