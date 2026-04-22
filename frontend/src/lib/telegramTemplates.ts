/**
 * Telegram notification templates.
 *
 * These are format-string skeletons — interpolation happens server-side
 * (Cursor). Kept here as the single source of truth for wording so copy
 * edits stay in the frontend review loop.
 */

/** Sent when a new signal is published to a Pro user. */
export const TELEGRAM_ENTRY_TEMPLATE = `🟢 Nouveau signal · Score {score}
{question}
{direction} @ {price}
Fenêtre : ~{hours} h
→ Parier sur ce marché`

/** Sent when an open position crosses the "à surveiller" or "vendre" threshold. */
export const TELEGRAM_EXIT_TEMPLATE = `🔴 Position à surveiller · {signal_id}
{question}
{reason}
→ Action recommandée : {action}`

/** Fields the backend must interpolate. */
export const TELEGRAM_ENTRY_FIELDS = [
  "score",
  "question",
  "direction",
  "price",
  "hours",
] as const

export const TELEGRAM_EXIT_FIELDS = [
  "signal_id",
  "question",
  "reason",
  "action",
] as const
