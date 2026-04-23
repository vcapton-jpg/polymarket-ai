import { useQuery } from "@tanstack/react-query"
import { fetchUserLimits } from "@/lib/api/limits"

export function useUserLimits() {
  return useQuery({
    queryKey: ["user-limits"],
    queryFn: fetchUserLimits,
    staleTime: 30_000,
  })
}
