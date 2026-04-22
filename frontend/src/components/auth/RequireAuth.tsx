import { Navigate, useLocation } from "react-router-dom"
import type { ReactElement } from "react"
import { readAuth } from "@/lib/trial"

/**
 * Route guard for authed surfaces. Auth state lives in
 * `localStorage.foresight.auth`; we never read it inline — always via
 * `readAuth()` so the shape contract stays in one place (trial.ts).
 *
 * Signup-first intelligence: when there's no active session we look at the
 * persisted `has_ever_signed_up` flag on the AuthState. First-time visitors
 * go to `/signup`, returning users with stale/absent auth go to `/login`.
 * Both carry a `next=<encoded>` hop-back param.
 *
 * Note: an authed user with stale onboarding is NOT redirected from here —
 * `RequireOnboarding` in App.tsx owns that gate.
 */
export function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  const location = useLocation()
  const auth = readAuth()
  if (auth && auth.email) return children
  const next = encodeURIComponent(location.pathname + location.search)
  // `has_ever_signed_up` may persist even after clearAuth() if the last
  // writeAuth carried it. Current trial-expiry downgrade preserves the flag.
  const target = auth?.has_ever_signed_up ? `/login?next=${next}` : `/signup?next=${next}`
  return <Navigate to={target} replace />
}
