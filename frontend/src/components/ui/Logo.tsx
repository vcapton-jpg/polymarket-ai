import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"

type LogoProps = {
  className?: string
  showWordmark?: boolean
  size?: number
}

export function Logo({ className, showWordmark = true, size = 28 }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <motion.div
        initial={{ opacity: 0, rotate: -30 }}
        animate={{ opacity: 1, rotate: 0 }}
        transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
        className="relative grid place-items-center"
        style={{ width: size, height: size }}
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <defs>
            <linearGradient id="fg" x1="0" y1="0" x2="32" y2="32">
              <stop offset="0%" stopColor="#5DFFCE" />
              <stop offset="100%" stopColor="#0BE0A6" />
            </linearGradient>
          </defs>
          <rect x="1" y="1" width="30" height="30" rx="8" stroke="url(#fg)" strokeWidth="1.4" opacity="0.4" />
          <path
            d="M9 22 L9 10 L23 10 M9 16 L19 16"
            stroke="url(#fg)"
            strokeWidth="2.4"
            strokeLinecap="square"
            strokeLinejoin="miter"
          />
          <circle cx="23" cy="22" r="2.2" fill="url(#fg)" />
        </svg>
      </motion.div>
      {showWordmark && (
        <span className="font-display text-[1.05rem] font-semibold tracking-tight text-ink">
          Foresight
        </span>
      )}
    </div>
  )
}
