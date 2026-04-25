import { Skeleton } from "./Skeleton"

/**
 * Generic page-level loading shell shown by `App.tsx`'s top-level
 * Suspense boundary while the route chunk downloads.
 *
 * The previous fallback was a single line of dim text ("Chargement…")
 * which gave no sense of where content would land — the screen
 * appeared frozen and the post-load reflow felt jarring. This
 * skeleton mirrors the rough vertical rhythm of every shipping page
 * (eyebrow + h1 + lede paragraph + a few content blocks) so the new
 * page paints into a familiar shape instead of from-blank.
 *
 * Inherits `prefers-reduced-motion` handling from the base Skeleton
 * (animations are killed via the global CSS reduce rule).
 */
export function PageSkeleton() {
  return (
    <div
      role="status"
      aria-label="Chargement de la page"
      className="container-page py-12 md:py-16"
    >
      {/* Eyebrow */}
      <Skeleton className="mb-3 h-3 w-24" />
      {/* H1 */}
      <Skeleton className="mb-4 h-8 w-3/4 max-w-[480px] md:h-10" />
      {/* Lede */}
      <Skeleton className="mb-10 h-4 w-full max-w-[520px]" />

      {/* A trio of content blocks — covers card grids, list views, and
          two-column layouts equally well. Heights tuned so the
          fallback never visibly shrinks the document on first paint. */}
      <div className="grid gap-4 md:grid-cols-2 md:gap-5">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32 md:col-span-2" />
      </div>
    </div>
  )
}
