/**
 * Auth API — thin client for /api/auth/*.
 *
 * The backend returns a JWT token + a compact user payload. For fully
 * hydrated user state (trial, preferences, profile) the client then calls
 * `fetchMe()` which maps to GET /api/auth/me.
 */

import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client"
import { STORAGE_KEYS } from "@/lib/storageKeys"

export type AuthUser = {
  id: number
  email: string | null
  plan: "free" | "pro"
  trial_ends_at: string | null
  card_attached: boolean
  created_at: string | null
}

export type AuthResponse = { token: string; user: AuthUser }

export type MeResponse = {
  id: number
  email: string | null
  plan: "free" | "pro"
  trial_ends_at: string | null
  card_attached: boolean
  stripe_customer_id: string | null
  preferences: Record<string, unknown> | null
  profile: Record<string, unknown> | null
  created_at: string
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEYS.token, token)
  } catch {
    // ignore — private mode / quota
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEYS.token)
  } catch {
    // ignore
  }
}

export function hasToken(): boolean {
  try {
    return !!window.localStorage.getItem(STORAGE_KEYS.token)
  } catch {
    return false
  }
}

export async function registerApi(
  email: string,
  password: string,
  plan: "free" | "pro" = "free",
  options: {
    age_confirmed_18: boolean
    country_residence: string
  },
): Promise<AuthResponse> {
  return apiPost<AuthResponse>("/auth/register", {
    email,
    password,
    plan,
    age_confirmed_18: options.age_confirmed_18,
    country_residence: options.country_residence,
  })
}

/**
 * Hard-delete the current user's account (RGPD Art. 17). Server cascades
 * the FK fan-out (`portfolios`, `positions`, `orders`, `user_limits`, …)
 * in one transaction. Caller is responsible for clearing local auth
 * state immediately after a 204.
 */
export async function deleteAccountApi(): Promise<void> {
  await apiDelete("/auth/me")
}

export async function loginApi(
  email: string,
  password: string,
): Promise<AuthResponse> {
  return apiPost<AuthResponse>("/auth/login", { email, password })
}

export async function googleLoginApi(credential: string): Promise<AuthResponse> {
  return apiPost<AuthResponse>("/auth/google", { credential })
}

export async function logoutApi(): Promise<void> {
  try {
    await apiPost("/auth/logout")
  } finally {
    clearToken()
  }
}

export async function fetchMe(): Promise<MeResponse | null> {
  if (!hasToken()) return null
  try {
    return await apiGet<MeResponse>("/auth/me")
  } catch (e) {
    if (
      e instanceof Error &&
      "status" in e &&
      (e as { status: number }).status === 401
    ) {
      clearToken()
      return null
    }
    throw e
  }
}

export async function putProfile(
  patch: Partial<{
    type: string
    experience: string
    reaction: string
    budget: string
    suggested_sizing: string
  }>,
): Promise<MeResponse> {
  return apiPut<MeResponse>("/auth/me/profile", patch)
}

export async function putPreferences(
  patch: Partial<{
    currency: "USD" | "EUR"
    language: "fr" | "en"
    exchange_rate: number
    notif_email: boolean
    notif_push: boolean
    notif_telegram: boolean
  }>,
): Promise<MeResponse> {
  return apiPut<MeResponse>("/auth/me/preferences", patch)
}
