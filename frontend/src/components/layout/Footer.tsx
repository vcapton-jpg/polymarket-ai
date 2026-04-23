import { Link } from "react-router-dom"
import { Logo } from "@/components/ui/Logo"

export function Footer() {
  return (
    <footer className="relative border-t border-line/60 bg-obsidian-900">
      <div className="container-page flex flex-col gap-6 py-10 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-6">
          <Logo />
          <span className="hidden md:inline text-label-sm text-ink-dim">
            © 2026 · Signal informatif · Pas un conseil financier
          </span>
        </div>

        <nav className="flex flex-wrap items-center gap-5 text-body-sm text-ink-muted">
          <Link to="/mentions-legales" className="hover:text-ink transition-premium">Mentions légales</Link>
          <Link to="/cgu" className="hover:text-ink transition-premium">CGU</Link>
          <Link to="/risques" className="hover:text-ink transition-premium">Risques</Link>
          <a href="mailto:contact@foresight.app" className="hover:text-ink transition-premium">Contact</a>
        </nav>

        <div className="flex items-center gap-2 rounded-full border border-line-strong bg-obsidian-800/60 px-3 py-1.5 text-label-sm">
          <span className="relative inline-flex h-1.5 w-1.5">
            <span className="absolute inset-0 animate-ping rounded-full bg-brand-500 opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-500" />
          </span>
          <span className="text-ink">Pipeline actif</span>
          <span className="text-line-strong">·</span>
          <span className="num text-ink-muted">Dernier signal il y a 3 min</span>
        </div>
      </div>
    </footer>
  )
}
