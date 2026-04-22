/**
 * Browser Notifications + Telegram simulation for "vendre" status alerts.
 *
 * When a position's status transitions to "vendre" (sell recommendation),
 * we fire two parallel alerts:
 *  1. A Web Notification via the browser Notification API — only if the
 *     user has explicitly opted in via Settings → Push navigateur.
 *  2. An in-app toast ("Alerte Telegram envoyée") to simulate the Telegram
 *     bot push. The real Telegram integration is a backend concern wired
 *     later; the UI contract is stable regardless.
 *
 * The "alerted" set in localStorage prevents re-notifying for positions
 * we've already alerted on — so page refreshes don't spam the user.
 */

const ALERTED_KEY = "foresight.notifications.alertedVendre"
const SETTINGS_KEY = "foresight.settings"

export function getNotificationPermission(): NotificationPermission {
  if (typeof window === "undefined" || !("Notification" in window)) return "denied"
  return Notification.permission
}

export function supportsNotifications(): boolean {
  return typeof window !== "undefined" && "Notification" in window
}

export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (!supportsNotifications()) return "denied"
  if (Notification.permission === "granted") return "granted"
  try {
    return await Notification.requestPermission()
  } catch {
    return "denied"
  }
}

/**
 * Reads the `pushNotif` preference persisted by the Settings page.
 * Treats any parse error as "disabled" — we never fire notifications
 * unless the user has explicitly opted in.
 */
export function readPushEnabled(): boolean {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return false
    const parsed = JSON.parse(raw)
    return Boolean(parsed?.pushNotif)
  } catch {
    return false
  }
}

export function readAlertedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(ALERTED_KEY)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return new Set(Array.isArray(arr) ? (arr as string[]) : [])
  } catch {
    return new Set()
  }
}

export function markAlerted(ids: string[]): void {
  if (ids.length === 0) return
  try {
    const current = readAlertedIds()
    ids.forEach((id) => current.add(id))
    localStorage.setItem(ALERTED_KEY, JSON.stringify(Array.from(current)))
  } catch {
    // ignore quota / disabled-storage edge cases
  }
}

/** Clears the alerted set (used by dev/test — not wired into UI). */
export function clearAlerted(): void {
  try {
    localStorage.removeItem(ALERTED_KEY)
  } catch {
    // ignore
  }
}

type VendreNotifParams = {
  question: string
  estimatedGain: number
}

/**
 * Fires a browser Notification for a "vendre" recommendation.
 * No-op unless the user has both granted permission AND enabled pushNotif.
 */
export function sendVendreBrowserNotification(params: VendreNotifParams): void {
  if (!supportsNotifications()) return
  if (getNotificationPermission() !== "granted") return
  if (!readPushEnabled()) return

  const gainSign = params.estimatedGain >= 0 ? "+" : ""
  try {
    new Notification("Signal vendre · Foresight", {
      body: `${params.question}\nGain estimé : ${gainSign}${params.estimatedGain.toFixed(0)} $`,
      tag: `foresight-vendre-${params.question.slice(0, 40)}`,
      requireInteraction: false,
    })
  } catch {
    // Notification constructor can throw in some Safari edge cases — swallow.
  }
}
