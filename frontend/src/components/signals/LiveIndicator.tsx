import { Wifi, WifiOff } from "lucide-react"
import { timeAgo } from "../../lib/utils"

interface Props {
  connected: boolean
  lastUpdate?: Date
}

export function LiveIndicator({ connected, lastUpdate }: Props) {
  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-lg bg-surface-card shadow-card text-xs">
      {connected ? (
        <>
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-50" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
          </span>
          <span className="font-semibold text-success">LIVE</span>
          {lastUpdate && <span className="text-txt-muted">{timeAgo(lastUpdate)} ago</span>}
        </>
      ) : (
        <>
          <WifiOff size={12} className="text-danger" />
          <span className="font-semibold text-danger">OFFLINE</span>
        </>
      )}
    </div>
  )
}
