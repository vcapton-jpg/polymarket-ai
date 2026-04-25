/**
 * Smart formatter for the "Agir avant X" opportunity-window badge on
 * signal cards. The backend computes `windowHours` as a float diffusion
 * horizon derived from signal characteristics (news age, urgency, source
 * tier, liquidity) — breaking news on a thin market can be minutes.
 *
 * Rendering tiers:
 *   < 1 min     → "< 1 min"
 *   < 1 h       → "X min"          (breaking news)
 *   < 36 h      → "X h"
 *   < 14 j      → "X j"            (typical cap for actionable signals)
 *   < 9 sem     → "X sem"          (defensive, rare in practice)
 *   etc.
 */
export function formatOpportunityWindow(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) return "expiré"

  const minutes = hours * 60
  if (minutes < 1) return "< 1 min"
  if (hours < 1) return `${Math.round(minutes)} min`
  // 1h–6h: render as "Xh YY" so a 1h26 window doesn't get rounded to "1 h"
  // and lose actionable precision. Beyond 6h we drop the minutes and round
  // to whole hours since the user no longer needs minute-level granularity.
  if (hours < 6) {
    const h = Math.floor(hours)
    const m = Math.round((hours - h) * 60)
    if (m === 60) return `${h + 1} h`
    return m === 0 ? `${h} h` : `${h}h${m.toString().padStart(2, "0")}`
  }
  if (hours < 36) return `${Math.round(hours)} h`

  const days = hours / 24
  if (days < 14) return `${Math.round(days)} j`

  const weeks = days / 7
  if (weeks < 9) return `${Math.round(weeks)} sem`

  const months = days / 30
  if (months < 18) return `${Math.round(months)} mois`

  const years = days / 365
  return `${years.toFixed(1)} an${years >= 2 ? "s" : ""}`
}
