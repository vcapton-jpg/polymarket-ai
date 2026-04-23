import { useQuery } from "@tanstack/react-query"
import { fetchOnboardingStatus } from "@/lib/api/onboarding"

export function useOnboardingStatus() {
  return useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
    staleTime: 10_000,
  })
}
