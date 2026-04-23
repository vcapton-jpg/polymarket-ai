/**
 * Educational gamification primitives — XP, badges, streaks.
 *
 * These are intentionally *learning* metrics, not *profit* metrics:
 * we reward reading outcomes, practicing paper trades, and completing
 * the onboarding gates, not real-money wins. The spec is explicit that
 * gamification must not push users toward more trading.
 *
 * All math is client-side and deterministic so tests can pin it.
 */

export type Badge = {
  id: string
  label: string
  icon: string
  earned: boolean
}

/**
 * Inputs come from /onboarding/status (tutorialDone, quizPassed) and
 * /paper/positions (paperTrades count). outcomeViews + realTrades are
 * optional today — the relevant endpoints ship later but the weights
 * are baked in now so XP jumps are expected, not surprising.
 */
export function computeXP(input: {
  outcomeViews: number
  paperTrades: number
  realTrades: number
  tutorialDone: boolean
  quizPassed: boolean
}): number {
  return (
    input.outcomeViews * 5 +
    input.paperTrades * 3 +
    input.realTrades * 2 +
    (input.tutorialDone ? 25 : 0) +
    (input.quizPassed ? 25 : 0)
  )
}

/** Level curve: quadratic so early wins feel fast, later levels slow down. */
export function computeLevel(xp: number): number {
  return 1 + Math.floor(Math.sqrt(xp / 50))
}

export function computeBadges(input: {
  outcomeViews: number
  paperTrades: number
  tutorialDone: boolean
  quizPassed: boolean
}): Badge[] {
  return [
    { id: "tutorial", label: "Tutoriel terminé", icon: "🎓", earned: input.tutorialDone },
    { id: "quiz", label: "Quiz risque validé", icon: "🧠", earned: input.quizPassed },
    { id: "first-paper", label: "Premier paper trade", icon: "📝", earned: input.paperTrades >= 1 },
    { id: "ten-outcomes", label: "10 outcomes lus", icon: "📖", earned: input.outcomeViews >= 10 },
    { id: "fifty-papers", label: "50 paper trades", icon: "🏆", earned: input.paperTrades >= 50 },
  ]
}

/** Local-calendar yyyy-mm-dd — avoids UTC off-by-one near midnight. */
function localDayKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/**
 * Counts consecutive local calendar days (up to 365) ending today that
 * have at least one entry in `viewedDates`. Returns 0 if today is
 * missing — streaks decay overnight, matching Duolingo-style
 * expectation. Uses local-tz date keys on both sides so a view logged
 * at 23:00 local and checked at 01:00 local the next day doesn't
 * accidentally count as the same calendar day (which UTC slicing would
 * do for anyone west of UTC+00).
 */
export function computeStreak(viewedDates: string[]): number {
  if (viewedDates.length === 0) return 0
  const days = new Set(viewedDates.map((d) => localDayKey(new Date(d))))
  let streak = 0
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  for (let i = 0; i < 365; i++) {
    if (days.has(localDayKey(cursor))) {
      streak += 1
      cursor.setDate(cursor.getDate() - 1)
    } else {
      break
    }
  }
  return streak
}
