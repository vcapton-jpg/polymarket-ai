/**
 * Currency formatting for Foresight V2.
 *
 * Money in the state is always stored in USD (Polymarket trades in USDC).
 * This helper converts + formats at display time based on the user's choice.
 *
 * Mocked exchange rate: 1 USD = 0.92 EUR.
 * Real FX API is a backend concern (Cursor will wire it later).
 */

export type Currency = "USD" | "EUR"

export const SUPPORTED_CURRENCIES: readonly Currency[] = ["USD", "EUR"] as const

export const MOCK_EXCHANGE_RATE_USD_TO_EUR = 0.92

export function isCurrency(v: unknown): v is Currency {
  return v === "USD" || v === "EUR"
}

export function convertFromUSD(amountUSD: number, to: Currency, rate = MOCK_EXCHANGE_RATE_USD_TO_EUR): number {
  return to === "USD" ? amountUSD : amountUSD * rate
}

type FormatOptions = {
  /** Always include the +/- sign even when positive. Useful for P&L. */
  signed?: boolean
  /** Decimals (default: 0 for round amounts, 2 if fractional). */
  decimals?: number
  /** Exchange rate override — defaults to MOCK_EXCHANGE_RATE_USD_TO_EUR. */
  rate?: number
  /** Locale for number separators — defaults to "fr-FR". */
  locale?: string
}

/**
 * Format a USD amount for display in the user's chosen currency.
 *
 * @example
 * formatCurrency(50, "USD")           // "$50"
 * formatCurrency(50, "EUR")           // "€46"
 * formatCurrency(-12, "USD", { signed: true }) // "−$12"
 * formatCurrency(47, "USD", { signed: true })  // "+$47"
 */
export function formatCurrency(amountUSD: number, currency: Currency, opts: FormatOptions = {}): string {
  const { signed = false, decimals, rate = MOCK_EXCHANGE_RATE_USD_TO_EUR, locale = "fr-FR" } = opts

  const converted = convertFromUSD(amountUSD, currency, rate)
  const isNegative = converted < 0
  const abs = Math.abs(converted)

  const inferredDecimals = decimals ?? (Number.isInteger(abs) ? 0 : 2)
  const formatted = abs.toLocaleString(locale, {
    minimumFractionDigits: inferredDecimals,
    maximumFractionDigits: inferredDecimals,
  })

  const symbol = currency === "USD" ? "$" : "€"
  const sign = isNegative ? "−" : signed ? "+" : ""

  return `${sign}${symbol}${formatted}`
}

export function currencySymbol(currency: Currency): string {
  return currency === "USD" ? "$" : "€"
}
