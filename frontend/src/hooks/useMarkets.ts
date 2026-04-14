import { useQuery } from "@tanstack/react-query"
import { api, queryKeys } from "../lib/api"

export function useMarkets(params?: {
  category?: string
  active_only?: boolean
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: queryKeys.markets(params),
    queryFn: () => api.markets(params),
    refetchInterval: 60_000,
  })
}
