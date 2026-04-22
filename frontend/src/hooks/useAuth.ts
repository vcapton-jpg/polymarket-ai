import { useEffect, useState } from "react"
import { readAuth, writeAuth, type AuthState } from "@/lib/trial"
import { AUTH_CHANGED_EVENT, STORAGE_KEYS } from "@/lib/storageKeys"
import { fetchMe, hasToken, type MeResponse } from "@/lib/api/auth"

/**
 * Reactive auth accessor. The ONLY React component-level interface to the
 * authoritative `foresight.auth` blob. Every consumer that needs live auth
 * state calls this hook; helpers that only need a snapshot (guards, event
 * handlers) can still use `readAuth()` directly.
 *
 * Subscribes to:
 *   - The native `storage` event (cross-tab writes — logout from a second tab,
 *     upgrade purchase in another window, card attachment, etc.)
 *   - The in-tab `foresight:auth-changed` CustomEvent dispatched by
 *     `writeAuth()` / `clearAuth()` so same-tab mutations (trial expiry
 *     downgrade, signup, login) propagate without waiting for a re-render.
 *
 * Returns `null` for unauth'd sessions. Pro-status is derived, not cached —
 * call sites that want it should read `auth?.plan === "pro"`.
 */
/** Pure local-only accessor for one-off reads (events, guards, etc.).
 *  For reactive state inside components, use `useAuth()`.
 */
export { readAuth } from "@/lib/trial"

/** Merge a /auth/me payload into the local AuthState blob. */
export function meToAuthState(me: MeResponse): AuthState {
  const prev = readAuth()
  return {
    email: me.email ?? prev?.email ?? "",
    plan: me.plan === "pro" ? "pro" : "free",
    trial_ends_at: me.trial_ends_at ?? undefined,
    card_attached: me.card_attached,
    has_ever_signed_up: prev?.has_ever_signed_up ?? true,
  }
}

export function useAuth(): AuthState | null {
  const [auth, setAuth] = useState<AuthState | null>(() => readAuth())

  useEffect(() => {
    const refresh = () => setAuth(readAuth())
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEYS.auth || e.key === null) refresh()
    }
    window.addEventListener("storage", onStorage)
    window.addEventListener(AUTH_CHANGED_EVENT, refresh)
    return () => {
      window.removeEventListener("storage", onStorage)
      window.removeEventListener(AUTH_CHANGED_EVENT, refresh)
    }
  }, [])

  // Hydrate from /auth/me at mount. This is what keeps the localStorage
  // AuthState blob aligned with the backend (plan flips, trial expiry,
  // stripe confirmation). Fire-and-forget; errors are swallowed in
  // fetchMe() for 401s so a stale token self-heals.
  useEffect(() => {
    if (!hasToken()) return
    let cancelled = false
    void fetchMe().then((me) => {
      if (cancelled || !me) return
      writeAuth(meToAuthState(me))
    })
    return () => {
      cancelled = true
    }
  }, [])

  return auth
}

/** Convenience selector — true only for authed users on Pro. */
export function useIsPro(): boolean {
  const auth = useAuth()
  return auth?.plan === "pro"
}

/** True for unauth'd users AND authed Free users. Paywall-appropriate. */
export function useIsFreePlan(): boolean {
  const auth = useAuth()
  return !auth || auth.plan !== "pro"
}
