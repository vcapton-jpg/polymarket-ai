import { useState } from 'react'
import { ShieldAlert, UserRound } from 'lucide-react'
import { REQUESTS, PRIORITY_META } from '../../demo/requests'
import type { Request } from '../../demo/types'
import { ChannelIcon } from './ChannelIcon'
import { RequestDetail } from './RequestDetail'

/** File des demandes transmises à un agent humain. */
export function Escalations() {
  const [selected, setSelected] = useState<Request | null>(null)
  const escalated = REQUESTS.filter((r) => r.analysis.action === 'escalate')

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 rounded-2xl border border-amber-400/15 bg-amber-400/[0.05] p-4 text-sm text-amber-200/90">
        <ShieldAlert className="h-4 w-4 shrink-0 text-amber-300" />
        Les cas sensibles (litiges, gestes commerciaux, menaces de résiliation) sont transmis à un
        humain — l’IA ne répond jamais seule dessus.
      </div>

      {escalated.map((r) => (
        <button
          key={r.id}
          onClick={() => setSelected(r)}
          className="block w-full rounded-2xl border-2 border-amber-400/25 bg-amber-400/[0.04] p-4 text-left transition-colors hover:border-amber-400/40"
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

          <div className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
              <span className="inline-flex items-center gap-1.5 font-semibold text-amber-300">
                <ShieldAlert className="h-3.5 w-3.5" /> Transmis à un humain
              </span>
              {r.analysis.escalationTo && (
                <span className="inline-flex items-center gap-1 text-cloud">
                  <UserRound className="h-3 w-3 text-amber-300" /> {r.analysis.escalationTo}
                </span>
              )}
              <span
                className="ml-auto inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-medium"
                style={{
                  color: PRIORITY_META[r.analysis.priority].color,
                  backgroundColor: `color-mix(in srgb, ${PRIORITY_META[r.analysis.priority].color} 14%, transparent)`,
                }}
              >
                Priorité {PRIORITY_META[r.analysis.priority].label}
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-mist">{r.analysis.escalationReason}</p>
          </div>
        </button>
      ))}

      <RequestDetail req={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
