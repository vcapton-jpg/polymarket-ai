import { useEffect, useState } from "react"
import { fetchPerformanceMe } from "@/lib/api/performance"
import { hasToken } from "@/lib/api/auth"
import { AUTH_CHANGED_EVENT } from "@/lib/storageKeys"
import { MOCK_PERFORMANCE } from "@/data/performance"
import type { PerformanceStats } from "@/types/signal"

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"

/**
 * Fetches the authenticated user's performance bundle from the API.
 *
 * Falls back to `MOCK_PERFORMANCE` for:
 *   - `VITE_USE_MOCKS=1` (demo mode)
 *   - Unauthenticated requests (no token in storage)
 *   - Any network / 5xx error (the UI never renders a blank Performance
 *     page — the stats in the mock are clearly signposted as demo in
 *     the V2 empty states where relevant).
 */
export function usePerformance() {
  const [stats, setStats] = useState<PerformanceStats>(MOCK_PERFORMANCE)
  const [loading, setLoading] = useState(false)
  const [isMock, setIsMock] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (USE_MOCKS || !hasToken()) {
        setStats(MOCK_PERFORMANCE)
        setIsMock(true)
        return
      }
      setLoading(true)
      try {
        const data = await fetchPerformanceMe()
        if (!cancelled) {
          setStats(data)
          setIsMock(false)
        }
      } catch {
        if (!cancelled) {
          setStats(MOCK_PERFORMANCE)
          setIsMock(true)
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

  return { stats, loading, isMock }
}
