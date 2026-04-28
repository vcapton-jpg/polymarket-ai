/**
 * Number-formatting helper used across marketing surfaces.
 *
 * The hardcoded `PUBLIC_STATS` constant that used to live here was
 * removed in Legal-PR-3 (audit finding B8 + H1). All numbers visible
 * to a marketing visitor now come from the live backend via
 * `usePublicStats()` so AMF / DGCCRF can never catch us advertising
 * figures that don't match the database. See
 * `frontend/src/hooks/usePublicStats.ts` and the
 * `GET /api/stats/public` endpoint.
 */

/** Format a number with French thin-space thousand separator. */
export function formatStat(n: number): string {
  return n.toLocaleString("fr-FR").replace(/ /g, " ")
}

/** Placeholder rendered when the backend legitimately reports 0 or
 *  null for a marketing stat (fresh DB / beta phase). Centralised so
 *  every consumer renders the same glyph. */
export const EMPTY_STAT_PLACEHOLDER = "—"
