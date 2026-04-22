/**
 * French typography helpers.
 *
 * Centralizes French-specific formatting so EN locales can plug their own
 * formatters later (via a simple locale switch in useUserPreferences).
 */

// Standard French typographic characters
export const NBSP = "\u00A0"          // espace insécable (before : ? ! ; and in number+unit)
export const NNBSP = "\u202F"         // narrow no-break space (thousands separator, some typographers)
export const CURLY_APOSTROPHE = "\u2019"  // ’
export const EN_DASH = "\u2013"       // – for ranges
export const EM_DASH = "\u2014"       // — for parentheticals
export const GUILLEMET_OPEN = "\u00AB"   // «
export const GUILLEMET_CLOSE = "\u00BB"  // »

/** Format an integer with French thin-space thousand grouping. "61247" → "61 247". */
export function formatFR(n: number): string {
  return n.toLocaleString("fr-FR").replace(/\u202F/g, NBSP)
}

/** Format "value + unit" with a non-breaking space. "68, s" → "68 s" (NBSP inside). */
export function formatFRUnit(value: number | string, unit: string): string {
  return `${value}${NBSP}${unit}`
}

/** Wrap a quoted term in French guillemets with internal NBSP. "vendre" → "« vendre »". */
export function guillemets(term: string): string {
  return `${GUILLEMET_OPEN}${NBSP}${term}${NBSP}${GUILLEMET_CLOSE}`
}

/** Format a currency amount in French: "29 €" (NBSP before symbol), "1 188 €" etc. */
export function formatFRCurrency(amount: number, symbol: string = "€"): string {
  return `${formatFR(amount)}${NBSP}${symbol}`
}

/** Format a numeric range in French: "50–200 €". */
export function formatFRRange(min: number, max: number, unit: string = ""): string {
  const core = `${formatFR(min)}${EN_DASH}${formatFR(max)}`
  return unit ? `${core}${NBSP}${unit}` : core
}
