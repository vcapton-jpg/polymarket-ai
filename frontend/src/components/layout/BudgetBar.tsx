import { Pause } from "lucide-react"
import { useUserLimits } from "@/hooks/useUserLimits"

/**
 * Persistent weekly-budget gauge shown in the authenticated shell.
 *
 * Displays `spent€ / budget€` + a progress bar clamped to [0,1]. When the
 * user is in a cooloff window (3 consecutive losses → 24h pause), swaps
 * the gauge for a "⏸ En pause" badge with the cooloff-until timestamp.
 *
 * Returns `null` when `/me/limits` has no data yet (loading or the 404
 * that Task 23 will remove). Silent by design — the OrderForm already
 * surfaces a blocking message on cooloff; this bar is just an anchor.
 */
export function BudgetBar() {
  const { data: limits } = useUserLimits()

  if (!limits) return null

  const inCooloff = limits.cooloffUntil
    ? new Date(limits.cooloffUntil) > new Date()
    : false

  if (inCooloff && limits.cooloffUntil) {
    const until = new Date(limits.cooloffUntil)
    const untilFr = until.toLocaleString("fr-FR", {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    })
    return (
      <div
        role="status"
        className="flex items-center gap-2 border-b border-line/60 bg-signal-no/10 px-4 py-2 text-sm text-signal-no lg:px-6"
      >
        <Pause className="h-3.5 w-3.5" aria-hidden="true" />
        <span>
          {`⏸ En pause jusqu'à ${untilFr} — 3 pertes consécutives.`}
        </span>
      </div>
    )
  }

  const pct = Math.min(
    1,
    Math.max(0, limits.weekSpentEur / Math.max(1, limits.budgetWeeklyEur)),
  )
  const pctLabel = Math.round(pct * 100)

  return (
    <div className="flex items-center gap-3 border-b border-line/60 bg-obsidian-900/60 px-4 py-2 text-xs text-ink-muted lg:px-6">
      <span className="num font-medium text-ink">
        {`${limits.weekSpentEur}€ / ${limits.budgetWeeklyEur}€`}
      </span>
      <span className="text-ink-dim">cette semaine</span>
      <div
        role="progressbar"
        aria-valuenow={pctLabel}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Budget hebdomadaire utilisé"
        className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-obsidian-800"
      >
        <div
          className={
            pct >= 0.9
              ? "h-full bg-signal-no transition-all"
              : pct >= 0.6
                ? "h-full bg-amber-400 transition-all"
                : "h-full bg-brand-500 transition-all"
          }
          style={{ width: `${pctLabel}%` }}
        />
      </div>
    </div>
  )
}
