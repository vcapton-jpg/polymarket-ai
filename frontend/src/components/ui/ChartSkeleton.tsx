import { Skeleton } from "@/components/ui/Skeleton"
import { cn } from "@/lib/utils"

type ChartSkeletonProps = {
  className?: string
  /** Chart inner height in px. Matches the 240px default of ChartCard. */
  height?: number
}

/**
 * Geometry-matched placeholder for a <ChartCard />-wrapped Recharts
 * component. Mirrors the title row + chart canvas so swap-in doesn't
 * shift layout. Honours `prefers-reduced-motion` via the base `Skeleton`.
 */
export function ChartSkeleton({ className, height = 240 }: ChartSkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-2xl border border-line-strong bg-obsidian-850/60 px-4 py-4 md:px-5 md:py-5",
        className,
      )}
    >
      <div className="mb-3 space-y-1.5">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-28" />
      </div>
      <Skeleton
        className="w-full rounded-md"
        style={{ height: `${height}px` }}
      />
    </div>
  )
}
