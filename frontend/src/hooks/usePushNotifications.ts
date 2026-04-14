import { useCallback, useEffect, useState } from "react"

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || ""

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/")
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

export function usePushNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "default",
  )
  const [subscribed, setSubscribed] = useState(false)
  const [supported] = useState(
    () => "serviceWorker" in navigator && "PushManager" in window && !!VAPID_PUBLIC_KEY,
  )

  useEffect(() => {
    if (!supported) return
    navigator.serviceWorker.ready.then((reg) => {
      reg.pushManager.getSubscription().then((sub) => {
        setSubscribed(!!sub)
      })
    })
  }, [supported])

  const subscribe = useCallback(async () => {
    if (!supported) return false
    try {
      const perm = await Notification.requestPermission()
      setPermission(perm)
      if (perm !== "granted") return false

      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })

      await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sub.toJSON()),
      })

      setSubscribed(true)
      return true
    } catch {
      return false
    }
  }, [supported])

  const unsubscribe = useCallback(async () => {
    if (!supported) return
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (!sub) return

      await fetch("/api/push/unsubscribe", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sub.toJSON()),
      })

      await sub.unsubscribe()
      setSubscribed(false)
    } catch {}
  }, [supported])

  return { supported, permission, subscribed, subscribe, unsubscribe }
}
