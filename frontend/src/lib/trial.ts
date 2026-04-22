/**
 * Foresight trial state — single source of truth for the 7-day Pro trial.
 *
 * On signup with plan=pro we store `trial_ends_at` (ISO) and `card_attached=false`
 * in `localStorage.foresight.auth`. At the end of the window we auto-downgrade
 * to Free and show the EndOfTrialModal once per session.
 */

import { AUTH_CHANGED_EVENT, STORAGE_KEYS } from "./storageKeys"

export const TRIAL_LENGTH_MS = 7 * 24 * 60 * 60 * 1000

export type AuthState = {
  email: string
  plan: "free" | "pro"
  trial_ends_at?: string
  card_attached?: boolean
  has_ever_signed_up?: boolean
}

const AUTH_KEY = STORAGE_KEYS.auth

export function readAuth(): AuthState | null {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<AuthState>
    if (!parsed || typeof parsed !== "object") return null
    // Legacy payloads without plan default to free so downstream reads are safe.
    const plan: AuthState["plan"] = parsed.plan === "pro" ? "pro" : "free"
    return {
      email: typeof parsed.email === "string" ? parsed.email : "",
      plan,
      trial_ends_at: typeof parsed.trial_ends_at === "string" ? parsed.trial_ends_at : undefined,
      card_attached: typeof parsed.card_attached === "boolean" ? parsed.card_attached : undefined,
      has_ever_signed_up:
        typeof parsed.has_ever_signed_up === "boolean" ? parsed.has_ever_signed_up : undefined,
    }
  } catch {
    return null
  }
}

export function writeAuth(next: AuthState): void {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify(next))
  } catch {
    // localStorage may be unavailable (private mode, quota). Fail silently —
    // the UI layer surfaces persistence errors where relevant.
  }
  // In-tab listeners: the native `storage` event only fires cross-tab, so
  // dispatch a custom event so useAuth / TrialBanner / AppShell react
  // immediately when the same tab mutates auth (e.g. trial expiry).
  try {
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
  } catch {
    // ignore — synthetic event dispatch failure is non-fatal
  }
}

/**
 * Log out. Preserves `has_ever_signed_up` so returning users see /login
 * instead of /signup on their next protected-route visit.
 *
 * Cursor: call this from the logout button handler. Do NOT removeItem()
 * the auth key directly — it would drop has_ever_signed_up and misroute
 * the user through the first-timer signup flow on re-visit.
 */
export function clearAuth(): void {
  if (typeof window === "undefined") return
  const existing = readAuth()
  const stub: AuthState = {
    email: "",
    plan: "free",
    has_ever_signed_up: existing?.has_ever_signed_up === true ? true : undefined,
  }
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify(stub))
  } catch {
    // ignore
  }
  try {
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
  } catch {
    // ignore
  }
}

export function isOnTrial(auth: AuthState | null): boolean {
  if (!auth) return false
  if (auth.plan !== "pro") return false
  if (auth.card_attached) return false
  if (!auth.trial_ends_at) return false
  const end = Date.parse(auth.trial_ends_at)
  if (Number.isNaN(end)) return false
  return end > Date.now()
}

export function trialEndDate(auth: AuthState | null): Date | null {
  if (!auth?.trial_ends_at) return null
  const t = Date.parse(auth.trial_ends_at)
  return Number.isNaN(t) ? null : new Date(t)
}

export function trialDaysRemaining(auth: AuthState | null): number {
  if (!isOnTrial(auth)) return 0
  const end = trialEndDate(auth)
  if (!end) return 0
  const ms = end.getTime() - Date.now()
  if (ms <= 0) return 0
  return Math.ceil(ms / (24 * 60 * 60 * 1000))
}

export function checkAndHandleTrialExpiry(): { expired: boolean; auth: AuthState | null } {
  const auth = readAuth()
  if (!auth) return { expired: false, auth: null }
  if (auth.plan !== "pro") return { expired: false, auth }
  if (auth.card_attached) return { expired: false, auth }
  if (!auth.trial_ends_at) return { expired: false, auth }
  const end = Date.parse(auth.trial_ends_at)
  if (Number.isNaN(end)) return { expired: false, auth }
  if (end >= Date.now()) return { expired: false, auth }
  // Auto-downgrade: clear trial markers, keep email + signup history.
  const downgraded: AuthState = {
    email: auth.email,
    plan: "free",
    has_ever_signed_up: auth.has_ever_signed_up,
  }
  writeAuth(downgraded)
  return { expired: true, auth: downgraded }
}

const FR_MONTHS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
] as const

export function formatTrialEndFR(d: Date): string {
  const day = d.getDate()
  const month = FR_MONTHS[d.getMonth()]
  const year = d.getFullYear()
  return `${day} ${month} ${year}`
}
