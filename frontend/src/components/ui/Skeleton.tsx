import { cn } from "@/lib/utils"

type SkeletonProps = {
  className?: string
  /** Accessible label; defaults to "Chargement". */
  label?: string
} & React.HTMLAttributes<HTMLDivElement>

/**
 * Base shimmer block. Composes two divs:
 *   1. an outer clipped surface painted with the obsidian token palette,
 *   2. an inner gradient sweep driven by the `animate-shimmer` keyframe
 *      declared in tailwind.config.ts.
 *
 * `prefers-reduced-motion` is honoured globally via `globals.css`, which
 * neutralises all animations under the reduce query — no JS branching needed.
 */
export function Skeleton({ className, label = "Chargement", ...rest }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-label={label}
      aria-busy="true"
      className={cn(
        "relative overflow-hidden rounded-md bg-obsidian-800",
        className,
      )}
      {...rest}
    >
      <div
        aria-hidden
        className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/5 to-transparent"
      />
    </div>
  )
}
