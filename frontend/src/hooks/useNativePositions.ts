/**
 * `useNativePositions` — subscribe to the `foresight.positions` localStorage
 * key written by `OrderForm` (legacy native-trading path).
 *
 * Audit follow-up 2026-05-05 (M8). Pre-PR `Portfolio.tsx` inlined the
 * read + cross-tab `storage` listener + custom-event listener
 * (`POSITIONS_CHANGED_EVENT`) + JSON shape guard, all inside one
 * 28-line `useEffect`. Three problems with that:
 *
 *   1. The bug surface was wide: deps included
 *      `activePositions.length` in a sibling useEffect that re-read
 *      positions, causing extra runs on irrelevant state changes.
 *   2. The same JSON parse + shape filter was easy to drift if a
 *      future page wanted to read positions for its own widget.
 *   3. The shape guard `isPositionLike` was duplicated in any other
 *      caller that wanted to defend against legacy / corrupted
 *      payloads (and the audit confirmed there are no other callers
 *      yet — but will be the moment a dashboard widget asks).
 *
 * The hook centralises all three concerns and returns a stable
 * `Position[]` (always an array, even on parse failure or absent key).
 * Cross-tab updates land via the standard `storage` DOM event; same-tab
 * writes land via the project's custom `POSITIONS_CHANGED_EVENT` that
 * `OrderForm` dispatches after a successful native trade.
 */

import { useEffect, useState } from "react"

import { POSITIONS_CHANGED_EVENT, STORAGE_KEYS } from "@/lib/storageKeys"
import type { Position } from "@/types/signal"

/**
 * Narrow shape guard for persisted positions. The localStorage payload
 * can drift (legacy builds, manual tampering) so reject anything that
 * doesn't look like a Position rather than blow up the page with
 * downstream TypeErrors. Exported so unit tests can pin its rules.
 */
export function isPositionLike(x: unknown): x is Position {
  if (!x || typeof x !== "object") return false
  const o = x as Record<string, unknown>
  return (
    typeof o.id === "string" &&
    typeof o.signalId === "string" &&
    typeof o.stake === "number" &&
    typeof o.entryPrice === "number"
  )
}

function readPositionsFromStorage(): Position[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.positions)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isPositionLike) : []
  } catch {
    return []
  }
}

export function useNativePositions(): Position[] {
  const [positions, setPositions] = useState<Position[]>(readPositionsFromStorage)

  useEffect(() => {
    const refresh = () => {
      setPositions(readPositionsFromStorage())
    }
    // Cross-tab updates fire `storage`; same-tab writes fire the
    // project's custom event because `storage` does NOT fire in the
    // tab that wrote the change.
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEYS.positions) refresh()
    }
    window.addEventListener("storage", onStorage)
    window.addEventListener(POSITIONS_CHANGED_EVENT, refresh)
    return () => {
      window.removeEventListener("storage", onStorage)
      window.removeEventListener(POSITIONS_CHANGED_EVENT, refresh)
    }
  }, [])

  return positions
}
