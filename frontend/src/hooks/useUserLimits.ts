import { useQuery } from "@tanstack/react-query"
import { fetchUserLimits } from "@/lib/api/limits"
import { hasToken } from "@/lib/api/auth"

/**
 * Fetches the authenticated user's Learn & Trade limits.
 *
 * `enabled: hasToken()` keeps anonymous sessions (marketing pages, logged-out
 * visitors) from triggering a 401 — `BudgetBar` renders null when `data` is
 * undefined, so the public shell stays clean.
 */
export function useUserLimits() {
  return useQuery({
    queryKey: ["user-limits"],
    queryFn: fetchUserLimits,
    staleTime: 30_000,
    enabled: hasToken(),
  })
}
