import { useState } from 'react'
import { motion } from 'framer-motion'
import { Sidebar } from './components/dashboard/Sidebar'
import { Overview } from './components/dashboard/Overview'
import { BoiteUnifiee } from './components/dashboard/BoiteUnifiee'
import { Categories } from './components/dashboard/Categories'
import { Replies } from './components/dashboard/Replies'
import { Brouillons } from './components/dashboard/Brouillons'
import { Escalations } from './components/dashboard/Escalations'
import { Analytics } from './components/dashboard/Analytics'
import { Onboarding } from './components/dashboard/Onboarding'
import { ALL_VIEWS, type View } from './components/dashboard/nav'
import { EASE } from './lib/motion'

/**
 * Dashboard de démo Tempo — poste de pilotage du service client.
 * Tout est simulé côté front : la bascule entre vues est un simple état React.
 */
export default function App() {
  const [view, setView] = useState<View>('overview')
  const meta = ALL_VIEWS.find((v) => v.id === view)!
  const today = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="min-h-screen">
      {/* Glow d'ambiance (discret, façon SaaS premium) */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div
          className="absolute -top-40 right-0 h-[40rem] w-[40rem] rounded-full opacity-[0.16] blur-3xl"
          style={{ background: 'radial-gradient(circle, #7c5cff, transparent 70%)' }}
        />
      </div>

      <Sidebar view={view} onSelect={setView} />

      <div className="lg:ml-64">
        {/* Barre supérieure */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-white/[0.06] bg-ink-950/70 px-6 backdrop-blur-xl">
          <div>
            <h1 className="text-[0.95rem] font-semibold tracking-tight text-cloud">{meta.label}</h1>
            {meta.sub && <p className="text-xs text-faint">{meta.sub}</p>}
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden items-center gap-1.5 text-xs text-mist sm:inline-flex">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              Système actif
            </span>
            <span className="hidden text-xs capitalize text-faint md:inline">{today}</span>
          </div>
        </header>

        {/* Contenu de la vue active */}
        <main className="px-6 py-6">
          <motion.div
            key={view}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            {view === 'overview' ? (
              <Overview />
            ) : view === 'inbox' ? (
              <BoiteUnifiee />
            ) : view === 'categories' ? (
              <Categories />
            ) : view === 'replies' ? (
              <Replies />
            ) : view === 'brouillons' ? (
              <Brouillons />
            ) : view === 'escalations' ? (
              <Escalations />
            ) : view === 'analytics' ? (
              <Analytics />
            ) : view === 'onboarding' ? (
              <Onboarding />
            ) : (
              <Placeholder label={meta.label} />
            )}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

/** Écran provisoire pour les vues pas encore construites. */
function Placeholder({ label }: { label: string }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-center">
      <div className="rounded-2xl border border-white/[0.06] bg-ink-900/40 px-10 py-12">
        <p className="text-lg font-semibold text-cloud">{label}</p>
        <p className="mt-1.5 text-sm text-faint">Section en cours de construction.</p>
      </div>
    </div>
  )
}
