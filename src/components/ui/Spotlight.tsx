import { useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'

/**
 * Lueur d'accent qui suit le curseur sur la surface (effet « spotlight » premium).
 * Le halo est additif (mix-blend) : il éclaire sans masquer le contenu.
 */
export function Spotlight({
  children,
  className = '',
  size = 420,
}: {
  children: ReactNode
  className?: string
  size?: number
}) {
  const ref = useRef<HTMLDivElement>(null)

  function onMove(e: MouseEvent<HTMLDivElement>) {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    el.style.setProperty('--mx', `${e.clientX - r.left}px`)
    el.style.setProperty('--my', `${e.clientY - r.top}px`)
  }

  return (
    <div ref={ref} onMouseMove={onMove} className={`group/spot relative ${className}`}>
      {children}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-20 rounded-[inherit] opacity-0 mix-blend-screen transition-opacity duration-300 group-hover/spot:opacity-100"
        style={{
          background: `radial-gradient(${size}px circle at var(--mx, 50%) var(--my, 50%), rgba(124,92,255,0.16), transparent 65%)`,
        }}
      />
    </div>
  )
}
