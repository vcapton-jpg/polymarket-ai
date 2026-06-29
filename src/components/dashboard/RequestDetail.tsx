import { AnimatePresence, motion } from 'framer-motion'
import { X, CheckCheck, PencilLine, ShieldAlert, Clock, Send } from 'lucide-react'
import type { Request } from '../../demo/types'
import { CATEGORY_META, CHANNEL_META, PRIORITY_META, SENTIMENT_META } from '../../demo/requests'
import { EASE } from '../../lib/motion'
import { ChannelIcon } from './ChannelIcon'

/** Panneau latéral de détail d'une demande (analyse complète + actions humaines). */
export function RequestDetail({ req, onClose }: { req: Request | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {req && (
        <div className="fixed inset-0 z-40">
          <motion.div
            className="absolute inset-0 bg-ink-950/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-white/[0.08] bg-ink-900/95 backdrop-blur-xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.3, ease: EASE }}
          >
            {/* En-tête */}
            <header className="flex items-start justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs text-faint">
                  <ChannelIcon channel={req.channel} className="h-3.5 w-3.5" />
                  {CHANNEL_META[req.channel].label} · {req.receivedAt}
                </div>
                <p className="mt-1 truncate text-base font-semibold text-cloud">{req.sender}</p>
                {req.senderRole && <p className="truncate text-xs text-mist">{req.senderRole}</p>}
              </div>
              <button
                onClick={onClose}
                className="shrink-0 rounded-lg border border-white/10 p-1.5 text-mist transition-colors hover:text-cloud"
                aria-label="Fermer"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
              {/* Message */}
              <section>
                {req.magazine && (
                  <span className="mb-2 inline-block rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-medium text-mist">
                    {req.magazine}
                    {req.subscriberId && <span className="text-faint"> · {req.subscriberId}</span>}
                  </span>
                )}
                <div className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3.5 text-sm leading-relaxed text-cloud">
                  {req.message}
                </div>
              </section>

              {/* Analyse IA */}
              <section>
                <h4 className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
                  Analyse Tempo
                </h4>
                <dl className="grid grid-cols-2 gap-3">
                  <Field label="Catégorie" value={CATEGORY_META[req.analysis.category].label} color={CATEGORY_META[req.analysis.category].color} />
                  <Field label="Priorité" value={PRIORITY_META[req.analysis.priority].label} color={PRIORITY_META[req.analysis.priority].color} />
                  <Field label="Sentiment" value={SENTIMENT_META[req.analysis.sentiment].label} color={SENTIMENT_META[req.analysis.sentiment].color} />
                  <Field label="Confiance" value={`${req.analysis.confidence} %`} />
                </dl>
              </section>

              {/* Réponse / escalade */}
              {req.analysis.action === 'escalate' ? (
                <section className="rounded-xl border-2 border-amber-400/30 bg-amber-400/[0.07] p-4">
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-300">
                    <ShieldAlert className="h-4 w-4" /> Transmis à un agent humain
                  </div>
                  {req.analysis.escalationTo && <p className="mt-1.5 text-xs text-cloud">→ {req.analysis.escalationTo}</p>}
                  <p className="mt-1.5 text-xs leading-relaxed text-mist">{req.analysis.escalationReason}</p>
                  <button className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-amber-400/90 px-3 py-2 text-xs font-medium text-ink-950 transition-colors hover:bg-amber-300">
                    Prendre en charge
                  </button>
                </section>
              ) : (
                <section>
                  {req.analysis.action === 'auto' ? (
                    <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-300">
                      <CheckCheck className="h-3.5 w-3.5" /> Réponse envoyée automatiquement
                    </h4>
                  ) : (
                    <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-300">
                      <PencilLine className="h-3.5 w-3.5" /> Brouillon à valider — dans le ton de la marque
                    </h4>
                  )}
                  <textarea
                    defaultValue={req.analysis.reply}
                    rows={6}
                    className="w-full resize-none rounded-xl border border-white/[0.08] bg-ink-950/50 p-3.5 text-sm leading-relaxed text-cloud outline-none focus:border-accent/40"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-400">
                      <Send className="h-3.5 w-3.5" /> {req.analysis.action === 'auto' ? 'Modifier et renvoyer' : 'Valider et envoyer'}
                    </button>
                    <button className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-mist transition-colors hover:text-cloud">
                      <PencilLine className="h-3.5 w-3.5" /> Modifier
                    </button>
                    <button className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 px-3 py-2 text-xs text-amber-300 transition-colors hover:bg-amber-400/10">
                      <ShieldAlert className="h-3.5 w-3.5" /> Escalader
                    </button>
                  </div>
                </section>
              )}

              {/* Historique client */}
              {req.history && req.history.length > 0 && (
                <section>
                  <h4 className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
                    <Clock className="h-3.5 w-3.5" /> Historique client
                  </h4>
                  <dl className="space-y-2">
                    {req.history.map((h) => (
                      <div key={h.label} className="flex items-baseline justify-between gap-3 text-sm">
                        <dt className="text-faint">{h.label}</dt>
                        <dd className="text-right text-mist">{h.detail}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  )
}

function Field({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
      <dt className="text-[10px] uppercase tracking-wider text-faint">{label}</dt>
      <dd className="mt-0.5 flex items-center gap-1.5 text-sm font-medium" style={{ color: color ?? 'var(--color-cloud)' }}>
        {color && <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />}
        {value}
      </dd>
    </div>
  )
}
