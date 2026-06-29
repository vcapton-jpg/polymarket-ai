import type { ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  // Accent plein + glow violet (CTA principal)
  primary:
    'bg-accent text-white ring-1 ring-inset ring-white/15 shadow-[0_8px_30px_-10px_rgba(124,92,255,0.7)] hover:bg-accent-400 hover:-translate-y-0.5 hover:shadow-[0_14px_44px_-8px_rgba(124,92,255,0.85)]',
  // Surface glass (CTA secondaire)
  secondary: 'glass text-cloud hover:border-white/20 hover:text-white hover:-translate-y-0.5',
  // Lien discret
  ghost: 'text-mist hover:text-cloud',
}

const SIZES: Record<Size, string> = {
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-[0.95rem]',
}

/**
 * CTA unifié. Rendu en <a> si `href` est fourni (liens Calendly / ancres / mailto),
 * sinon en <button>. Toutes les actions du site passent par ce composant.
 */
export function Button({
  children,
  href,
  variant = 'primary',
  size = 'md',
  external,
  className = '',
  onClick,
}: {
  children: ReactNode
  href?: string
  variant?: Variant
  size?: Size
  external?: boolean
  className?: string
  onClick?: () => void
}) {
  const cls = `inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 active:translate-y-0 ${SIZES[size]} ${VARIANTS[variant]} ${className}`

  if (href) {
    return (
      <a
        href={href}
        className={cls}
        onClick={onClick}
        {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      >
        {children}
      </a>
    )
  }
  return (
    <button type="button" className={cls} onClick={onClick}>
      {children}
    </button>
  )
}
