import { useState } from 'react'
import { REQUESTS, CATEGORY_META, PRIORITY_META, ACTION_META } from '../../demo/requests'
import type { Category, Request } from '../../demo/types'
import { ChannelIcon } from './ChannelIcon'
import { RequestDetail } from './RequestDetail'

const FILTERS: { id: Category | 'all'; label: string }[] = [
  { id: 'all', label: 'Toutes' },
  { id: 'livraison', label: 'Livraison' },
  { id: 'abonnement', label: 'Abonnement' },
  { id: 'facturation', label: 'Facturation' },
  { id: 'produit', label: 'Produit / éditorial' },
  { id: 'reclamation', label: 'Réclamation' },
]

/** Répertoire : toutes les demandes, triées, filtrables, retrouvables. */
export function Categories() {
  const [filter, setFilter] = useState<Category | 'all'>('all')
  const [selected, setSelected] = useState<Request | null>(null)
  const rows = filter === 'all' ? REQUESTS : REQUESTS.filter((r) => r.analysis.category === filter)

  return (
    <div className="space-y-4">
      {/* Filtres par catégorie */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => {
          const count = f.id === 'all' ? REQUESTS.length : REQUESTS.filter((r) => r.analysis.category === f.id).length
          const active = filter === f.id
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                active
                  ? 'bg-accent/15 text-accent-300 ring-1 ring-inset ring-accent/30'
                  : 'border border-white/10 text-mist hover:text-cloud'
              }`}
            >
              {f.label}
              <span className="text-faint">{count}</span>
            </button>
          )
        })}
      </div>

      {/* Tableau */}
      <div className="overflow-x-auto rounded-2xl border border-white/[0.06] bg-ink-900/40">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-white/[0.06] text-[11px] uppercase tracking-wider text-faint">
              <th className="px-4 py-3 font-medium">Demande</th>
              <th className="px-4 py-3 font-medium">Magazine</th>
              <th className="px-4 py-3 font-medium">Catégorie</th>
              <th className="px-4 py-3 font-medium">Priorité</th>
              <th className="px-4 py-3 font-medium">Statut</th>
              <th className="px-4 py-3 text-right font-medium">Heure</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.id}
                onClick={() => setSelected(r)}
                className="cursor-pointer border-b border-white/[0.04] transition-colors last:border-0 hover:bg-white/[0.02]"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-mist">
                      <ChannelIcon channel={r.channel} />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-cloud">{r.sender}</p>
                      <p className="max-w-[22rem] truncate text-xs text-faint">{r.message}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-mist">{r.magazine ?? '—'}</td>
                <td className="px-4 py-3">
                  <Tag color={CATEGORY_META[r.analysis.category].color}>{CATEGORY_META[r.analysis.category].label}</Tag>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5 text-mist">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: PRIORITY_META[r.analysis.priority].color }} />
                    {PRIORITY_META[r.analysis.priority].label}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Tag color={ACTION_META[r.analysis.action].color}>{ACTION_META[r.analysis.action].short}</Tag>
                </td>
                <td className="px-4 py-3 text-right text-faint">{r.receivedAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <RequestDetail req={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function Tag({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium"
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {children}
    </span>
  )
}
