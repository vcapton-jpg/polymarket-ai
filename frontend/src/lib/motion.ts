import { useReducedMotion } from "framer-motion"

/**
 * Foresight motion system.
 *
 * Single source of truth for easing curves, durations, and stagger rhythms.
 * Every `motion.*` component should import from here — no raw
 * `[0.22, 1, 0.36, 1]` literals, no magic 0.4s durations.
 */

export const EASE_PREMIUM = [0.22, 1, 0.36, 1] as const

export const DURATIONS = {
  /** Micro-interactions, list entries, quick UI feedback. */
  quick: 0.18,
  /** Default block-level transitions (cards, panels, modals). */
  default: 0.3,
  /** Hero reveals, marketing sections, theatrical beats. */
  expressive: 0.5,
} as const

export const STAGGER = {
  /** Card lists, form fields, default sequential reveal. */
  default: 0.06,
  /** Homepage hero reveals, marketing sections. */
  hero: 0.1,
} as const

/**
 * Returns a Framer Motion `transition` object that respects
 * `prefers-reduced-motion`. When reduced, `duration=0` so animations snap.
 *
 * @example
 * const t = useMotionConfig("default")
 * return <motion.div transition={t} animate={{ y: 0, opacity: 1 }} />
 */
export function useMotionConfig(duration: keyof typeof DURATIONS = "default") {
  const reduced = useReducedMotion()
  return {
    duration: reduced ? 0 : DURATIONS[duration],
    ease: EASE_PREMIUM,
  }
}

/**
 * Returns a stagger delay value, zeroed under reduced-motion.
 *
 * @example
 * const s = useStagger("default")
 * transition={{ ...useMotionConfig(), delay: index * s }}
 */
export function useStagger(kind: keyof typeof STAGGER = "default") {
  const reduced = useReducedMotion()
  return reduced ? 0 : STAGGER[kind]
}

/** Standard fade-in-up for page sections. */
export const fadeInUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
}

/** Standard fade-in. */
export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
}
