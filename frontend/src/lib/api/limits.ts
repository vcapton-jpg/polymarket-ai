import { apiGet } from "./client"

export type UserLimits = {
  budgetWeeklyEur: number
  maxStakeEur: number
  level: number
  realTradesCount: number
  consecutiveLosses: number
  weekSpentEur: number
  cooloffUntil: string | null
  quizPassed: boolean
  ageConfirmed18: boolean
}

type WireUserLimits = {
  budget_weekly_eur: number
  max_stake_eur: number
  level: number
  real_trades_count: number
  consecutive_losses: number
  week_spent_eur: number
  cooloff_until: string | null
  quiz_passed: boolean
  age_confirmed_18: boolean
}

function hydrate(w: WireUserLimits): UserLimits {
  return {
    budgetWeeklyEur: w.budget_weekly_eur,
    maxStakeEur: w.max_stake_eur,
    level: w.level,
    realTradesCount: w.real_trades_count,
    consecutiveLosses: w.consecutive_losses,
    weekSpentEur: w.week_spent_eur,
    cooloffUntil: w.cooloff_until,
    quizPassed: w.quiz_passed,
    ageConfirmed18: w.age_confirmed_18,
  }
}

/**
 * Fetch the authenticated user's Learn & Trade limits (budget, cooloff, flags).
 *
 * Consumes `GET /api/me/limits`. The server returns safe locked defaults
 * (20€/10€, quiz_passed=false, age_confirmed_18=false) when no row exists,
 * so callers don't need to handle 404 — just render against the values.
 */
export async function fetchUserLimits(): Promise<UserLimits> {
  const wire = await apiGet<WireUserLimits>("/me/limits")
  return hydrate(wire)
}
