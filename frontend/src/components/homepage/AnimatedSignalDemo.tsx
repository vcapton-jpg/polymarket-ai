import { useEffect, useLayoutEffect, useRef, useState } from "react"
import {
  motion,
  AnimatePresence,
  useMotionValue,
  useTransform,
  animate as fmAnimate,
  useReducedMotion,
  type MotionValue,
} from "framer-motion"
import {
  Bookmark,
  Check,
  ChevronRight,
  Clock,
  Sparkles,
  Target,
  Timer,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { EASE_PREMIUM } from "@/lib/motion"
import { CategoryPill, DirectionBadge } from "@/components/signals/badges"
import { MOCK_SIGNALS } from "@/data/signals"

/* ─────────────────────────────────────────────────────────── */
/* Demo content — sourced from MOCK_SIGNALS[3] (Fed signal)    */
/* so the hero card stays coherent with the rest of the site.  */
/* ─────────────────────────────────────────────────────────── */

const SIG = MOCK_SIGNALS[3]
const DEMO = {
  stake: 100,
  gain: 142, // 100 USD @ 41% implied → ~142 USD gain if YES
  loss: 100,
}

type Screen = "card" | "form" | "confirmation"
type CursorTarget = "off" | "cta" | "amount" | "submit"

/* Timeline in ms — extra second on the card so the catalyst stays readable
   before the cursor engages; then the full loop runs at a calm pace. */
const TIMELINE = {
  cursorAppear: 1500,
  cursorArriveCta: 3100,
  pulseStart: 3100,
  pulseEnd: 3400,
  ctaClick: 3500,
  morphToForm: 3750,
  cursorToAmount: 4800,
  cursorArriveAmount: 5900,
  amountClick: 6000,
  countupStart: 6150,
  countupEnd: 6750,
  gainPulseStart: 6750,
  gainPulseEnd: 7500,
  cursorToSubmit: 7600,
  cursorArriveSubmit: 8700,
  submitClick: 8900,
  morphToConfirm: 9200,
  loopEnd: 12500,
} as const

export function AnimatedSignalDemo() {
  const reduced = useReducedMotion() ?? false
  const containerRef = useRef<HTMLDivElement>(null)
  const ctaRef = useRef<HTMLElement | null>(null)
  const amountRef = useRef<HTMLElement | null>(null)
  const submitRef = useRef<HTMLElement | null>(null)
  const timers = useRef<number[]>([])

  const [inView, setInView] = useState(false)
  const [tabVisible, setTabVisible] = useState(true)
  const [liveText, setLiveText] = useState("")

  const [screen, setScreen] = useState<Screen>("card")
  const [cardHover, setCardHover] = useState(false)
  const [cursorTarget, setCursorTarget] = useState<CursorTarget>("off")
  const [cursorPulsing, setCursorPulsing] = useState(false)
  const [cursorClicking, setCursorClicking] = useState(false)
  const [submitFlash, setSubmitFlash] = useState(false)
  const [amountActive, setAmountActive] = useState(false)
  const [gainPulse, setGainPulse] = useState(false)
  const [cursorXY, setCursorXY] = useState<{ x: number; y: number }>({ x: -40, y: -40 })

  const amountMV = useMotionValue(0)
  const gainMV = useMotionValue(0)
  const lossMV = useMotionValue(0)

  /* ── Visibility gating ────────────────────────────────────── */
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting && entry.intersectionRatio >= 0.4),
      { threshold: [0, 0.4, 0.8] },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    const onVis = () => setTabVisible(!document.hidden)
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  /* ── Cursor positioning: measured from the target element ─── */
  const moveCursorTo = (target: CursorTarget) => {
    setCursorTarget(target)
    if (target === "off") return
    // Defer to next frame so the target element is in DOM after morphs.
    requestAnimationFrame(() => {
      const el =
        target === "cta" ? ctaRef.current
        : target === "amount" ? amountRef.current
        : target === "submit" ? submitRef.current
        : null
      const c = containerRef.current
      if (!el || !c) return
      const er = el.getBoundingClientRect()
      const cr = c.getBoundingClientRect()
      const zoom = 1.18
      setCursorXY({
        x: (er.left - cr.left + er.width / 2) / zoom,
        y: (er.top - cr.top + er.height / 2) / zoom,
      })
    })
  }

  /* Re-measure cursor position on resize to stay aligned. */
  useLayoutEffect(() => {
    const onResize = () => {
      if (cursorTarget === "off") return
      moveCursorTo(cursorTarget)
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursorTarget])

  const resetToInitial = () => {
    setScreen("card")
    setCardHover(false)
    setCursorTarget("off")
    setCursorXY({ x: -40, y: -40 })
    setCursorPulsing(false)
    setCursorClicking(false)
    setSubmitFlash(false)
    setAmountActive(false)
    setGainPulse(false)
    amountMV.set(0)
    gainMV.set(0)
    lossMV.set(0)
  }

  const clearTimers = () => {
    timers.current.forEach((t) => window.clearTimeout(t))
    timers.current = []
  }
  const schedule = (fn: () => void, at: number) => {
    timers.current.push(window.setTimeout(fn, at))
  }

  /* ── Main animation loop ──────────────────────────────────── */
  useEffect(() => {
    if (!inView || !tabVisible) {
      clearTimers()
      return
    }

    /* Reduced-motion: slideshow with aria-live narration. */
    if (reduced) {
      let cancelled = false
      const run = () => {
        if (cancelled) return
        resetToInitial()
        setLiveText("Étape 1 sur 4\u00A0: signal détecté.")
        schedule(() => {
          setLiveText("Étape 2 sur 4\u00A0: saisie du montant.")
          setScreen("form")
          amountMV.set(DEMO.stake)
          gainMV.set(DEMO.gain)
          lossMV.set(DEMO.loss)
        }, 1500)
        schedule(() => setLiveText("Étape 3 sur 4\u00A0: gain potentiel calculé."), 3000)
        schedule(() => {
          setLiveText("Étape 4 sur 4\u00A0: position enregistrée.")
          setScreen("confirmation")
        }, 4500)
        schedule(() => { if (!cancelled) run() }, 9000)
      }
      run()
      return () => { cancelled = true; clearTimers() }
    }

    let cancelled = false
    const runLoop = () => {
      if (cancelled) return
      resetToInitial()

      /* Beat 1 — cursor appears and glides to "Investir" CTA. */
      schedule(() => {
        setCardHover(true)
        moveCursorTo("cta")
      }, TIMELINE.cursorAppear)
      schedule(() => setCursorPulsing(true), TIMELINE.pulseStart)
      schedule(() => setCursorPulsing(false), TIMELINE.pulseEnd)

      /* Beat 2 — click + morph to order form. */
      schedule(() => setCursorClicking(true), TIMELINE.ctaClick)
      schedule(() => setCursorClicking(false), TIMELINE.ctaClick + 200)
      schedule(() => {
        setScreen("form")
        setCursorTarget("off")
      }, TIMELINE.morphToForm)

      /* Beat 3 — cursor to amount preset, click, countup. */
      schedule(() => moveCursorTo("amount"), TIMELINE.cursorToAmount)
      schedule(() => setCursorClicking(true), TIMELINE.amountClick)
      schedule(() => setCursorClicking(false), TIMELINE.amountClick + 200)
      schedule(() => setAmountActive(true), TIMELINE.amountClick + 80)
      schedule(() => {
        const dur = 0.6
        fmAnimate(amountMV, DEMO.stake, { duration: dur, ease: EASE_PREMIUM })
        fmAnimate(gainMV, DEMO.gain, { duration: dur, ease: EASE_PREMIUM })
        fmAnimate(lossMV, DEMO.loss, { duration: dur, ease: EASE_PREMIUM })
      }, TIMELINE.countupStart)
      schedule(() => setGainPulse(true), TIMELINE.gainPulseStart)
      schedule(() => setGainPulse(false), TIMELINE.gainPulseEnd)

      /* Beat 4 — cursor to submit, click, morph to confirmation. */
      schedule(() => moveCursorTo("submit"), TIMELINE.cursorToSubmit)
      schedule(() => {
        setSubmitFlash(true)
        setCursorClicking(true)
      }, TIMELINE.submitClick)
      schedule(() => setCursorClicking(false), TIMELINE.submitClick + 200)
      schedule(() => {
        setScreen("confirmation")
        setCursorTarget("off")
        setSubmitFlash(false)
      }, TIMELINE.morphToConfirm)

      /* Loop. */
      schedule(() => { if (!cancelled) runLoop() }, TIMELINE.loopEnd)
    }

    runLoop()
    return () => { cancelled = true; clearTimers() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView, tabVisible, reduced])

  return (
    <div
      ref={containerRef}
      className="relative mx-auto w-full"
      aria-label="Démonstration animée\u00A0: comment prendre position sur un signal Foresight"
      data-demo-screen={screen}
      style={{ transform: "translateZ(0)" }}
    >
      <p className="sr-only" aria-live="polite">
        {liveText ||
          "Cette démonstration montre en quatre étapes comment prendre position sur un signal Foresight."}
      </p>

      {/* Glow halo behind card (matches hero) */}
      <div
        className="pointer-events-none absolute inset-x-10 -top-6 h-20 bg-gradient-to-b from-brand-500/20 to-transparent blur-2xl"
        aria-hidden
      />

      {/* Card frame with fixed min-height so morphs don't shift layout */}
      <div
        className={cn(
          "relative isolate overflow-hidden rounded-2xl border bg-obsidian-850/60 backdrop-blur-sm",
          "transition-colors duration-[400ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
          cardHover && screen === "card"
            ? "border-brand-500/40 shadow-elevated"
            : "border-line-strong",
        )}
        style={{ zoom: 1.18 }}
      >
        {/* Direction accent bar (YES/green) */}
        <div
          className="absolute left-0 top-0 h-full w-[3px] bg-gradient-to-b from-signal-yes via-signal-yes/80 to-signal-yes/20"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-signal-yes/20 blur-3xl opacity-40"
          aria-hidden
        />

        <motion.div
          animate={
            reduced
              ? {}
              : { scale: cardHover && screen === "card" ? 1.01 : 1 }
          }
          transition={{ duration: 0.4, ease: EASE_PREMIUM }}
          className="relative h-full"
        >
          <AnimatePresence mode="wait" initial={false}>
            {screen === "card" && (
              <motion.div
                key="card"
                initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduced ? 0 : -6 }}
                transition={{ duration: reduced ? 0.2 : 0.4, ease: EASE_PREMIUM }}
              >
                <DemoSignalCardBody ctaRef={ctaRef} />
              </motion.div>
            )}
            {screen === "form" && (
              <motion.div
                key="form"
                initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduced ? 0 : -6 }}
                transition={{ duration: reduced ? 0.2 : 0.4, ease: EASE_PREMIUM }}
              >
                <DemoOrderFormBody
                  amountMV={amountMV}
                  gainMV={gainMV}
                  lossMV={lossMV}
                  amountActive={amountActive}
                  gainPulse={gainPulse}
                  submitFlash={submitFlash}
                  reduced={reduced}
                  amountRef={amountRef}
                  submitRef={submitRef}
                />
              </motion.div>
            )}
            {screen === "confirmation" && (
              <motion.div
                key="confirmation"
                initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0.2 : 0.4, ease: EASE_PREMIUM }}
                className="flex min-h-[460px] items-center justify-center"
              >
                <DemoConfirmationBody reduced={reduced} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Cursor overlay */}
        {!reduced && (
          <DemoCursor
            x={cursorXY.x}
            y={cursorXY.y}
            visible={cursorTarget !== "off"}
            pulsing={cursorPulsing}
            clicking={cursorClicking}
          />
        )}
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Signal card body — visually identical to the real SignalCard */
/* with MOCK_SIGNALS[3] content.                                 */
/* ─────────────────────────────────────────────────────────── */

function DemoSignalCardBody({
  ctaRef,
}: {
  ctaRef: React.MutableRefObject<HTMLElement | null>
}) {
  return (
    <div className="relative px-5 py-4 md:px-6 md:py-5">
      {/* Top row */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <CategoryPill label={SIG.categoryLabel} />
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="inline-flex items-center gap-1 text-[0.6875rem] text-ink-readable whitespace-nowrap">
            <Clock className="h-3 w-3" aria-hidden />
            il y a 5 min
          </span>
          <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-ink-dim/60 select-none">
            exemple
          </span>
        </div>
      </div>

      {/* Hero row: score tile + meta */}
      <div className="mb-4 flex items-stretch gap-4 rounded-xl border border-line/80 bg-obsidian-800/40 px-4 py-3">
        <div className="flex shrink-0 flex-col items-center justify-center rounded-lg border border-brand-400/50 bg-brand-400/10 px-4 py-2 text-brand-300 min-w-[96px]">
          <span className="num font-display text-[2.25rem] font-semibold leading-none tracking-tight">
            {SIG.score}
          </span>
          <span className="mt-1 font-mono text-[0.625rem] uppercase tracking-[0.14em] opacity-80">
            {SIG.scoreLabel}
          </span>
        </div>
        <div className="flex flex-1 min-w-0 flex-col justify-center gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <DirectionBadge direction={SIG.direction} size="md" />
            <span className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800/60 px-2.5 py-1 text-[0.75rem]">
              <span className="text-ink-readable">Marché</span>
              <span className="num font-semibold text-signal-yes">
                {Math.round(SIG.marketProbability * 100)}%
              </span>
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-[0.75rem] text-ink-muted">
            <Timer className="h-3.5 w-3.5 text-brand-400" aria-hidden />
            <span>Agir avant</span>
            <span className="num font-semibold text-ink">
              ~{SIG.windowHours}&nbsp;h
            </span>
          </div>
        </div>
      </div>

      {/* Question */}
      <h3 className="mb-4 font-display text-[1.125rem] md:text-[1.25rem] font-semibold leading-tight tracking-tight text-ink text-balance">
        {SIG.question}
      </h3>

      {/* Sub-metrics grid */}
      <div className="mb-4 grid grid-cols-3 gap-x-4 gap-y-2">
        <MetricCell label="Confiance" value={SIG.confidence} tone="positive" />
        <MetricCell label="Urgence" value={SIG.urgency} tone="positive" />
        <MetricCell label="Tradabilité" value={SIG.tradability} tone="positive" />
      </div>

      {/* Catalyst */}
      <div className="mb-4 rounded-lg border border-line/80 bg-obsidian-800/40 px-3.5 py-3">
        <p className="text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim mb-1">
          Ce qu’on a détecté
        </p>
        <p className="text-sm leading-relaxed text-ink/90">{SIG.catalyst}</p>
      </div>

      {/* Footer: sources + bookmark + Investir */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
        <div className="flex items-center gap-2 text-[0.75rem] text-ink-muted">
          <Target className="h-3.5 w-3.5 text-brand-400" aria-hidden />
          <span>
            <span className="num font-medium text-ink">{SIG.sources.length}</span>{" "}
            sources
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-dim"
          >
            <Bookmark className="h-4 w-4" />
          </span>
          <span
            ref={(el) => { ctaRef.current = el }}
            data-demo-cta
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand-500 px-3 text-[0.8125rem] font-medium text-obsidian-900 shadow-[0_0_0_1px_rgba(11,224,166,0.25),0_6px_20px_-8px_rgba(11,224,166,0.45)]"
          >
            Investir
            <ChevronRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    </div>
  )
}

function MetricCell({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: "positive" | "warning" | "negative"
}) {
  const toneCls =
    tone === "positive" ? "text-signal-yes"
    : tone === "warning" ? "text-signal-amber"
    : tone === "negative" ? "text-signal-no"
    : "text-ink"
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim">
        {label}
      </span>
      <span className={cn("text-[0.8125rem] font-medium", toneCls)}>{value}</span>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Order form body — mimics the real OrderForm                 */
/* ─────────────────────────────────────────────────────────── */

function DemoOrderFormBody({
  amountMV,
  gainMV,
  lossMV,
  amountActive,
  gainPulse,
  submitFlash,
  reduced,
  amountRef,
  submitRef,
}: {
  amountMV: MotionValue<number>
  gainMV: MotionValue<number>
  lossMV: MotionValue<number>
  amountActive: boolean
  gainPulse: boolean
  submitFlash: boolean
  reduced: boolean
  amountRef: React.MutableRefObject<HTMLElement | null>
  submitRef: React.MutableRefObject<HTMLElement | null>
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl p-5 md:p-6",
        "bg-gradient-to-br from-brand-500/[0.06] via-obsidian-850/80 to-obsidian-900",
      )}
    >
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-brand-500/40 bg-brand-500/10">
            <Sparkles className="h-4 w-4 text-brand-400" />
          </div>
          <div>
            <h3 className="font-display text-body-lg font-semibold text-ink">
              Parier sur ce marché
            </h3>
            <p className="text-body-sm text-ink-muted">
              Exécution directe via Polymarket — aucun redirect.
            </p>
          </div>
        </div>
        <span className="inline-flex h-6 items-center rounded-full border border-brand-500/40 bg-brand-500/10 px-2 text-[0.625rem] font-mono uppercase tracking-wider text-brand-300">
          Native
        </span>
      </div>

      {/* Direction toggle — YES active */}
      <div className="mb-4">
        <p className="mb-1.5 font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-ink-dim">
          Direction
        </p>
        <div className="grid grid-cols-2 gap-2">
          <span className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-signal-yes/60 bg-signal-yes/10 font-mono font-semibold tracking-wider text-signal-yes shadow-[0_0_0_1px_rgba(34,197,94,0.25)]">
            <span aria-hidden className="text-xs">▲</span>
            BUY YES
          </span>
          <span className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-line-strong bg-obsidian-800/60 font-mono font-semibold tracking-wider text-ink-muted">
            <span aria-hidden className="text-xs">▼</span>
            BUY NO
          </span>
        </div>
      </div>

      {/* Amount input + presets */}
      <div className="mb-4">
        <div className="mb-1.5 flex items-center justify-between font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-ink-dim">
          <span>Mise (USDC)</span>
          <span className="normal-case tracking-normal">
            ≈ <CountupNumber mv={amountMV} inline /> €
          </span>
        </div>
        <div className="relative mb-2">
          <span className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-body-sm text-ink-dim" aria-hidden>
            $
          </span>
          <div
            className={cn(
              "num flex h-11 w-full items-center justify-end rounded-md border bg-obsidian-800 pl-8 pr-3.5 font-display text-lg font-semibold tracking-tight text-ink transition-premium",
              amountActive
                ? "border-brand-500/60 shadow-[0_0_0_2px_rgba(11,224,166,0.18)]"
                : "border-line-strong",
            )}
          >
            <CountupNumber mv={amountMV} />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {[10, 25, 50, 100].map((p) => {
            const active = p === DEMO.stake && amountActive
            const isTarget = p === DEMO.stake
            return (
              <span
                key={p}
                ref={isTarget ? (el) => { amountRef.current = el } : undefined}
                className={cn(
                  "num inline-flex h-7 items-center rounded-full border px-2.5 font-mono text-[0.6875rem] transition-premium",
                  active
                    ? "border-brand-500/40 bg-brand-500/10 text-brand-300"
                    : "border-line bg-obsidian-800/60 text-ink-muted",
                )}
              >
                ${p}
              </span>
            )
          })}
        </div>
      </div>

      {/* Gain / Loss cells */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <motion.div
          animate={
            reduced
              ? {}
              : {
                  scale: gainPulse ? [1, 1.06, 1] : 1,
                  boxShadow: gainPulse
                    ? [
                        "0 0 0 0 rgba(74,222,128,0)",
                        "0 0 22px 4px rgba(74,222,128,0.32)",
                        "0 0 0 0 rgba(74,222,128,0)",
                      ]
                    : "0 0 0 0 rgba(74,222,128,0)",
                }
          }
          transition={{ duration: 0.7, ease: EASE_PREMIUM }}
          className={cn(
            "rounded-md border bg-signal-yes/5 p-4 transition-colors duration-[400ms]",
            gainPulse ? "border-signal-yes/50" : "border-signal-yes/20",
          )}
        >
          <p className="text-label-sm text-ink-readable">Gain si ✓</p>
          <div className="num mt-1 flex items-baseline gap-0.5 text-title-md font-semibold text-signal-yes">
            <span>+$</span>
            <CountupNumber mv={gainMV} tone="yes" />
          </div>
        </motion.div>
        <div className="rounded-md border border-signal-no/20 bg-signal-no/5 p-4">
          <p className="text-label-sm text-ink-readable">Perte si ✗</p>
          <div className="num mt-1 flex items-baseline gap-0.5 text-title-md font-semibold text-signal-no">
            <span>−$</span>
            <CountupNumber mv={lossMV} tone="no" />
          </div>
        </div>
      </div>

      {/* Submit */}
      <span
        ref={(el) => { submitRef.current = el }}
        data-demo-submit
        className={cn(
          "inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-md px-3 text-[0.875rem] font-semibold text-obsidian-900 shadow-[0_0_0_1px_rgba(11,224,166,0.25),0_6px_20px_-8px_rgba(11,224,166,0.45)]",
          "transition-colors duration-200",
          submitFlash ? "bg-brand-400" : "bg-brand-500",
        )}
      >
        Valider ma position
        <ChevronRight className="h-4 w-4" />
      </span>
    </div>
  )
}

function CountupNumber({
  mv,
  tone,
  inline,
}: {
  mv: MotionValue<number>
  tone?: "yes" | "no"
  inline?: boolean
}) {
  const rounded = useTransform(mv, (v) => Math.round(v))
  const [n, setN] = useState(() => Math.round(mv.get()))
  useEffect(() => rounded.on("change", (v) => setN(v)), [rounded])
  const toneCls =
    tone === "yes" ? "text-signal-yes"
    : tone === "no" ? "text-signal-no"
    : "text-ink"
  return (
    <span
      className={cn(
        "num tabular-nums",
        inline ? "text-ink-dim" : cn("font-display font-semibold leading-none tracking-tight", toneCls),
      )}
    >
      {n}
    </span>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Confirmation body                                            */
/* ─────────────────────────────────────────────────────────── */

function DemoConfirmationBody({ reduced }: { reduced: boolean }) {
  return (
    <div className="relative flex flex-col items-center justify-center px-6 py-10 text-center">
      <motion.div
        initial={{ scale: reduced ? 1 : 0 }}
        animate={reduced ? { scale: 1 } : { scale: [0, 1.15, 1] }}
        transition={{ duration: reduced ? 0.2 : 0.55, ease: EASE_PREMIUM, times: [0, 0.6, 1] }}
        className="relative"
      >
        <motion.div
          animate={reduced ? {} : { scale: [1, 1.02, 1] }}
          transition={{ duration: 2.2, ease: "easeInOut", repeat: Infinity }}
          className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-brand-500 shadow-brand-glow"
          aria-hidden
        >
          <Check className="h-7 w-7 text-obsidian-900" strokeWidth={3} />
        </motion.div>
      </motion.div>

      <p className="mt-5 font-display text-title-md font-semibold text-ink">
        Votre position a été enregistrée
      </p>
      <p className="mt-1.5 num tabular-nums text-body-sm text-ink-readable">
        100&nbsp;USD engagés · +142&nbsp;USD en gain potentiel
      </p>
      <p className="mt-4 text-label-sm text-ink-dim">
        Retrouvez-la dans votre portfolio Foresight.
      </p>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Stylized cursor — glowing dot with halo + click ripple       */
/* ─────────────────────────────────────────────────────────── */

function DemoCursor({
  x,
  y,
  visible,
  pulsing,
  clicking,
}: {
  x: number
  y: number
  visible: boolean
  pulsing: boolean
  clicking: boolean
}) {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none absolute z-30"
      initial={false}
      animate={{ x, y, opacity: visible ? 1 : 0 }}
      transition={{
        x: { duration: 1.0, ease: EASE_PREMIUM },
        y: { duration: 1.0, ease: EASE_PREMIUM },
        opacity: { duration: 0.25, ease: EASE_PREMIUM },
      }}
      style={{ left: 0, top: 0, translateX: "-50%", translateY: "-50%" }}
    >
      <span
        className="absolute -inset-3 rounded-full bg-brand-500/25 blur-md"
        aria-hidden
      />
      <motion.span
        className="relative block h-3 w-3 rounded-full bg-brand-500 shadow-[0_0_16px_rgba(11,224,166,0.65)]"
        animate={{
          scale: clicking ? [1, 0.82, 1] : pulsing ? [1, 1.18, 1] : 1,
        }}
        transition={{
          duration: clicking ? 0.18 : pulsing ? 0.28 : 0.2,
          ease: EASE_PREMIUM,
        }}
      />
      <AnimatePresence>
        {clicking && (
          <motion.span
            key="ripple"
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-brand-500/50"
            initial={{ width: 0, height: 0, opacity: 0.6 }}
            animate={{ width: 52, height: 52, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: EASE_PREMIUM }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  )
}
