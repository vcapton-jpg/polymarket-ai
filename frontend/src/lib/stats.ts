/**
 * Public-facing stats displayed on marketing surfaces (Homepage, Login, Signup).
 * Single source of truth — update here to keep all pages in sync.
 * Cursor: wire real values from backend metrics pipeline when ready.
 */
export const PUBLIC_STATS = {
  detectionLatencySeconds: 68,
  marketsMonitored: 61_247,
  signalsGeneratedTotal: 2_847,
  backtestWinRatePct: 71,
  activeTradersWeek: 842,
  signalsToday: 57,
} as const

/** Format a number with French thin-space thousand separator. */
export function formatStat(n: number): string {
  return n.toLocaleString("fr-FR").replace(/\u202F/g, " ")
}
