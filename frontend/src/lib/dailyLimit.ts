/**
 * Daily signal view counter for Free-plan paywall mechanics.
 *
 * Two-layer store:
 *   1. Server (Redis, authoritative) — see `/api/me/quota`. Synced on
 *      mount and after every click-through via `syncQuotaFromServer()` /
 *      `consumeQuotaOnServer()` in the callers that opt in.
 *   2. localStorage mirror under
 *      `foresight.daily_signals_viewed_YYYY-MM-DD` — used for optimistic
 *      updates and offline resilience. Stays authoritative for unauth'd
 *      users (the server never sees them).
 *
 * Old daily keys (>7 days) are pruned on mount by the Signals page.
 */

import {
  DAILY_LIMIT_KEY_PREFIX,
  DAILY_SIGNAL_VIEWED_EVENT,
} from "./storageKeys"
import { todayISODate } from "./utils"
import { consumeQuota, fetchQuota } from "./api/quota"
import { hasToken } from "./api/auth"

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

/** Write the server's authoritative count into the local mirror. Used on
 *  mount + after navigation so the paywall UI self-heals if the user
 *  consumed signals from another device. No-op for unauth'd users. */
export async function syncQuotaFromServer(): Promise<number | null> {
  if (typeof window === "undefined") return null
  if (!hasToken()) return null
  try {
    const q = await fetchQuota()
    // Pro users carry `limit=-1`; don't write a counter for them.
    if (q.limit === -1) return null
    try {
      localStorage.setItem(getDailyKey(), String(q.used))
      window.dispatchEvent(new Event(DAILY_SIGNAL_VIEWED_EVENT))
    } catch {
      // ignore — mirror write can fail in private mode
    }
    return q.used
  } catch {
    return null
  }
}

/** Optimistic consume: bump the local mirror immediately, then POST to the
 *  server. If the server disagrees (e.g. multi-device race) we overwrite
 *  with the authoritative value. Gracefully returns the optimistic count
 *  when the server is unreachable or the user is unauth'd. */
export async function consumeQuotaOnServer(): Promise<number> {
  const optimistic = incrementDailyCount()
  if (typeof window === "undefined") return optimistic
  if (!hasToken()) return optimistic
  try {
    const q = await consumeQuota()
    if (q.limit === -1) return optimistic
    try {
      localStorage.setItem(getDailyKey(), String(q.used))
      window.dispatchEvent(new Event(DAILY_SIGNAL_VIEWED_EVENT))
    } catch {
      // ignore
    }
    return q.used
  } catch {
    return optimistic
  }
}
