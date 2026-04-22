import { Skeleton } from "@/components/ui/Skeleton"
import { cn } from "@/lib/utils"

type PositionCardSkeletonProps = {
  className?: string
}

/**
 * Geometry-matched placeholder for <PositionCard />. Mirrors the accent
 * rail, category/source row, question, 3-col price grid, life bar, and
 * footer CTA so hydration swaps without layout shift.
 */
export function PositionCardSkeleton({ className }: PositionCardSkeletonProps) {
  return (
    <article
      aria-hidden
      className={cn(
        "relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm",
        className,
      )}
    >
      <div className="absolute left-0 top-0 h-full w-[3px] bg-line-strong/60" />

      <div className="relative px-5 py-4 md:px-6 md:py-5">
        {/* Top row */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-4 w-14 rounded" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-5 w-12 rounded" />
          </div>
        </div>

        {/* Question */}
        <div className="mb-4 space-y-2">
          <Skeleton className="h-4 w-[90%]" />
          <Skeleton className="h-4 w-[60%]" />
        </div>

        {/* Entry / Current / PnL row */}
        <div className="mb-4 grid grid-cols-3 gap-3 rounded-xl border border-line/80 bg-obsidian-800/40 px-4 py-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <Skeleton className="h-2.5 w-14" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-3 w-12" />
            </div>
          ))}
        </div>

        {/* Life bar */}
        <div className="mb-4 rounded-xl border border-line/70 bg-obsidian-800/30 px-4 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <Skeleton className="h-2.5 w-24" />
            <Skeleton className="h-3 w-14" />
          </div>
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2.5 pt-1">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-9 w-36 rounded-md" />
        </div>
      </div>
    </article>
  )
}
