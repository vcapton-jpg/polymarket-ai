/**
 * Polymarket Builder Program integration — URL building.
 *
 * The Builder Program attributes trade volume routed through our UI back to
 * Foresight. We pass our builder code as a query param on every outbound
 * Polymarket URL. Cursor wires the real code via `VITE_POLYMARKET_BUILDER_CODE`
 * at build time; without it we fall back to `"foresight"` so the link works in
 * local dev.
 *
 * Keep all referral params here so we have a single choke point to audit.
 */

/** Builder code injected at build time via Vite. Falls back to `"foresight"`
 *  for local dev; the real code comes from the Polymarket dashboard. */
export const POLYMARKET_BUILDER_CODE: string =
  (import.meta.env.VITE_POLYMARKET_BUILDER_CODE as string | undefined) ??
  "foresight"

/**
 * Append our referral / builder code to a Polymarket market URL, preserving
 * any existing query string. Never throws — if the URL is malformed we return
 * it unchanged so the link still works.
 */
export function withBuilderCode(polymarketUrl: string): string {
  if (!polymarketUrl) return polymarketUrl
  try {
    const u = new URL(polymarketUrl)
    // Only inject for polymarket.com — never risk leaking the code elsewhere.
    if (!u.hostname.endsWith("polymarket.com")) return polymarketUrl
    if (!u.searchParams.has("referralCode")) {
      u.searchParams.set("referralCode", POLYMARKET_BUILDER_CODE)
    }
    return u.toString()
  } catch {
    return polymarketUrl
  }
}
