import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Play, Pause, RotateCcw, Inbox } from 'lucide-react'
import type { Request } from '../../demo/types'
import { SIM_SEQUENCE } from '../../demo/requests'
import { classifyRequest } from '../../demo/classify'
import { RequestCard, type CardState } from './RequestCard'
import { RequestDetail } from './RequestDetail'

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))
type Shown = { req: Request; state: CardState }

/**
 * Boîte unifiée — le cœur de la démo.
 * Les demandes « tombent » en haut de la file en temps réel, chacune passant
 * par « Tempo analyse… » → traitée. Tout est simulé (timers + données mockées).
 */
export function BoiteUnifiee() {
  const [shown, setShown] = useState<Shown[]>([])
  const [running, setRunning] = useState(false)
  const [selected, setSelected] = useState<Request | null>(null)

  const idxRef = useRef(0)
  const runRef = useRef(0)

  /** Boucle d'arrivée des demandes (annulable via runRef). */
  const loop = useCallback(async (myRun: number) => {
    while (runRef.current === myRun && idxRef.current < SIM_SEQUENCE.length) {
      const req = SIM_SEQUENCE[idxRef.current]
      idxRef.current += 1
      setShown((prev) => [{ req, state: 'analyzing' }, ...prev]) // tombe en haut
      await classifyRequest(req) // ← simulation du temps d'analyse IA
      if (runRef.current !== myRun) return
      setShown((prev) => prev.map((s) => (s.req.id === req.id ? { ...s, state: 'done' } : s)))
      await wait(1700) // respiration avant la prochaine arrivée
    }
    if (runRef.current === myRun) setRunning(false)
  }, [])

  const start = useCallback(() => {
    if (running) return
    const myRun = ++runRef.current
    setRunning(true)
    void loop(myRun)
  }, [running, loop])

  const pause = useCallback(() => {
    runRef.current++ // annule la boucle en cours
    setRunning(false)
  }, [])

  const replay = useCallback(() => {
    runRef.current++
    idxRef.current = 0
    setSelected(null)
    setShown([])
    const myRun = ++runRef.current
    setRunning(true)
    void loop(myRun)
  }, [loop])

  // Annule la boucle au démontage de la vue
  useEffect(() => () => void runRef.current++, [])

  // Compteurs live
  const done = shown.filter((s) => s.state === 'done')
  const auto = done.filter((s) => s.req.analysis.action === 'auto').length
  const drafts = done.filter((s) => s.req.analysis.action === 'draft').length
  const escalated = done.filter((s) => s.req.analysis.action === 'escalate').length

  // Détection omnicanal : un thread présent ≥ 2 fois = conversation fusionnée
  const threadCount: Record<string, number> = {}
  shown.forEach((s) => {
    if (s.req.threadId) threadCount[s.req.threadId] = (threadCount[s.req.threadId] ?? 0) + 1
  })
  const isLinked = (req: Request) => !!(req.threadId && threadCount[req.threadId] > 1)

  const allDone = idxRef.current >= SIM_SEQUENCE.length && !running

  return (
    <div className="space-y-5">
      {/* Barre de contrôle + compteurs live */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/[0.06] bg-ink-900/40 p-3">
        <div className="flex items-center gap-2">
          {allDone ? (
            <ControlButton primary onClick={replay} icon={RotateCcw} label="Rejouer la simulation" />
          ) : running ? (
            <ControlButton onClick={pause} icon={Pause} label="Pause" />
          ) : (
            <ControlButton primary onClick={start} icon={Play} label="Lancer la simulation" />
          )}
          {shown.length > 0 && !allDone && (
            <ControlButton onClick={replay} icon={RotateCcw} label="Rejouer" />
          )}
          {running && (
            <span className="ml-1 inline-flex items-center gap-1.5 text-xs text-mist">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              En direct
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <LiveCounter value={done.length} label="traitées" color="#f5f5f7" />
          <LiveCounter value={auto} label="auto-résolues" color="#34d399" />
          <LiveCounter value={drafts} label="brouillons" color="#7c5cff" />
          <LiveCounter value={escalated} label="escalades" color="#fbbf24" />
        </div>
      </div>

      {/* File unifiée */}
      {shown.length === 0 ? (
        <EmptyState onStart={start} />
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {shown.map((s) => (
              <RequestCard
                key={s.req.id}
                req={s.req}
                state={s.state}
                linked={isLinked(s.req)}
                onClick={() => setSelected(s.req)}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      <RequestDetail req={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function ControlButton({
  primary,
  onClick,
  icon: Icon,
  label,
}: {
  primary?: boolean
  onClick: () => void
  icon: React.ComponentType<{ className?: string }>
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
        primary
          ? 'bg-accent text-white hover:bg-accent-400'
          : 'border border-white/10 text-mist hover:border-white/20 hover:text-cloud'
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  )
}

function LiveCounter({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex items-baseline gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-1.5">
      <motion.span
        key={value}
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="font-mono text-sm font-semibold tabular-nums"
        style={{ color }}
      >
        {value}
      </motion.span>
      <span className="text-[11px] text-faint">{label}</span>
    </div>
  )
}

function EmptyState({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-white/[0.08] text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/20">
        <Inbox className="h-7 w-7" />
      </span>
      <div>
        <p className="text-base font-semibold text-cloud">La file unifiée est prête</p>
        <p className="mx-auto mt-1 max-w-sm text-sm text-faint">
          Tous les canaux fusionnés en une seule vue. Lancez la simulation : les demandes arrivent en
          temps réel et Tempo les traite sous vos yeux.
        </p>
      </div>
      <button
        onClick={onStart}
        className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-400"
      >
        <Play className="h-4 w-4" /> Lancer la simulation
      </button>
    </div>
  )
}
