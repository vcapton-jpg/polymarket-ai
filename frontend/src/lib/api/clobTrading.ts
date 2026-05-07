/**
 * Non-custodial CLOB trading API helpers.
 *
 * Companion to `useClobClient` — those are the BACKEND calls (token_ids
 * lookup + order persistence) that bracket the user's MetaMask signing.
 *
 * Flow consumed by `OrderForm.tsx`:
 *
 *   1. fetchClobMarketInfo(market_id)
 *      ─▶ GET /api/trading/markets/{id}/clob-info
 *      ─▶ returns YES/NO token_id + tick_size + neg_risk
 *   2. clobClient.createAndPostOrder(orderArgs, options, GTC|FOK)
 *      ─▶ MetaMask signs EIP-712
 *      ─▶ posted directly to clob.polymarket.com (with our HMAC builder
 *         headers via /api/polymarket/sign)
 *   3. recordOrder({...})
 *      ─▶ POST /api/trading/orders/record
 *      ─▶ persists Order row so portfolio + worker poll see it
 *
 * The OrderForm should treat each step as can-fail and surface the real
 * error to the user (no more silent "ordre en local uniquement" with a
 * fictional position in localStorage).
 */
import { apiGet, apiPost } from "./client"

// ─── /api/trading/markets/{id}/clob-info ────────────────────────────────────

export type ClobMarketInfo = {
  market_id: string
  yes_token_id: string | null
  no_token_id: string | null
  tick_size: string
  neg_risk: boolean
  last_trade_price: number | null
  accepting_orders: boolean
}

export async function fetchClobMarketInfo(market_id: string): Promise<ClobMarketInfo> {
  return apiGet<ClobMarketInfo>(
    `/trading/markets/${encodeURIComponent(market_id)}/clob-info`,
  )
}

// ─── /api/trading/orders/record ─────────────────────────────────────────────

export type OrderRecordPayload = {
  market_id: string
  polymarket_order_id: string
  direction: "YES" | "NO" | "BUY_YES" | "BUY_NO"
  token_id: string
  size: number
  price: number
  /** Order type returned by clob-client (GTC for limit, FOK for market). */
  order_type?: "GTC" | "FOK" | "GTD" | "FAK"
  signal_id?: number | null
}

export type OrderRecordResponse = {
  success: boolean
  order_id: number | null
  error: string | null
}

export async function recordOrder(
  payload: OrderRecordPayload,
): Promise<OrderRecordResponse> {
  return apiPost<OrderRecordResponse>("/trading/orders/record", payload)
}
