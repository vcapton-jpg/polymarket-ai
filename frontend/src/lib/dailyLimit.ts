/**
 * Daily signal view counter for Free-plan paywall mechanics.
 *
 * Stores a per-day counter in localStorage under
 * `foresight.daily_signals_viewed_YYYY-MM-DD`. The Signals feed reads it to
 * paywall the 6th+ card of the day; SignalCard increments it on click-through.
 *
 * Old daily keys (>7 days) are pruned on mount by the Signals page.
 */

import {
  DAILY_LIMIT_KEY_PREFIX,
  DAILY_SIGNAL_VIEWED_EVENT,
} from "./storageKeys"
import { todayISODate } from "./utils"

export {
  DAILY_LIMIT_KEY_PREFIX,
  DAILY_SIGNAL_VIEWED_EVENT,
  todayISODate,
}

export const FREE_DAILY_LIMIT = 5

export function getDailyKey(): string {
  return DAILY_LIMIT_KEY_PREFIX + todayISODate()
}

export function readDailyCount(): number {
  if (typeof window === "undefined") return 0
  try {
    return Number(localStorage.getItem(getDailyKey())) || 0
  } catch {
    return 0
  }
}

export function incrementDailyCount(): number {
  if (typeof window === "undefined") return 0
  try {
    const next = readDailyCount() + 1
    localStorage.setItem(getDailyKey(), String(next))
    return next
  } catch {
    return 0
  }
}

export function cleanupOldDailyKeys(): void {
  if (typeof window === "undefined") return
  try {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i)
      if (k && k.startsWith(DAILY_LIMIT_KEY_PREFIX)) {
        const dateStr = k.slice(DAILY_LIMIT_KEY_PREFIX.length)
        const t = Date.parse(dateStr)
        if (!isNaN(t) && t < cutoff) localStorage.removeItem(k)
      }
    }
  } catch {
    // ignore
  }
}
