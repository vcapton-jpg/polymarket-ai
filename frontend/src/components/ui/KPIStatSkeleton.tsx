import { Skeleton } from "@/components/ui/Skeleton"
import { cn } from "@/lib/utils"

type KPIStatSkeletonProps = {
  className?: string
  /** Render the sub-caption placeholder (matches KPIStat's `sub`). */
  withSub?: boolean
}

/**
 * Geometry-matched placeholder for <KPIStat />. Same padding / border /
 * rounded-2xl surface so the count-up value animates in without shift.
 */
export function KPIStatSkeleton({ className, withSub = true }: KPIStatSkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn(
        "relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm px-5 py-4",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <Skeleton className="h-2.5 w-20" />
        <Skeleton className="h-3.5 w-3.5 rounded" />
      </div>
      <Skeleton className="h-8 w-28" />
      {withSub && <Skeleton className="mt-2 h-3 w-24" />}
    </div>
  )
}
