import { useQuery } from "@tanstack/react-query"
import { api, queryKeys } from "../lib/api"

export function useAccuracy(opts?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: queryKeys.accuracy,
    queryFn: api.accuracy,
    refetchInterval: opts?.refetchInterval ?? 120_000,
  })
}

export function useDashboardKpis(opts?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: queryKeys.dashboardKpis,
    queryFn: api.dashboardKpis,
    refetchInterval: opts?.refetchInterval ?? 60_000,
  })
}

export function useSimulatedPnl(minScore = 60) {
  return useQuery({
    queryKey: queryKeys.simulatedPnl(minScore),
    queryFn: () => api.simulatedPnl(minScore),
    refetchInterval: 120_000,
  })
}

export function useTrackRecord() {
  return useQuery({
    queryKey: queryKeys.trackRecord,
    queryFn: api.trackRecord,
    refetchInterval: 120_000,
  })
}
