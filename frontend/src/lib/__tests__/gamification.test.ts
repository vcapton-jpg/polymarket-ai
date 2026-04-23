import { describe, expect, it } from "vitest"
import {
  computeBadges,
  computeLevel,
  computeStreak,
  computeXP,
} from "../gamification"

describe("computeXP", () => {
  it("sums weighted activities and flat onboarding bonuses", () => {
    // 2*5 + 4*3 + 1*2 + 25 + 25 = 74
    expect(
      computeXP({
        outcomeViews: 2,
        paperTrades: 4,
        realTrades: 1,
        tutorialDone: true,
        quizPassed: true,
      }),
    ).toBe(74)
  })

  it("returns 0 when no activity has happened", () => {
    expect(
      computeXP({
        outcomeViews: 0,
        paperTrades: 0,
        realTrades: 0,
        tutorialDone: false,
        quizPassed: false,
      }),
    ).toBe(0)
  })
})

describe("computeLevel", () => {
  it("starts at level 1", () => {
    expect(computeLevel(0)).toBe(1)
    expect(computeLevel(49)).toBe(1)
  })

  it("reaches level 2 at 50 XP and level 3 at 200 XP", () => {
    expect(computeLevel(50)).toBe(2)
    expect(computeLevel(199)).toBe(2)
    expect(computeLevel(200)).toBe(3)
  })
})

describe("computeBadges", () => {
  it("flags tutorial + quiz + first-paper as earned once their conditions are met", () => {
    const badges = computeBadges({
      outcomeViews: 0,
      paperTrades: 1,
      tutorialDone: true,
      quizPassed: true,
    })
    const byId = Object.fromEntries(badges.map((b) => [b.id, b.earned]))
    expect(byId.tutorial).toBe(true)
    expect(byId.quiz).toBe(true)
    expect(byId["first-paper"]).toBe(true)
    expect(byId["ten-outcomes"]).toBe(false)
    expect(byId["fifty-papers"]).toBe(false)
  })
})

describe("computeStreak", () => {
  it("returns 0 on an empty history", () => {
    expect(computeStreak([])).toBe(0)
  })

  it("counts consecutive days ending today", () => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const yday = new Date(today)
    yday.setDate(yday.getDate() - 1)
    expect(computeStreak([today.toISOString(), yday.toISOString()])).toBe(2)
  })

  it("breaks the streak when today is missing", () => {
    const yday = new Date()
    yday.setDate(yday.getDate() - 1)
    expect(computeStreak([yday.toISOString()])).toBe(0)
  })
})
