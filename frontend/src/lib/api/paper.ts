import { apiGet, apiPost } from "./client"

/**
 * Paper-trade API client.
 *
 * The backend wire format still ships an `is_tutorial` boolean — left over
 * from the L&T tutorial gate that was removed in the Apprendre/Welcome
 * pivot. The field is now informational on the server (kept for analytics
 * & older mobile builds) and is no longer exposed on the JS surface:
 * `openPaperTrade` always sends `false`, and `PaperPosition` does not
 * include the field. If a future client needs it back, re-add `isTutorial`
 * here and to the hydrate mapping rather than reading the wire blob raw.
 */

export type PaperPosition = {
  id: number
  marketId: string
  signalId: number | null
  direction: "YES" | "NO"
  stakeEur: number
  entryPrice: number
  currentPrice: number | null
  resolved: boolean
  correct: boolean | null
  pnlEur: number | null
  openedAt: string
  resolvedAt: string | null
}

type WirePaperPosition = {
  id: number
  market_id: string
  signal_id: number | null
  direction: "YES" | "NO"
  stake_eur: number
  entry_price: number
  current_price: number | null
  resolved: boolean
  correct: boolean | null
  pnl_eur: number | null
  is_tutorial: boolean
  opened_at: string
  resolved_at: string | null
}

function hydrate(w: WirePaperPosition): PaperPosition {
  return {
    id: w.id,
    marketId: w.market_id,
    signalId: w.signal_id,
    direction: w.direction,
    stakeEur: w.stake_eur,
    entryPrice: w.entry_price,
    currentPrice: w.current_price,
    resolved: w.resolved,
    correct: w.correct,
    pnlEur: w.pnl_eur,
    openedAt: w.opened_at,
    resolvedAt: w.resolved_at,
  }
}

export async function openPaperTrade(input: {
  marketId: string
  signalId?: number | null
  direction: "YES" | "NO"
  stakeEur: number
  entryPrice: number
}): Promise<PaperPosition> {
  const wire = await apiPost<WirePaperPosition>("/paper/trade", {
    market_id: input.marketId,
    signal_id: input.signalId ?? null,
    direction: input.direction,
    stake_eur: input.stakeEur,
    entry_price: input.entryPrice,
    is_tutorial: false,
  })
  return hydrate(wire)
}

export async function fetchPaperPositions(): Promise<PaperPosition[]> {
  const r = await apiGet<{ items: WirePaperPosition[] }>("/paper/positions")
  return r.items.map(hydrate)
}
