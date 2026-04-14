import { useQuery } from "@tanstack/react-query"
import { api, queryKeys } from "../lib/api"

export type UseSignalsParams = {
  bucket?: string
  min_score?: number
  direction?: string
  limit?: number
  offset?: number
  /** Override default 30s polling (e.g. dashboard wants fresher KPIs). */
  refetchInterval?: number | false
  refetchOnWindowFocus?: boolean
}

function loadStoredPrefs(): { bucket?: string; min_score?: number } {
  try {
    const raw = localStorage.getItem("signal-prefs")
    if (!raw) return {}
    const p = JSON.parse(raw)
    const result: { bucket?: string; min_score?: number } = {}
    if (p.defaultBucket) result.bucket = p.defaultBucket
    if (p.defaultMinScore && p.defaultMinScore > 0) result.min_score = p.defaultMinScore
    return result
  } catch {
    return {}
  }
}

export function useSignals(params?: UseSignalsParams) {
  const {
    refetchInterval = 30_000,
    refetchOnWindowFocus,
    ...apiParams
  } = params ?? {}

  const storedPrefs = loadStoredPrefs()
  const merged = {
    ...storedPrefs,
    ...apiParams,
  }
  const hasParams = Object.keys(merged).length > 0

  return useQuery({
    queryKey: queryKeys.signals(hasParams ? merged : undefined),
    queryFn: () => api.signals(hasParams ? merged : undefined),
    refetchInterval,
    ...(refetchOnWindowFocus !== undefined ? { refetchOnWindowFocus } : {}),
  })
}

export function useSignal(id: number) {
  return useQuery({
    queryKey: queryKeys.signal(id),
    queryFn: () => api.signal(id),
    enabled: id > 0,
  })
}
