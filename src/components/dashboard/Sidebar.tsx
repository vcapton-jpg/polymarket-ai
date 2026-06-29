import { motion } from 'framer-motion'
import { CONFIG } from '../../config'
import { EASE } from '../../lib/motion'
import { BrandMark } from '../ui/BrandMark'
import { NAV_MAIN, NAV_FOOTER, type NavItem, type View } from './nav'

/** Barre latérale de navigation du dashboard. */
export function Sidebar({ view, onSelect }: { view: View; onSelect: (v: View) => void }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/[0.06] bg-ink-900/70 backdrop-blur-xl lg:flex">
      {/* Logo produit */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <BrandMark className="h-[22px] w-[22px]" />
        <span className="text-[1.05rem] font-semibold tracking-tight text-cloud">{CONFIG.product}</span>
        <span className="ml-1 rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-faint">
          démo
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-1">
        <p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-faint/70">
          Pilotage
        </p>
        {NAV_MAIN.map((item) => (
          <NavButton key={item.id} item={item} active={view === item.id} onClick={() => onSelect(item.id)} />
        ))}
        <div className="my-3 border-t border-white/[0.06]" />
        {NAV_FOOTER.map((item) => (
          <NavButton key={item.id} item={item} active={view === item.id} onClick={() => onSelect(item.id)} />
        ))}
      </nav>

      {/* Espace client (personnalisation prospect) */}
      <div className="border-t border-white/[0.06] p-3">
        <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent/30 to-accent/[0.04] text-[11px] font-bold text-accent-300 ring-1 ring-accent/20">
            {CONFIG.clientShort}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[10px] uppercase tracking-wider text-faint">Espace</p>
            <p className="truncate text-sm font-medium text-cloud">{CONFIG.client}</p>
          </div>
        </div>
      </div>
    </aside>
  )
}

function NavButton({ item, active, onClick }: { item: NavItem; active: boolean; onClick: () => void }) {
  const Icon = item.icon
  return (
    <button
      onClick={onClick}
      className={`group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
        active ? 'text-cloud' : 'text-mist hover:bg-white/[0.04] hover:text-cloud'
      }`}
    >
      {active && (
        <motion.span
          layoutId="navActive"
          transition={{ duration: 0.25, ease: EASE }}
          className="absolute inset-0 rounded-lg bg-accent/[0.12] ring-1 ring-inset ring-accent/25"
        />
      )}
      <Icon className={`relative z-10 h-[18px] w-[18px] ${active ? 'text-accent' : 'text-faint group-hover:text-mist'}`} />
      <span className="relative z-10 text-sm font-medium">{item.label}</span>
    </button>
  )
}
