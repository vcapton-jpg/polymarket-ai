import { useId } from 'react'

/**
 * Logo « Tempo » — deux barres décalées qui montent (mouvement / cadence),
 * en dégradé violet. SVG net à toute taille. Les ids de dégradé sont uniques
 * par instance (useId) pour éviter tout conflit quand le logo est rendu N fois.
 */
export function BrandMark({ className = '' }: { className?: string }) {
  const id = useId()
  const gl = `${id}-l`
  const gr = `${id}-r`
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gl} x1="0" y1="0" x2="0.7" y2="1">
          <stop offset="0" stopColor="#a08fff" />
          <stop offset="1" stopColor="#7a57f2" />
        </linearGradient>
        <linearGradient id={gr} x1="0" y1="0" x2="1" y2="0.5">
          <stop offset="0" stopColor="#8b73ff" />
          <stop offset="1" stopColor="#6234df" />
        </linearGradient>
      </defs>
      {/* barre gauche (plus courte, plus claire) */}
      <path d="M16 82 L28 42 L52 42 L40 82 Z" fill={`url(#${gl})`} />
      {/* barre droite (plus haute, en avant) */}
      <path d="M40 82 L58 22 L82 22 L64 82 Z" fill={`url(#${gr})`} />
    </svg>
  )
}
