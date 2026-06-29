import { useState } from 'react'
import { PencilLine } from 'lucide-react'
import { REQUESTS } from '../../demo/requests'
import type { Request } from '../../demo/types'
import { ChannelIcon } from './ChannelIcon'
import { RequestDetail } from './RequestDetail'

/** File des brouillons : réponses rédigées par l'IA, prêtes à valider par un humain. */
export function Brouillons() {
  const [selected, setSelected] = useState<Request | null>(null)
  const drafts = REQUESTS.filter((r) => r.analysis.action === 'draft')

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 rounded-2xl border border-accent/15 bg-accent/[0.05] p-4 text-sm text-accent-200/90">
        <PencilLine className="h-4 w-4 shrink-0 text-accent" />
        Réponses déjà rédigées dans votre ton, prêtes à partir — pour les cas simples qui méritent un
        dernier regard. Vous validez en un clic.
      </div>

      {drafts.map((r) => (
        <button
          key={r.id}
          onClick={() => setSelected(r)}
          className="block w-full rounded-2xl border border-accent/20 bg-accent/[0.04] p-4 text-left transition-colors hover:border-accent/40"
        >
          <div className="flex items-center gap-2 text-xs">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-mist">
              <ChannelIcon channel={r.channel} />
            </span>
            <span className="font-medium text-mist">{r.sender}</span>
            {r.senderRole && <span className="truncate text-faint">· {r.senderRole}</span>}
            <span className="ml-auto shrink-0 text-faint">{r.receivedAt}</span>
          </div>

          {r.magazine && (
            <span className="mt-2 inline-block rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-medium text-mist">
              {r.magazine}
            </span>
          )}
          <p className="mt-2 text-sm leading-relaxed text-cloud">{r.message}</p>

          <div className="mt-3 rounded-xl border border-accent/20 bg-accent/[0.06] p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-300">
                <PencilLine className="h-3.5 w-3.5" /> Brouillon prêt — à valider
              </span>
              <span className="hidden items-center gap-1.5 sm:flex">
                <span className="rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white">Envoyer</span>
                <span className="rounded-md border border-white/10 px-2.5 py-1 text-[11px] text-mist">Modifier</span>
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-mist">« {r.analysis.reply} »</p>
          </div>
        </button>
      ))}

      <RequestDetail req={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
