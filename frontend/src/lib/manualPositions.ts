import type { Position, Signal } from "@/types/signal"

export const MANUAL_POSITIONS_STORAGE_KEY = "foresight.manualPositions"

/**
 * Draft of a manually-entered position before persistence.
 * User fills this in the ManualPositionModal after trading on Polymarket
 * directly, so Foresight can still track it in their portfolio.
 */
export type ManualPositionInput = {
  signalId: string
  direction: "YES" | "NO"
  stake: number
  entryPrice: number
  /** ISO string. Optional — defaults to now. */
  entryDate?: string
}

/** Read all manual positions from localStorage. Safe in SSR (returns []). */
export function readManualPositions(): Position[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(MANUAL_POSITIONS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Position[]) : []
  } catch {
    return []
  }
}

function writeManualPositions(positions: Position[]): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      MANUAL_POSITIONS_STORAGE_KEY,
      JSON.stringify(positions),
    )
    // Same-tab broadcast for subscribers like useManualPositions().
    window.dispatchEvent(new Event("foresight:manual-positions-changed"))
  } catch {
    // quota exceeded or disabled — silently ignore, user-facing UX remains intact
  }
}

/**
 * Build a Position from a ManualPositionInput + the referenced signal.
 * For a freshly-entered position we assume the current price equals the
 * entry price (flat gain), status="tenir", lifePercent copied from the signal.
 */
export function buildManualPosition(
  input: ManualPositionInput,
  signal: Signal,
): Position {
  const entryDate = input.entryDate ?? new Date().toISOString()
  const id = `POS-M-${Date.now().toString(36).toUpperCase()}`
  return {
    id,
    signalId: signal.id,
    signal,
    direction: input.direction,
    entryPrice: input.entryPrice,
    currentPrice: input.entryPrice,
    entryDate,
    status: "tenir",
    lifePercent: signal.lifePercent,
    estimatedGain: 0,
    stake: input.stake,
    resolved: false,
    correctPrediction: null,
    source: "manual",
  }
}

export function addManualPosition(
  input: ManualPositionInput,
  signal: Signal,
): Position {
  const position = buildManualPosition(input, signal)
  const all = readManualPositions()
  all.unshift(position)
  writeManualPositions(all)
  return position
}

export function removeManualPosition(id: string): void {
  const all = readManualPositions().filter((p) => p.id !== id)
  writeManualPositions(all)
}
