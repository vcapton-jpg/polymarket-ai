import { useCallback, useEffect, useState } from "react"
import type { Position } from "@/types/signal"
import {
  MANUAL_POSITIONS_STORAGE_KEY,
  readManualPositions,
  removeManualPosition as removeRaw,
} from "./manualPositions"

/**
 * React hook exposing the manual-entry positions from localStorage.
 *
 * Reactively syncs across tabs via the `storage` event so Portfolio stays
 * up to date when a user saves a position from a SignalDetail modal.
 */
export function useManualPositions(): {
  positions: Position[]
  refresh: () => void
  remove: (id: string) => void
} {
  const [positions, setPositions] = useState<Position[]>(() => readManualPositions())

  const refresh = useCallback(() => {
    setPositions(readManualPositions())
  }, [])

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === MANUAL_POSITIONS_STORAGE_KEY) refresh()
    }
    // Cross-tab signal
    window.addEventListener("storage", onStorage)
    // Same-tab signal: we dispatch a custom event in addManualPosition callers.
    window.addEventListener("foresight:manual-positions-changed", refresh)
    return () => {
      window.removeEventListener("storage", onStorage)
      window.removeEventListener("foresight:manual-positions-changed", refresh)
    }
  }, [refresh])

  const remove = useCallback(
    (id: string) => {
      removeRaw(id)
      setPositions(readManualPositions())
      window.dispatchEvent(new Event("foresight:manual-positions-changed"))
    },
    [],
  )

  return { positions, refresh, remove }
}
