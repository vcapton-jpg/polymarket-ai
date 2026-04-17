import { cn } from "../../lib/utils"

const SHIMMER_GOLD =
  "linear-gradient(90deg, rgba(212,160,23,0.04) 25%, rgba(212,160,23,0.08) 50%, rgba(212,160,23,0.04) 75%)"

export function Skeleton({
  width = "100%",
  height = 14,
  className,
}: {
  width?: string | number
  height?: number
  className?: string
}) {
  return (
    <div
      className={cn("rounded-md animate-shimmer-gold", className)}
      style={{
        width,
        height,
        background: SHIMMER_GOLD,
        backgroundSize: "200% 100%",
      }}
    />
  )
}

export function SkeletonLine({ width = "100%", height = 14 }: { width?: string | number; height?: number }) {
  return (
    <div
      className="rounded-md animate-shimmer-gold"
      style={{
        width,
        height,
        background: SHIMMER_GOLD,
        backgroundSize: "200% 100%",
      }}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="glass-card rounded-xl shadow-card p-5 space-y-4 border border-edge-subtle">
      <div className="flex items-center justify-between">
        <SkeletonLine width={80} height={20} />
        <SkeletonLine width={60} height={20} />
      </div>
      <SkeletonLine width="75%" height={16} />
      <SkeletonLine width="100%" height={10} />
      <div className="flex items-center justify-between pt-1">
        <SkeletonLine width={120} height={12} />
        <SkeletonLine width={60} height={12} />
      </div>
    </div>
  )
}
