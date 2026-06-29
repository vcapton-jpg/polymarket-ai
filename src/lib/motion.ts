import type { Variants } from 'framer-motion'

/** Easing « doux premium » réutilisé partout (cubic-bezier). */
export const EASE: [number, number, number, number] = [0.22, 0.61, 0.36, 1]

/** Conteneur qui orchestre l'apparition en cascade de ses enfants. */
export const staggerContainer = (stagger = 0.08, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren: delay } },
})

/** Apparition « fade + montée » standard (pour les enfants d'un stagger). */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
}

/** Fondu simple. */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.7, ease: EASE } },
}

/** Apparition avec léger zoom (cartes, panneaux). */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96, y: 12 },
  show: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
}

/**
 * Réglage viewport commun pour whileInView :
 * on ne rejoue qu'une fois, déclenché un peu avant l'entrée à l'écran.
 */
export const viewportOnce = { once: true, margin: '-80px' } as const
