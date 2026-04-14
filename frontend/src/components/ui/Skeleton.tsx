export function Skeleton({ width = "100%", height = 14, className }: { width?: string | number; height?: number; className?: string }) {
  return (
    <div
      className={`rounded animate-shimmer ${className ?? ""}`}
      style={{
        width,
        height,
        background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
        backgroundSize: "200% 100%",
      }}
    />
  )
}

export function SkeletonLine({ width = "100%", height = 14 }: { width?: string | number; height?: number }) {
  return (
    <div
      className="rounded animate-shimmer"
      style={{
        width,
        height,
        background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
        backgroundSize: "200% 100%",
      }}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-surface-card rounded-lg shadow-card p-5 space-y-4">
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
