/** JWT localStorage key — single source of truth */
export const TOKEN_KEY = "foresight-token"
const LEGACY_TOKEN_KEYS = ["presage-token", "signal-token"] as const

/** Run once at module load so api + AuthProvider see the same token */
export function migrateLegacyAuthToken(): void {
  if (typeof localStorage === "undefined") return
  if (localStorage.getItem(TOKEN_KEY)) return
  for (const key of LEGACY_TOKEN_KEYS) {
    const v = localStorage.getItem(key)
    if (v) {
      localStorage.setItem(TOKEN_KEY, v)
      localStorage.removeItem(key)
      return
    }
  }
}

migrateLegacyAuthToken()

/** User UI preferences */
export const PREFS_KEY = "foresight-prefs"

export function migrateLegacyPrefs(): void {
  if (typeof localStorage === "undefined") return
  if (localStorage.getItem(PREFS_KEY)) return
  const legacy = localStorage.getItem("presage-prefs") ?? localStorage.getItem("signal-prefs")
  if (legacy) {
    localStorage.setItem(PREFS_KEY, legacy)
    localStorage.removeItem("presage-prefs")
    localStorage.removeItem("signal-prefs")
  }
}

migrateLegacyPrefs()
