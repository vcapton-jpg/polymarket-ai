import { useEffect, useState } from "react"
import { fetchPortfolio, type RemotePortfolio } from "@/lib/api/portfolio"
import { hasToken } from "@/lib/api/auth"
import { AUTH_CHANGED_EVENT } from "@/lib/storageKeys"

const EMPTY: RemotePortfolio = {
  positions: [],
  resolved: [],
  kpis: {
    total_positions: 0,
    active_positions: 0,
    resolved_positions: 0,
    total_stake: 0,
    total_estimated_gain: 0,
  },
}

/**
 * Fetch the authenticated user's portfolio from /api/portfolio. Returns
 * `EMPTY` before the first response lands (so the UI renders without
 * flickers) plus an explicit `loading` flag. Unauthenticated users get
 * `EMPTY` immediately (no network call).
 *
 * Refreshes on AUTH_CHANGED_EVENT so logout/login flips feed back into
 * the hook without requiring a page reload.
 */
export function useRemotePositions() {
  const [data, setData] = useState<RemotePortfolio>(EMPTY)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!hasToken()) {
        setData(EMPTY)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const p = await fetchPortfolio()
        if (!cancelled) setData(p)
      } catch (e) {
        if (!cancelled) {
          setData(EMPTY)
          setError(e instanceof Error ? e : new Error("Portfolio fetch failed"))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    const onAuth = () => void load()
    window.addEventListener(AUTH_CHANGED_EVENT, onAuth)
    return () => {
      cancelled = true
      window.removeEventListener(AUTH_CHANGED_EVENT, onAuth)
    }
  }, [])

  return { data, loading, error }
}
