import type { ReactNode } from "react"
import { motion } from "framer-motion"
import { Lock } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { DURATIONS, EASE_PREMIUM, useMotionConfig } from "@/lib/motion"

/**
 * PaywallOverlay — reusable Pro-gate cover for cards.
 *
 * Renders `children` underneath a blurred, non-interactive layer and overlays
 * a lock card with title, optional subtitle, and an upgrade CTA. Used to
 * paywall Score 90+ matches and 6th+ daily signals for Free users.
 *
 * Accessibility: the covered `children` is `aria-hidden` + pointer-events
 * disabled so keyboard focus lands on the CTA button only.
 */

export type PaywallOverlayProps = {
  children: ReactNode
  title: string
  subtitle?: string
  ctaLabel?: string
  onCTA?: () => void
  blurAmount?: number
}

export function PaywallOverlay({
  children,
  title,
  subtitle,
  ctaLabel,
  onCTA,
  blurAmount = 6,
}: PaywallOverlayProps) {
  const navigate = useNavigate()
  const motionConfig = useMotionConfig("default")

  const handleCTA = () => {
    if (onCTA) {
      onCTA()
      return
    }
    navigate("/pricing?plan=pro")
  }

  return (
    <div className="relative">
      <div
        style={{ filter: `blur(${blurAmount}px)` }}
        className="pointer-events-none select-none"
        aria-hidden
      >
        {children}
      </div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ ...motionConfig, duration: motionConfig.duration === 0 ? 0 : DURATIONS.default, ease: EASE_PREMIUM }}
        className="absolute inset-0 flex items-center justify-center bg-obsidian-900/55 backdrop-blur-sm rounded-card"
      >
        <div className="text-center px-6 max-w-[80%]">
          <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-brand-500/15 border border-brand-500/30">
            <Lock className="h-5 w-5 text-brand-400" aria-hidden />
          </div>
          <p className="text-body-md font-medium text-ink">{title}</p>
          {subtitle && <p className="mt-1 text-body-sm text-ink-muted">{subtitle}</p>}
          <button
            type="button"
            onClick={handleCTA}
            aria-label={`Débloquer\u00A0— ${title}`}
            className="mt-4 inline-flex items-center gap-2 h-10 px-5 rounded-md bg-brand-500 text-obsidian-900 font-medium hover:bg-brand-400 transition-premium cursor-pointer"
          >
            {ctaLabel ?? "Débloquer pour 29\u00A0€/mois"}
          </button>
        </div>
      </motion.div>
    </div>
  )
}
