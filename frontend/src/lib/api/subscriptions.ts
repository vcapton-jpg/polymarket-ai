/**
 * Subscriptions API — Stripe checkout / portal.
 *
 * `startCheckout` returns the Stripe-hosted URL the caller should redirect
 * to (window.location.assign). `openPortal` does the same for the existing
 * customer self-service portal.
 *
 * Both require an authenticated session. Unauth'd users should be routed
 * to /signup?plan=pro first, not here.
 */

import { apiGet, apiPost, ApiError } from "@/lib/api/client"

export type PlanKey = "pro" | "trader"
export type BillingCycle = "monthly" | "annual"

export type CurrentPlan = {
  plan: "free" | "pro" | "trader"
  trial_ends_at: string | null
  card_attached: boolean
  details: Record<string, unknown>
}

export async function fetchCurrentPlan(): Promise<CurrentPlan> {
  return apiGet<CurrentPlan>("/subscriptions/current")
}

export async function startCheckout(
  plan: PlanKey,
  cycle: BillingCycle = "monthly",
): Promise<string> {
  const { checkout_url } = await apiPost<{ checkout_url: string }>(
    "/subscriptions/checkout",
    { plan, cycle },
  )
  return checkout_url
}

export async function openStripePortal(): Promise<string> {
  const { portal_url } = await apiPost<{ portal_url: string }>(
    "/subscriptions/portal",
    {},
  )
  return portal_url
}

/** Narrow helper the UI layer can use to decide whether to surface a
 *  "Passer Pro" CTA (returns the checkout URL) or fall back to the
 *  signup flow (returns null for 503s with a clear message). */
export async function safeStartCheckout(
  plan: PlanKey,
  cycle: BillingCycle = "monthly",
): Promise<{ url: string } | { error: string }> {
  try {
    const url = await startCheckout(plan, cycle)
    return { url }
  } catch (e) {
    if (e instanceof ApiError) {
      return { error: e.message }
    }
    return { error: "Impossible de lancer le paiement. Réessaie." }
  }
}
