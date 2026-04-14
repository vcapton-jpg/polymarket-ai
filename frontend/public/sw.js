const CACHE_NAME = "signal-v1"
const PRECACHE = ["/", "/dashboard", "/icon.svg"]

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()),
  )
})

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener("fetch", (e) => {
  if (e.request.url.includes("/api/") || e.request.url.includes("/ws")) return

  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok && e.request.method === "GET") {
          const clone = res.clone()
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone))
        }
        return res
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/"))),
  )
})

self.addEventListener("push", (e) => {
  let data = { title: "Signal", body: "New signal available" }
  try {
    if (e.data) data = e.data.json()
  } catch {}

  e.waitUntil(
    self.registration.showNotification(data.title || "Signal", {
      body: data.body || "New signal available",
      icon: "/icon.svg",
      badge: "/icon.svg",
      tag: data.tag || "signal-" + Date.now(),
      data: { url: data.url || "/dashboard" },
      vibrate: [200, 100, 200],
    }),
  )
})

self.addEventListener("notificationclick", (e) => {
  e.notification.close()
  const url = e.notification.data?.url || "/dashboard"
  e.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && "focus" in client) return client.focus()
      }
      return self.clients.openWindow(url)
    }),
  )
})
