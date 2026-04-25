import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { ArrowLeft } from "lucide-react"
import { Logo } from "@/components/ui/Logo"
import { cn } from "@/lib/utils"

type AuthShellProps = {
  children: React.ReactNode
  visual: React.ReactNode
  footer: React.ReactNode
  className?: string
}

export function AuthShell({ children, visual, footer, className }: AuthShellProps) {
  return (
    <div className={cn("relative min-h-screen overflow-hidden bg-obsidian-950", className)}>
      {/* Ambient backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-grid bg-grid-fade opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-[640px] w-[900px] -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: "radial-gradient(50% 50% at 50% 50%, rgba(11,224,166,0.10), transparent 70%)" }}
        aria-hidden
      />

      <div className="relative grid min-h-screen lg:grid-cols-2">
        {/* Left: form */}
        <div className="flex min-h-screen flex-col">
          <header className="flex items-center justify-between px-6 py-5 md:px-10">
            <Link to="/" className="flex items-center gap-2">
              <Logo />
            </Link>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-body-sm text-ink-muted hover:text-ink transition-premium"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Retour
            </Link>
          </header>

          <main id="main" className="flex flex-1 items-center justify-center px-6 pb-12 md:px-10">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
              className="w-full max-w-[420px]"
            >
              {children}
            </motion.div>
          </main>

          <footer className="px-6 pb-6 text-center text-label-sm text-ink-dim md:px-10">
            {footer}
          </footer>
        </div>

        {/* Right: visual panel (desktop only) */}
        <aside className="relative hidden overflow-hidden border-l border-line/60 bg-obsidian-900/60 lg:block">
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(60% 60% at 70% 30%, rgba(11,224,166,0.08), transparent 70%)",
            }}
            aria-hidden
          />
          <div className="relative flex h-full items-center justify-center p-12">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DURATIONS.expressive, delay: 0.15, ease: EASE_PREMIUM }}
              className="w-full max-w-[460px]"
            >
              {visual}
            </motion.div>
          </div>
        </aside>
      </div>
    </div>
  )
}
