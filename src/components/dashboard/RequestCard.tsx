import { motion } from 'framer-motion'
import { Sparkles, CheckCheck, ShieldAlert, Link2, PencilLine } from 'lucide-react'
import type { Analysis, Request } from '../../demo/types'
import { CATEGORY_META, PRIORITY_META, SENTIMENT_META } from '../../demo/requests'
import { EASE } from '../../lib/motion'
import { ChannelIcon } from './ChannelIcon'

export type CardState = 'analyzing' | 'done'

/** Une carte de la file unifiée : message entrant + traitement IA en direct. */
export function RequestCard({
  req,
  state,
  linked,
  onClick,
}: {
  req: Request
  state: CardState
  linked: boolean
  onClick: () => void
}) {
  return (
    <motion.button
      layout
      onClick={onClick}
      initial={{ opacity: 0, y: -18, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="block w-full rounded-2xl border border-white/[0.06] bg-ink-900/40 p-4 text-left transition-colors hover:border-white/[0.14] hover:bg-ink-900/60"
    >
      {/* En-tête : canal · expéditeur · heure */}
      <div className="flex items-center gap-2 text-xs">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-mist">
          <ChannelIcon channel={req.channel} />
        </span>
        <span className="font-medium text-mist">{req.sender}</span>
        {req.senderRole && <span className="truncate text-faint">· {req.senderRole}</span>}
        <span className="ml-auto shrink-0 text-faint">{req.receivedAt}</span>
      </div>

      {/* Badges : magazine + lien omnicanal */}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        {req.magazine && (
          <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-medium text-mist">
            {req.magazine}
          </span>
        )}
        {linked && (
          <span className="inline-flex items-center gap-1 rounded-md border border-accent/30 bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent-300">
            <Link2 className="h-3 w-3" /> Conversation fusionnée · 2 canaux
          </span>
        )}
      </div>

      {/* Message reçu */}
      <p className="mt-2.5 line-clamp-2 text-sm leading-relaxed text-cloud">{req.message}</p>

      {/* Traitement IA */}
      {state === 'analyzing' ? <Analyzing /> : <Resolved a={req.analysis} />}
    </motion.button>
  )
}

/** État « Tempo analyse… » : barre de progression indéterminée. */
function Analyzing() {
  return (
    <div className="mt-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
      <div className="flex items-center gap-2 text-xs text-mist">
        <Sparkles className="h-3.5 w-3.5 text-accent" /> Tempo analyse…
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/[0.05]">
        <motion.div
          className="h-full w-1/3 rounded-full bg-accent"
          animate={{ x: ['-110%', '320%'] }}
          transition={{ duration: 1, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>
    </div>
  )
}

/** Résultat de l'analyse : badges + action prise. */
function Resolved({ a }: { a: Analysis }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="mt-3 space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill color={CATEGORY_META[a.category].color}>{CATEGORY_META[a.category].label}</Pill>
        <Pill color={PRIORITY_META[a.priority].color} dot>
          Priorité {PRIORITY_META[a.priority].label}
        </Pill>
        <Pill color={SENTIMENT_META[a.sentiment].color} dot>
          {SENTIMENT_META[a.sentiment].label}
        </Pill>
        <Confidence value={a.confidence} />
      </div>

      {a.action === 'escalate' ? (
        <div className="rounded-xl border-2 border-amber-400/30 bg-amber-400/[0.07] p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5" /> Escaladé à un agent humain
          </div>
          {a.escalationTo && <p className="mt-1 text-xs text-cloud">→ {a.escalationTo}</p>}
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-mist">{a.escalationReason}</p>
        </div>
      ) : a.action === 'auto' ? (
        <div className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.05] p-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-300">
            <CheckCheck className="h-3.5 w-3.5" /> Réponse automatique envoyée
          </div>
          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-mist">« {a.reply} »</p>
        </div>
      ) : (
        <div className="rounded-xl border border-accent/20 bg-accent/[0.06] p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-accent-300">
              <PencilLine className="h-3.5 w-3.5" /> Brouillon prêt — à valider
            </div>
            <div className="hidden items-center gap-1.5 sm:flex">
              <span className="rounded-md bg-accent px-2 py-0.5 text-[11px] font-medium text-white">Envoyer</span>
              <span className="rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-mist">Modifier</span>
            </div>
          </div>
          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-mist">« {a.reply} »</p>
        </div>
      )}
    </motion.div>
  )
}

function Pill({ color, dot, children }: { color: string; dot?: boolean; children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium"
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />}
      {children}
    </span>
  )
}

function Confidence({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-medium text-mist">
      Confiance
      <span className="relative h-1 w-8 overflow-hidden rounded-full bg-white/10">
        <motion.span
          className="absolute inset-y-0 left-0 rounded-full bg-accent"
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: EASE }}
        />
      </span>
      <span className="font-mono text-cloud">{value}%</span>
    </span>
  )
}
