/**
 * Signals API — thin passthrough to FastAPI `/signals` endpoints.
 *
 * The backend serves the V2 shape natively (see `app/api/signal_mapper.py`)
 * so this module does zero transformation: fetch + JSON, typed as
 * `Signal`.
 */

import { apiGet } from "@/lib/api/client"
import type { Signal } from "@/types/signal"

export type SignalListResponse = { signals: Signal[]; total: number }

export async function fetchSignalsFromApi(params?: {
  limit?: number
  offset?: number
  /** 0–100 — filter out below. */
  min_score?: number
  /** "YES" | "NO" (the API also accepts legacy BUY_YES/BUY_NO). */
  direction?: string
  /** V2 category — forwarded as `category=` query param. */
  category?: string
}): Promise<SignalListResponse> {
  const q = new URLSearchParams()
  if (params?.limit != null) q.set("limit", String(params.limit))
  if (params?.offset != null) q.set("offset", String(params.offset))
  if (params?.min_score != null) q.set("min_score", String(params.min_score))
  if (params?.direction) q.set("direction", params.direction)
  if (params?.category) q.set("category", params.category)
  const qs = q.toString()
  return apiGet<SignalListResponse>(`/signals${qs ? `?${qs}` : ""}`)
}

export async function fetchSignalDetailFromApi(id: string | number): Promise<Signal> {
  return apiGet<Signal>(`/signals/${id}`)
}
