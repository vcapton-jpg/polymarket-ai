import { apiGet } from "@/lib/api/client"
import type { PerformanceStats } from "@/types/signal"

/** GET /api/performance/me — requires auth. Returns the exact
 *  PerformanceStats shape the V2 Performance page renders. */
export async function fetchPerformanceMe(): Promise<PerformanceStats> {
  return apiGet<PerformanceStats>("/performance/me")
}
