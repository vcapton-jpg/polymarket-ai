import { useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { fetchPerformanceMe } from "@/lib/api/performance"
import { hasToken } from "@/lib/api/auth"
import { AUTH_CHANGED_EVENT } from "@/lib/storageKeys"
import { MOCK_PERFORMANCE } from "@/data/performance"
import type { PerformanceStats } from "@/types/signal"

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"
const QUERY_KEY = ["performance-me"] as const

/**
 * Fetches the authenticated user's performance bundle from the API.
 *
 * Migrated from `useEffect` + `useState` to TanStack Query for the same
 * reasons as `useRemotePositions`: shared cache, no refetch flicker
 * across navigations, automatic dedup, and the shared retry/staleTime
 * defaults from `main.tsx`.
 *
 * Mock-first behavior is preserved:
 *   - `VITE_USE_MOCKS=1` → always returns `MOCK_PERFORMANCE`, no fetch
 *   - No auth token → `MOCK_PERFORMANCE`, no fetch
 *   - Network / 5xx error → `MOCK_PERFORMANCE` (we never render a blank
 *     Performance page; the mock is signposted as demo where relevant)
 *
 * Backward-compatible shape: `{ stats, loading, isMock }`.
 */
export function usePerformance(): {
  stats: PerformanceStats
  loading: boolean
  isMock: boolean
} {
  const qc = useQueryClient()
  const enabled = !USE_MOCKS && hasToken()

  const query = useQuery<PerformanceStats, Error>({
    queryKey: QUERY_KEY,
    queryFn: fetchPerformanceMe,
    enabled,
  })

  useEffect(() => {
    const onAuth = () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
    }
    window.addEventListener(AUTH_CHANGED_EVENT, onAuth)
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, onAuth)
  }, [qc])

  // Disabled (mocks/no-auth) OR fetch failed → fall back to the mock
  // bundle. `isMock` is true whenever the data on screen is not a fresh
  // server payload, so the UI can still surface the demo-mode banner.
  const usingMock = !enabled || query.isError || !query.data

  return {
    stats: usingMock ? MOCK_PERFORMANCE : query.data,
    loading: query.isFetching,
    isMock: usingMock,
  }
}
