import { useEffect, useState } from "react"
import type { PositionStatus } from "@/types/signal"

/** Decay rate in percent per second — slow enough to feel "alive" without distracting. */
const DECAY_PER_SECOND = 0.05

export function statusFromLifePercent(percent: number): PositionStatus {
  if (percent >= 50) return "tenir"
  if (percent >= 20) return "surveiller"
  return "vendre"
}

/**
 * Decay hook — starts from initial percent and ticks down at DECAY_PER_SECOND.
 * Respects prefers-reduced-motion: users who disable animations see a static bar.
 */
export function useLifeDecay(initial: number, paused = false): number {
  const [percent, setPercent] = useState(initial)

  useEffect(() => {
    if (paused) return

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    if (reduced) return

    const id = setInterval(() => {
      setPercent((p) => Math.max(0, p - DECAY_PER_SECOND))
    }, 1000)
    return () => clearInterval(id)
  }, [paused])

  return percent
}

/** Compute approximate minutes remaining given current life % and total window hours. */
export function minutesRemaining(percent: number, windowHours: number): number {
  return Math.max(0, Math.round((percent / 100) * windowHours * 60))
}

export function formatMinutesRemaining(mins: number): string {
  if (mins <= 0) return "fenêtre fermée"
  if (mins < 60) return `~${mins} min`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m === 0 ? `~${h}h` : `~${h}h${m.toString().padStart(2, "0")}`
}
