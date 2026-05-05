/**
 * `useSignalsList` — TanStack Query hook for the `/api/signals` list.
 *
 * Migrated from a hand-rolled `useState` + `useEffect` + `useCallback`
 * pattern in `Signals.tsx` (audit follow-up 2026-05-05, H11). Pre-PR:
 *
 *   - Every mount of `Signals` triggered a fresh fetch (no cache).
 *   - Every focus / unmount-remount cycle re-fetched.
 *   - There was no dedup with future hooks that might want the same
 *     list (e.g. dashboard summary, paper-trading widget).
 *   - The fetch logic, the loading state, the error state, and the
 *     "USE_MOCKS" escape hatch were all interleaved in the page
 *     component — over time it had become 7 stateful variables for one
 *     remote resource.
 *
 * Post-PR, the page consumes a single `useSignalsList()` call. The
 * shared cache (`staleTime: 60s` from `main.tsx`) keeps the list warm
 * across navigations; the query key includes the filter values so each
 * `(direction, minScore)` combination has its own independent slice
 * (no cross-pollination, but rapid filter toggles within an active
 * window dedupe naturally).
 *
 * Mock-first behavior is preserved (matches `usePerformance`,
 * `useRemotePositions`, `usePaperPortfolio`):
 *   - `VITE_USE_MOCKS=1` → always returns the static `MOCK_SIGNALS`, no
 *     network call.
 *   - Network / 5xx → `error` is exposed for the caller to render a
 *     banner, and `signals` falls back to an empty array (NOT to mocks)
 *     so the user understands "we tried and the API is down" rather
 *     than seeing demo data they cannot act on.
 */

import { useQuery } from "@tanstack/react-query"
import { fetchSignalsFromApi } from "@/lib/apiSignals"
import { MOCK_SIGNALS } from "@/data/signals"
import type { Signal } from "@/types/signal"

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"

export type UseSignalsListParams = {
  /** "YES" | "NO" | undefined (no direction filter). */
  direction?: "YES" | "NO"
  /** Minimum signal score (0–100) — `undefined` or 0 means "no minimum". */
  minScore?: number
  /** API page size — keep aligned with the rendered cap. */
  limit?: number
}

export type UseSignalsListResult = {
  signals: Signal[]
  total: number
  loading: boolean
  error: string | null
  /** True when the data on screen is the static mock bundle (either
   *  because `VITE_USE_MOCKS=1` or because TanStack Query is still
   *  initialising). The page uses this to decide whether to show a
   *  "demo data" banner. */
  isMock: boolean
  /** Force a refetch — wired to the page's manual refresh button. */
  refresh: () => Promise<unknown>
}

export function useSignalsList(
  params: UseSignalsListParams = {},
): UseSignalsListResult {
  const { direction, minScore, limit = 100 } = params

  // Keys mirror the API query string so two pages asking for the same
  // filters share a single in-memory copy. The `mocks` flag is part of
  // the key so a runtime toggle of `VITE_USE_MOCKS` (rare, but exists
  // in dev) doesn't return stale real-API data.
  const queryKey = [
    "signals-list",
    {
      direction: direction ?? null,
      minScore: minScore && minScore > 0 ? minScore : null,
      limit,
      mocks: USE_MOCKS,
    },
  ] as const

  const query = useQuery<{ signals: Signal[]; total: number }, Error>({
    queryKey,
    queryFn: async () => {
      if (USE_MOCKS) {
        return { signals: MOCK_SIGNALS, total: MOCK_SIGNALS.length }
      }
      return fetchSignalsFromApi({
        limit,
        direction,
        min_score: minScore && minScore > 0 ? minScore : undefined,
      })
    },
  })

  const isMock = USE_MOCKS

  return {
    signals: query.data?.signals ?? [],
    total: query.data?.total ?? 0,
    loading: query.isFetching,
    error: query.error?.message ?? null,
    isMock,
    refresh: () => query.refetch(),
  }
}
