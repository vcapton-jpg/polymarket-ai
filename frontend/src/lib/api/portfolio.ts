/**
 * Portfolio API — thin wrapper over /api/portfolio.
 *
 * The backend returns the V2 Position shape directly (camelCase), so this
 * module only adds `source: "native"` in case the server response omits it
 * and normalises the `entryDate` string into a Date in the UI layer
 * elsewhere.
 */

import { apiGet } from "@/lib/api/client"
import type { Position } from "@/types/signal"

export type PortfolioKpis = {
  total_positions: number
  active_positions: number
  resolved_positions: number
  total_stake: number
  total_estimated_gain: number
}

export type RemotePortfolio = {
  positions: Position[]
  resolved: Position[]
  kpis: PortfolioKpis
}

/** Raw wire shape — `signal` carries camelCase V2 Signal fields, and
 *  `entryDate` is an ISO string (converted to Date by `fetchPortfolio`). */
type WirePosition = Omit<Position, "entryDate" | "source"> & {
  entryDate: string
  source?: "native" | "manual"
}

type WirePortfolio = {
  positions: WirePosition[]
  resolved: WirePosition[]
  kpis: PortfolioKpis
}

function hydrate(p: WirePosition): Position {
  return {
    ...p,
    entryDate: p.entryDate, // Position.entryDate is typed as string in V2
    source: p.source ?? "native",
  } as Position
}

export async function fetchPortfolio(): Promise<RemotePortfolio> {
  const raw = await apiGet<WirePortfolio>("/portfolio")
  return {
    positions: raw.positions.map(hydrate),
    resolved: raw.resolved.map(hydrate),
    kpis: raw.kpis,
  }
}
