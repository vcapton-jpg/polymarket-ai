import { Skeleton } from "@/components/ui/Skeleton"
import { cn } from "@/lib/utils"

type SignalCardSkeletonProps = {
  className?: string
}

/**
 * Geometry-matched placeholder for <SignalCard variant="default" />.
 * Mirrors the rounded-2xl frame, big score tile, title lines, sub-metric
 * grid, catalyst block, and footer row so the reflow on hydration is
 * imperceptible.
 */
export function SignalCardSkeleton({ className }: SignalCardSkeletonProps) {
  return (
    <article
      aria-hidden
      className={cn(
        "relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm",
        className,
      )}
    >
      {/* Left accent rail */}
      <div className="absolute left-0 top-0 h-full w-[3px] bg-line-strong/60" />

      <div className="relative px-5 py-4 md:px-6 md:py-5">
        {/* Top: category pill + time */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="h-3 w-14" />
        </div>

        {/* Hero row: score tile + meta + market thumbnail */}
        <div className="mb-4 flex items-stretch gap-4 rounded-xl border border-line/80 bg-obsidian-800/40 px-4 py-3">
          <Skeleton className="h-[72px] min-w-[96px] rounded-lg" />
          <div className="flex flex-1 flex-col justify-center gap-2">
            <div className="flex gap-1.5">
              <Skeleton className="h-6 w-16 rounded-md" />
              <Skeleton className="h-6 w-20 rounded-md" />
            </div>
            <Skeleton className="h-3 w-40" />
          </div>
          <Skeleton className="h-16 w-16 self-center rounded-lg" />
        </div>

        {/* Question (2 lines) */}
        <div className="mb-4 space-y-2">
          <Skeleton className="h-4 w-[92%]" />
          <Skeleton className="h-4 w-[68%]" />
        </div>

        {/* Sub-metrics (3 cols) */}
        <div className="mb-4 grid grid-cols-3 gap-x-4 gap-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <Skeleton className="h-2.5 w-16" />
              <Skeleton className="h-3 w-12" />
            </div>
          ))}
        </div>

        {/* Catalyst block */}
        <div className="mb-4 rounded-lg border border-line/80 bg-obsidian-800/40 px-3.5 py-3">
          <Skeleton className="mb-2 h-2.5 w-28" />
          <Skeleton className="mb-1.5 h-3 w-full" />
          <Skeleton className="h-3 w-[82%]" />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2.5 pt-1">
          <Skeleton className="h-3 w-20" />
          <div className="flex items-center gap-1.5">
            <Skeleton className="h-8 w-8 rounded-md" />
            <Skeleton className="h-9 w-32 rounded-md" />
          </div>
        </div>
      </div>
    </article>
  )
}
