/**
 * Cookie & local-storage consent state machine.
 *
 * The CNIL requires:
 *   1. No non-essential storage / tracker fires before the user makes a choice.
 *   2. "Refuse all" must be as easy as "Accept all" (no friction asymmetry).
 *   3. The user can revisit the choice at any time.
 *   4. The consent record is versioned so a policy change re-prompts.
 *
 * The categories below mirror our actual surface:
 *
 *   essential   Auth (JWT in localStorage), preferences (language /
 *               currency), open-position state. These are strictly
 *               necessary — the app does not function without them.
 *               No opt-out (CNIL exempt under Art. 82, alinéa 2).
 *
 *   analytics   Sentry, performance metrics, behavioural analytics.
 *               OFF by default; the app must function fully without.
 *
 *   marketing   Re-targeting pixels, conversion tracking, third-party
 *               ad SDKs. Today: NONE. Reserved so when something does
 *               land it cannot bypass the gate by accident.
 *
 * Persistence: localStorage under `foresight.cookieConsent`. A bumped
 * `CONSENT_VERSION` invalidates older records and re-prompts.
 *
 * Read-side: `isAllowed("analytics")` is the single guard every
 * non-essential script loader must consult before firing. The hook
 * `useConsent()` lets components reactively show/hide UI based on
 * the consent state.
 */

import { useEffect, useState } from "react"

export type ConsentCategory = "essential" | "analytics" | "marketing"

export type ConsentRecord = {
  version: number
  decidedAt: string // ISO 8601 UTC
  categories: Record<ConsentCategory, boolean>
}

const STORAGE_KEY = "foresight.cookieConsent"
const CONSENT_VERSION = 1
const CONSENT_EVENT = "foresight:consent-changed"

const DEFAULTS: Record<ConsentCategory, boolean> = {
  essential: true, // Always granted (Art. 82 alinéa 2 — exempt).
  analytics: false,
  marketing: false,
}

function safeRead(): ConsentRecord | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ConsentRecord
    if (parsed.version !== CONSENT_VERSION) return null
    // Defensive: treat unknown categories as "not granted".
    return {
      version: parsed.version,
      decidedAt: parsed.decidedAt,
      categories: { ...DEFAULTS, ...parsed.categories, essential: true },
    }
  } catch {
    return null
  }
}

function safeWrite(record: ConsentRecord): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record))
    window.dispatchEvent(
      new CustomEvent(CONSENT_EVENT, { detail: record }),
    )
  } catch {
    // Private mode / quota — nothing we can do.
  }
}

export function getConsent(): ConsentRecord | null {
  return safeRead()
}

export function hasDecided(): boolean {
  return safeRead() !== null
}

/**
 * Persist a decision and notify subscribers. Pass a partial map; missing
 * keys default to FALSE (refused). `essential` is always TRUE regardless
 * of input — the schema enforces what's actually CNIL-exempt.
 */
export function setConsent(
  partial: Partial<Record<ConsentCategory, boolean>>,
): ConsentRecord {
  const next: ConsentRecord = {
    version: CONSENT_VERSION,
    decidedAt: new Date().toISOString(),
    categories: {
      essential: true,
      analytics: !!partial.analytics,
      marketing: !!partial.marketing,
    },
  }
  safeWrite(next)
  return next
}

/** "Accept all" / "Refuse all" — must be equally one-click (CNIL). */
export function acceptAll(): ConsentRecord {
  return setConsent({ analytics: true, marketing: true })
}
export function refuseAll(): ConsentRecord {
  return setConsent({ analytics: false, marketing: false })
}

/** Used by Settings → "Revoir mes choix" so the banner reappears. */
export function revoke(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
    window.dispatchEvent(
      new CustomEvent(CONSENT_EVENT, { detail: null }),
    )
  } catch {
    // ignore
  }
}

export function isAllowed(category: ConsentCategory): boolean {
  if (category === "essential") return true
  const record = safeRead()
  return record?.categories[category] === true
}

/**
 * React hook — returns the current record (or null if undecided) and
 * re-renders on consent changes. Components can mount tracking SDKs
 * inside an effect that depends on the returned value.
 */
export function useConsent(): ConsentRecord | null {
  const [record, setRecord] = useState<ConsentRecord | null>(() => safeRead())

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<ConsentRecord | null>).detail ?? null
      setRecord(detail)
    }
    window.addEventListener(CONSENT_EVENT, onChange)
    // Cross-tab: storage event fires for other tabs writing the same key.
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setRecord(safeRead())
    }
    window.addEventListener("storage", onStorage)
    return () => {
      window.removeEventListener(CONSENT_EVENT, onChange)
      window.removeEventListener("storage", onStorage)
    }
  }, [])

  return record
}

export const COOKIE_CONSENT_VERSION = CONSENT_VERSION
export const COOKIE_CONSENT_STORAGE_KEY = STORAGE_KEY
export const COOKIE_CONSENT_EVENT = CONSENT_EVENT
