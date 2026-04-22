import { Link, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { DURATIONS } from "@/lib/motion"
import { useEffect, useState } from "react"
import { Menu, X } from "lucide-react"
import { Logo } from "@/components/ui/Logo"
import { Button } from "@/components/ui/Button"
import { cn } from "@/lib/utils"

const NAV_LINKS = [
  { label: "Comment ça marche", href: "/#how" },
  { label: "Pricing", href: "/pricing" },
  { label: "FAQ", href: "/faq" },
]

export function PublicNav() {
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  useEffect(() => {
    setOpen(false)
  }, [pathname])

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-40 transition-premium",
        scrolled
          ? "border-b border-line/80 bg-obsidian-900/70 backdrop-blur-xl"
          : "border-b border-transparent",
      )}
    >
      <div className="container-page relative flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <Logo />
        </Link>

        {/* Nav links — absolutely centered so they don't shift with logo/button width */}
        <nav className="absolute left-1/2 -translate-x-1/2 hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="px-3 py-2 text-sm text-ink-muted hover:text-ink transition-premium"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-2 shrink-0">
          <Link to="/login">
            <Button variant="ghost" size="sm">Se connecter</Button>
          </Link>
          <Link to="/signup?plan=free">
            <Button variant="primary" size="sm">Commencer gratuitement</Button>
          </Link>
        </div>

        <button
          className="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-md text-ink hover:bg-obsidian-800 cursor-pointer"
          onClick={() => setOpen(!open)}
          aria-label="Menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: DURATIONS.quick }}
            className="md:hidden border-t border-line/60 bg-obsidian-900/95 backdrop-blur-xl"
          >
            <div className="container-page flex flex-col gap-2 py-4">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="rounded-md px-3 py-3 text-sm text-ink-muted hover:bg-obsidian-800 hover:text-ink"
                >
                  {link.label}
                </a>
              ))}
              <div className="mt-2 flex flex-col gap-2 pt-2 border-t border-line/60">
                <Link to="/login"><Button variant="secondary" className="w-full">Se connecter</Button></Link>
                <Link to="/signup?plan=free"><Button variant="primary" className="w-full">Commencer gratuitement</Button></Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
