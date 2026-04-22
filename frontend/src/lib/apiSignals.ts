import type { ApiSignalDetail, ApiSignalRow } from "@/lib/mapApiSignal"
import { mapApiDetailToSignal, mapApiRowToSignal } from "@/lib/mapApiSignal"
import type { Signal } from "@/types/signal"

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "/api"

async function getJson<T>(path: string): Promise<T> {
  const url = path.startsWith("http") ? path : `${BASE}${path.startsWith("/") ? path : `/${path}`}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export type SignalsListPayload = { signals: ApiSignalRow[]; total: number }

export async function fetchSignalsFromApi(params?: {
  limit?: number
  offset?: number
  min_score?: number
  direction?: string
}): Promise<{ signals: Signal[]; total: number }> {
  const q = new URLSearchParams()
  if (params?.limit != null) q.set("limit", String(params.limit))
  if (params?.offset != null) q.set("offset", String(params.offset))
  if (params?.min_score != null) q.set("min_score", String(params.min_score))
  if (params?.direction) q.set("direction", params.direction)
  const qs = q.toString()
  const data = await getJson<SignalsListPayload>(`/signals${qs ? `?${qs}` : ""}`)
  return {
    signals: data.signals.map(mapApiRowToSignal),
    total: data.total,
  }
}

export async function fetchSignalDetailFromApi(id: number): Promise<Signal> {
  const row = await getJson<ApiSignalDetail>(`/signals/${id}`)
  return mapApiDetailToSignal(row)
}
