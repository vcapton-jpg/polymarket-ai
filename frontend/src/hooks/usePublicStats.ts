import { useQuery } from "@tanstack/react-query"
import { fetchPublicStats, type PublicStats } from "@/lib/api/publicStats"

/**
 * Marketing surface counters — Homepage, Login, Portfolio empty state.
 *
 * Replaces the hardcoded `PUBLIC_STATS` block in `lib/stats.ts` with a
 * live read of `/api/stats/public`. The endpoint is unauthenticated
 * and computes every field from real DB queries so AMF / DGCCRF can
 * never catch us advertising figures that don't match the database.
 *
 * Honest empty-state contract: `data` is `undefined` while loading,
 * each field returns 0 / null when the DB is empty. Callers MUST
 * render skeletons during the initial load and a clear placeholder
 * (e.g. "—" or "Lancement en bêta") for null/0 values — never fall
 * back to a fabricated number.
 *
 * 2 min stale time matches the backend's 60 s in-process cache; we
 * trade slight staleness for negligible round-trip volume on
 * homepage load.
 */
export function usePublicStats(): {
  data: PublicStats | undefined
  loading: boolean
  isError: boolean
} {
  const query = useQuery<PublicStats, Error>({
    queryKey: ["public-stats"],
    queryFn: fetchPublicStats,
    staleTime: 120_000,
  })
  return {
    data: query.data,
    loading: query.isLoading,
    isError: query.isError,
  }
}
