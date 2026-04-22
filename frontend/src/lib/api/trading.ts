/**
 * Trading API — order placement via Polymarket CLOB (Builder API).
 *
 * The backend validates ownership, resolves the CLOB token ID from the
 * signal's market, and submits the order. We keep this client minimal:
 * the V2 OrderForm doesn't need more than `placeTrade`.
 */

import { apiPost } from "@/lib/api/client"

export type TradeRequest = {
  /** Polymarket market ID the order should hit. */
  market_id: string
  /** YES / NO from the UI, BUY_YES / BUY_NO accepted by the legacy API. */
  direction: "YES" | "NO" | "BUY_YES" | "BUY_NO"
  /** Order size in USDC. */
  amount: number
  /** Limit price in probability space (0..1). Omit for market orders. */
  price?: number
  /** Optional: the signal the trade is acting on. Recorded on the Order
   *  row so Portfolio can join back to the V2 Signal snapshot. */
  signal_id?: number
}

export type TradeResponse = {
  success: boolean
  order_id?: number | null
  polymarket_order_id?: string | null
  error?: string | null
}

function normaliseDirection(d: TradeRequest["direction"]): "BUY_YES" | "BUY_NO" {
  if (d === "YES" || d === "BUY_YES") return "BUY_YES"
  return "BUY_NO"
}

export async function placeTrade(req: TradeRequest): Promise<TradeResponse> {
  return apiPost<TradeResponse>("/trading/trade", {
    ...req,
    direction: normaliseDirection(req.direction),
  })
}
