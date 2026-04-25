import { describe, expect, it } from "vitest"
import {
  computeBadges,
  computeLevel,
  computeStreak,
  computeXP,
} from "../gamification"

describe("computeXP", () => {
  it("sums weighted activities and Apprendre section reads", () => {
    // 2*5 + 4*3 + 1*2 + 6*5 = 54
    expect(
      computeXP({
        outcomeViews: 2,
        paperTrades: 4,
        realTrades: 1,
        learnSectionsRead: 6,
      }),
    ).toBe(54)
  })

  it("returns 0 when no activity has happened", () => {
    expect(
      computeXP({
        outcomeViews: 0,
        paperTrades: 0,
        realTrades: 0,
        learnSectionsRead: 0,
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
  it("flags first-section + first-paper once unlocked, leaves others gated", () => {
    const badges = computeBadges({
      outcomeViews: 0,
      paperTrades: 1,
      learnSectionsRead: 1,
    })
    const byId = Object.fromEntries(badges.map((b) => [b.id, b.earned]))
    expect(byId["first-section"]).toBe(true)
    expect(byId["first-paper"]).toBe(true)
    expect(byId["all-sections"]).toBe(false)
    expect(byId["ten-outcomes"]).toBe(false)
    expect(byId["fifty-papers"]).toBe(false)
  })

  it("unlocks all-sections only when every Apprendre section is read", () => {
    const badges = computeBadges({
      outcomeViews: 0,
      paperTrades: 0,
      learnSectionsRead: 11,
    })
    const byId = Object.fromEntries(badges.map((b) => [b.id, b.earned]))
    expect(byId["all-sections"]).toBe(true)
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
