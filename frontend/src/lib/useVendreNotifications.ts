import { useEffect } from "react"
import { MOCK_POSITIONS } from "@/data/positions"
import { useManualPositions } from "./useManualPositions"
import {
  markAlerted,
  readAlertedIds,
  sendVendreBrowserNotification,
} from "./notifications"
import { useToasts } from "./useToasts"

/**
 * Watches all active positions and fires "vendre" alerts on transitions.
 *
 * For every position whose status is "vendre" and whose id is NOT in the
 * localStorage `alerted` set, we fire two alerts in parallel:
 *  1. A browser notification (only if user has opted in via Settings).
 *  2. An in-app toast simulating the Telegram bot push.
 *
 * After firing, the position id is added to the alerted set so we never
 * re-notify across page refreshes. The set is scoped per-device on purpose:
 * if the user opens Foresight on another device, they'll get the alert
 * again there, which matches how a real Telegram bot push would behave
 * (delivered per-session-device).
 *
 * Mounted at AppShell level so alerts work regardless of current page.
 */
export function useVendreNotifications(): void {
  const { positions: manualPositions } = useManualPositions()
  const { addToast } = useToasts()

  useEffect(() => {
    // Combine both sources: the baseline mocks plus anything the user has
    // saved manually via the SignalDetail modal.
    const all = [...MOCK_POSITIONS, ...manualPositions]

    const vendrePositions = all.filter(
      (p) => !p.resolved && p.status === "vendre",
    )
    if (vendrePositions.length === 0) return

    const alerted = readAlertedIds()
    const newlyVendre = vendrePositions.filter((p) => !alerted.has(p.id))
    if (newlyVendre.length === 0) return

    // Mark first to make this idempotent — if the browser notif or the
    // toast throws for some reason, we still don't re-alert on next render.
    markAlerted(newlyVendre.map((p) => p.id))

    newlyVendre.forEach((position) => {
      sendVendreBrowserNotification({
        question: position.signal.question,
        estimatedGain: position.estimatedGain,
      })

      addToast({
        type: "telegram",
        title: "Alerte Telegram envoyée",
        description: `Signal vendre sur "${truncate(position.signal.question, 64)}"`,
        duration: 6000,
      })
    })
  }, [manualPositions, addToast])
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max - 1).trimEnd() + "…"
}
