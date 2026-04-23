import { useQuery } from "@tanstack/react-query"
import { fetchOnboardingStatus } from "@/lib/api/onboarding"
import { hasToken } from "@/lib/api/auth"

/**
 * Fetches the server-authoritative onboarding gate status. Disabled for
 * anonymous sessions so public marketing pages don't trigger a 401.
 */
export function useOnboardingStatus() {
  return useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
    staleTime: 10_000,
    enabled: hasToken(),
  })
}
