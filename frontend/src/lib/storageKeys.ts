/**
 * Central registry of every localStorage / sessionStorage key Foresight
 * writes. Keep ALL reads and writes of these keys going through this module
 * so renames, grep-audits, and Cursor's backend integration have one place
 * to look. Do NOT inline string literals like `"foresight.auth"` in pages.
 *
 * Dynamic keys (date-scoped, hash-scoped) are exposed as factory functions.
 */

export const STORAGE_KEYS = {
  /** Authoritative AuthState blob (see lib/trial.ts). */
  auth: "foresight.auth",
  /** JWT bearer token issued by /api/auth/{login,register,google}. */
  token: "foresight.token",
  /** UserProfile blob (see types/signal.ts). */
  profile: "foresight.profile",
  /** Native-order positions written by OrderForm. */
  positions: "foresight.positions",
  /** Onboarding status: "pending" | "done" | "skipped". */
  onboarding: "foresight.onboarding",
  /** Pricing cycle toggle: "monthly" | "yearly". */
  pricingCycle: "foresight.pricing_cycle",
  /** Recoverable email draft from an in-flight Signup. */
  signupDraftEmail: "foresight.signup_draft_email",
  /** Coach-mark dismissed-once flag for the first Signals card. */
  firstSignalSeen: "foresight.first_signal_seen",
  /** Advanced-filters disclosure state on /signals. */
  signalsAdvFiltersOpen: "foresight.signals.advFiltersOpen",
  /** Beginner (Découvreur) coach-mark on /apprendre shown-once flag. */
  apprendreCoached: "foresight.apprendre_coached",
} as const

export const SESSION_KEYS = {
  /** Session flag: "on-trial expired" modal was shown once. */
  trialExpiryShown: "foresight.trial_expiry_shown",
  /** Dismissed the skip-onboarding banner on /signals this session. */
  skipBannerDismissed: "foresight.skip_banner_dismissed",
  /** Dismissed the sizing-personalisation nudge inside OrderForm. */
  sizingNudgeDismissed: "foresight.sizing_nudge_dismissed",
} as const

/** Fired after writeAuth() completes, so same-tab listeners can react.
 *  The native `storage` event only fires for CROSS-tab writes — this
 *  CustomEvent closes that gap inside the current tab. */
export const AUTH_CHANGED_EVENT = "foresight:auth-changed"

/** Fired after a position is inserted into STORAGE_KEYS.positions. */
export const POSITIONS_CHANGED_EVENT = "foresight:positions-changed"

/** Daily-limit family (see lib/dailyLimit.ts). */
export const DAILY_LIMIT_KEY_PREFIX = "foresight.daily_signals_viewed_"
export const DAILY_SIGNAL_VIEWED_EVENT = "foresight:daily_signal_viewed"

/** Trial banner dismissed-today family. Scoped per-day so a new day re-shows. */
export const TRIAL_BANNER_DISMISS_PREFIX = "foresight.trial_banner_dismissed_"

export function trialBannerDismissKey(isoDate: string): string {
  return `${TRIAL_BANNER_DISMISS_PREFIX}${isoDate}`
}
