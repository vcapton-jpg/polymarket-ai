import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"

/**
 * Global offline indicator. Shows a red-tinted fixed banner at the very
 * top of the viewport when `navigator.onLine === false`. Auto-hides when
 * connectivity returns. Not dismissable — the banner disappearing is the
 * confirmation that the connection is back.
 */
export function OfflineBanner() {
  const [online, setOnline] = useState<boolean>(() => {
    if (typeof navigator === "undefined") return true
    return navigator.onLine
  })

  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener("online", on)
    window.addEventListener("offline", off)
    return () => {
      window.removeEventListener("online", on)
      window.removeEventListener("offline", off)
    }
  }, [])

  if (online) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 top-0 z-[70] flex items-center justify-center gap-2 border-b border-signal-no/40 bg-signal-no/15 px-4 py-2 text-label-sm font-medium text-signal-no backdrop-blur-xl"
      style={{ maxHeight: 56 }}
    >
      <WifiOff className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>Connexion perdue — les signaux ne se rafraîchissent plus.</span>
    </div>
  )
}
