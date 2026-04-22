import type { ReactNode } from "react"
import type { ProfileLevel } from "@/lib/useProfile"

export type LearnContentBlocks = {
  /** Baseline — shown when no level-specific override applies. */
  standard: ReactNode
  /** Découvreur — simpler, more visuals, friendlier examples. */
  discoverer?: ReactNode
  /** Confirmé — technical appendix appended after standard. */
  expert?: ReactNode
}

type LearnContentProps = {
  level: ProfileLevel
  content: LearnContentBlocks
  /**
   * Optional experience-derived depth. When provided and equal to "expert",
   * the expert appendix is shown even if the user's `type` is not
   * "Confirmé" — experience > type for pedagogical depth. When "beginner",
   * the discoverer variant is preferred. "intermediate" (default) yields
   * the standard resolution rules.
   */
  depth?: "beginner" | "intermediate" | "expert"
}

/**
 * Renders learn content keyed on the user’s profile level.
 *
 * Resolution rules:
 * - "Découvreur" replaces standard when `content.discoverer` is provided,
 *   otherwise falls back to standard. This matches the spec
 *   (README-V2 lines 682-686): simpler tone for beginners.
 * - "Actif" always renders standard — the neutral default.
 * - "Confirmé" renders standard AND the expert appendix when provided.
 *   The appendix is additive (never a replacement) because experts still
 *   benefit from the narrative framing before the technical detail.
 */
export function LearnContent({ level, content, depth }: LearnContentProps) {
  // Experience-based depth overrides type-based resolution when explicit.
  if (depth === "beginner") {
    return <>{content.discoverer ?? content.standard}</>
  }
  if (depth === "expert") {
    return (
      <>
        {content.standard}
        {content.expert}
      </>
    )
  }
  if (level === "Découvreur") {
    return <>{content.discoverer ?? content.standard}</>
  }
  if (level === "Confirmé") {
    return (
      <>
        {content.standard}
        {content.expert}
      </>
    )
  }
  return <>{content.standard}</>
}
