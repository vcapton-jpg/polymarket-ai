import { useEffect, useRef, useState, useCallback } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "../lib/api"
import type { Signal } from "../lib/types"

const MAX_RECONNECT_DELAY = 30_000
const INITIAL_RECONNECT_DELAY = 2_000
const MAX_RECONNECT_ATTEMPTS = 50

export function useWebSocket() {
  const [liveSignals, setLiveSignals] = useState<Signal[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const reconnectAttempts = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/signals`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        reconnectAttempts.current = 0
      }

      ws.onclose = () => {
        setConnected(false)
        if (unmountedRef.current) return
        if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) return

        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts.current),
          MAX_RECONNECT_DELAY,
        )
        reconnectAttempts.current += 1
        reconnectTimer.current = setTimeout(connect, delay)
      }

      ws.onerror = () => ws.close()

      ws.onmessage = (e) => {
        try {
          const signal: Signal = JSON.parse(e.data)
          if (!signal.id) return
          setLiveSignals((prev) => [signal, ...prev].slice(0, 50))
          queryClient.invalidateQueries({ queryKey: ["signals"] })
          queryClient.invalidateQueries({ queryKey: queryKeys.accuracy })
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboardKpis })
        } catch {
          /* skip non-json heartbeats */
        }
      }
    } catch {
      /* WebSocket constructor can throw if URL is invalid */
    }
  }, [queryClient])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { liveSignals, connected }
}
