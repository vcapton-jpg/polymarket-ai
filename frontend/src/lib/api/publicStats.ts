import { apiGet } from "@/lib/api/client"

/**
 * Wire shape — must match `PublicStatsOut` in
 * `app/api/routes/public_stats.py`. Fields are nullable when the DB
 * has no data yet so the UI can render an honest empty state instead
 * of a fabricated number.
 */
export type PublicStats = {
  signals_today: number
  signals_total: number
  markets_monitored: number
  active_traders_week: number
  last_signal_minutes_ago: number | null
  win_rate_1h_pct: number | null
  win_rate_sample_size: number
  win_rate_window_days: number
}

export async function fetchPublicStats(): Promise<PublicStats> {
  return apiGet<PublicStats>("/stats/public")
}
