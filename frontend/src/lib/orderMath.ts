/**
 * Order-form math, extracted as pure functions so the numbers can be
 * unit-tested without mounting React. When Cursor wires the Polymarket CLOB
 * client, these functions are the contract the UI will keep rendering —
 * replace the mocks, not the math.
 *
 * All amounts are in USDC (notional), prices are [0, 1] probabilities.
 */

export const MIN_AMOUNT = 1
export const MAX_AMOUNT = 10_000
/** Approximate USD→EUR rate used for sizing hints. Display-only. */
export const USD_TO_EUR = 0.92

export type OrderMath = {
  /** Number of shares the stake buys at the current price. */
  shares: number
  /** Pay-off relative to stake if the position resolves in favour. */
  estimatedReturn: number
  /** Max downside — the user loses the full stake. */
  maxLoss: number
  /** True iff the market is tradeable (price strictly inside (0,1)). */
  marketTradeable: boolean
}

/**
 * Pure order math. Degenerate markets (price 0 or 1) return shares=0,
 * estimatedReturn=0, and flip marketTradeable=false so the UI can refuse
 * to submit. Non-finite or negative inputs are clamped to zero.
 */
export function computeOrderMath(amount: number, pricePerShare: number): OrderMath {
  const safeAmount = Number.isFinite(amount) && amount > 0 ? amount : 0
  const safePrice = Number.isFinite(pricePerShare) ? pricePerShare : 0
  const marketTradeable = safePrice > 0 && safePrice < 1
  if (!marketTradeable || safeAmount === 0) {
    return {
      shares: 0,
      estimatedReturn: 0,
      maxLoss: safeAmount,
      marketTradeable,
    }
  }
  const shares = safeAmount / safePrice
  // Each winning share pays $1, minus the stake already paid.
  const estimatedReturn = shares - safeAmount
  return {
    shares,
    estimatedReturn,
    maxLoss: safeAmount,
    marketTradeable,
  }
}

/** True iff the stake passes the min/max invariant. */
export function isAmountValid(amount: number): boolean {
  return (
    Number.isFinite(amount) &&
    amount >= MIN_AMOUNT &&
    amount <= MAX_AMOUNT
  )
}

/** Sanitize a raw input string into a non-negative number without
 *  coercing empty string to zero. Returns `null` for empty. */
export function parseAmountInput(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === "") return null
  const n = Number(trimmed)
  return Number.isFinite(n) && n >= 0 ? n : null
}
