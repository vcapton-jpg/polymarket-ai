import type { ReactNode } from 'react'
import { Reveal } from './Reveal'

/** En-tête de section réutilisable : eyebrow + titre + sous-titre optionnel. */
export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  align = 'center',
}: {
  eyebrow: string
  title: ReactNode
  subtitle?: ReactNode
  align?: 'center' | 'left'
}) {
  return (
    <Reveal className={align === 'center' ? 'mx-auto max-w-2xl text-center' : 'max-w-2xl'}>
      <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-ink-900/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.14em] text-accent-300">
        {eyebrow}
      </span>
      <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
        {title}
      </h2>
      {subtitle && <p className="mt-4 text-balance text-mist">{subtitle}</p>}
    </Reveal>
  )
}
