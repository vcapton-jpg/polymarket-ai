import type { ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "../../lib/utils"

interface Props {
  title: string
  subtitle?: string
  actions?: ReactNode
}

function isSingleWordTitle(title: string): boolean {
  const t = title.trim()
  return t.length > 0 && !/\s/.test(t)
}

export function PageHeader({ title, subtitle, actions }: Props) {
  const titleGradient = isSingleWordTitle(title)

  return (
    <motion.header
      className="flex items-start justify-between gap-4 mb-8"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <div>
        <h1
          className={cn(
            "text-2xl font-semibold font-display tracking-display",
            titleGradient ? "text-gradient-gold" : "text-txt-primary",
          )}
        >
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-txt-secondary mt-2 max-w-2xl leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-3 shrink-0">{actions}</div>
      )}
    </motion.header>
  )
}
