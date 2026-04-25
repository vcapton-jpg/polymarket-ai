import { useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
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

const QUERY_KEY = ["remote-portfolio"] as const

/**
 * Fetch the authenticated user's portfolio from /api/portfolio.
 *
 * Migrated from a hand-rolled `useEffect` + `useState` pair to TanStack
 * Query so callers benefit from the global cache (no refetch flicker on
 * navigation back to Portfolio), automatic dedup across mounts, and the
 * shared retry/staleTime defaults declared in `main.tsx`.
 *
 * Backward-compatible shape: returns `{ data, loading, error }` so the
 * single existing consumer (`Portfolio.tsx`) doesn't need to change.
 *
 * Unauthenticated users get `EMPTY` immediately and skip the network
 * call (`enabled: hasToken()`). On AUTH_CHANGED_EVENT we invalidate the
 * cache so a fresh fetch fires after login/logout.
 */
export function useRemotePositions(): {
  data: RemotePortfolio
  loading: boolean
  error: Error | null
} {
  const qc = useQueryClient()

  const query = useQuery<RemotePortfolio, Error>({
    queryKey: QUERY_KEY,
    queryFn: fetchPortfolio,
    enabled: hasToken(),
  })

  useEffect(() => {
    const onAuth = () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
    }
    window.addEventListener(AUTH_CHANGED_EVENT, onAuth)
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, onAuth)
  }, [qc])

  return {
    data: query.data ?? EMPTY,
    loading: query.isFetching,
    error: query.error ?? null,
  }
}
