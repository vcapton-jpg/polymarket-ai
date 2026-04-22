import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"

type Options = {
  duration?: number
  decimals?: number
  once?: boolean
  format?: (n: number) => string
}

export function useCountUp(target: number, opts: Options = {}) {
  const { duration = 1200, decimals = 0, once = true, format } = opts
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once, margin: "-10% 0px" })
  const reduced = useReducedMotion()
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (!inView) return
    if (reduced) {
      // Snap straight to the final value for users who prefer reduced motion.
      setValue(target)
      return
    }
    let raf = 0
    const start = performance.now()
    const animate = (t: number) => {
      const progress = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(target * eased)
      if (progress < 1) raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf)
  }, [inView, target, duration, reduced])

  const display = format
    ? format(value)
    : value.toLocaleString("fr-FR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })

  return { ref, display }
}
