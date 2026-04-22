import { useEffect, useId, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import FocusLock from "react-focus-lock"
import { Check, X } from "lucide-react"
import type { Signal } from "@/types/signal"
import { Button } from "@/components/ui/Button"
import { useUserPreferences } from "@/lib/userPreferences"
import { useToasts } from "@/lib/useToasts"
import { addManualPosition, type ManualPositionInput } from "@/lib/manualPositions"
import { DURATIONS, EASE_PREMIUM } from "@/lib/motion"
import { cn } from "@/lib/utils"

type Direction = "YES" | "NO"
const DIRECTIONS: readonly Direction[] = ["YES", "NO"] as const

type ManualPositionModalProps = {
  open: boolean
  signal: Signal
  onClose: () => void
  onSaved?: (input: ManualPositionInput) => void
}

/**
 * Modal for logging a position that the user took directly on Polymarket.
 *
 * Polymarket-powered native orders go through OrderForm. This path covers
 * the case where the user prefers to trade themselves and only needs
 * Foresight for tracking.
 */
export function ManualPositionModal({
  open,
  signal,
  onClose,
  onSaved,
}: ManualPositionModalProps) {
  const titleId = useId()
  const stakeErrorId = useId()
  const priceErrorId = useId()
  const { formatMoney } = useUserPreferences()
  const { addToast } = useToasts()
  const navigate = useNavigate()

  const [touched, setTouched] = useState<{ stake: boolean; price: boolean }>({
    stake: false,
    price: false,
  })
  const [direction, setDirection] = useState<Direction>(signal.direction)
  const directionRefs = useRef<Map<Direction, HTMLButtonElement | null>>(new Map())
  const handleDirectionKey = (d: Direction, e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "ArrowUp" && e.key !== "ArrowDown") return
    e.preventDefault()
    const next: Direction = d === "YES" ? "NO" : "YES"
    setDirection(next)
    directionRefs.current.get(next)?.focus()
  }
  const [stake, setStake] = useState<number>(25)
  const [entryPrice, setEntryPrice] = useState<number>(signal.marketProbability)
  const [saved, setSaved] = useState(false)

  // Reset to signal defaults whenever re-opened
  useEffect(() => {
    if (open) {
      setDirection(signal.direction)
      setStake(25)
      setEntryPrice(signal.marketProbability)
      setSaved(false)
      setTouched({ stake: false, price: false })
    }
  }, [open, signal.direction, signal.marketProbability])

  // ESC to close
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const stakeValid = stake > 0 && stake <= 10_000
  const priceValid = entryPrice > 0 && entryPrice < 1
  const formValid = stakeValid && priceValid
  const stakeError = !stakeValid ? "Mise doit être positive" : null
  const priceError = !priceValid ? "Prix entre 0 et 1" : null
  const showStakeError = touched.stake && stakeError
  const showPriceError = touched.price && priceError

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setTouched({ stake: true, price: true })
    if (!formValid) return
    const input: ManualPositionInput = {
      signalId: signal.id,
      direction,
      stake,
      entryPrice,
    }
    addManualPosition(input, signal)
    onSaved?.(input)
    setSaved(true)
    addToast({
      type: "success",
      title: "Position ajoutée au portfolio — voir",
      duration: 4000,
    })
    // NOTE: useToasts does not currently support action buttons.
    // We auto-navigate after the modal closes so the user lands on their
    // new position. TODO(x3): extend useToasts with an optional action slot.
    window.setTimeout(() => {
      onClose()
      navigate("/portfolio")
    }, 1500)
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-obsidian-950/80 backdrop-blur-sm"
            aria-hidden
          />

          {/* Dialog */}
          <div
            className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
          >
            <FocusLock returnFocus>
            <motion.div
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
              className="relative w-full max-w-lg overflow-hidden rounded-t-2xl border border-line-strong bg-obsidian-850 shadow-2xl sm:rounded-2xl"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-4 border-b border-line/60 px-5 py-4">
                <div>
                  <p className="mb-0.5 font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
                    Saisie manuelle
                  </p>
                  <h2 id={titleId} className="font-display text-title-sm font-semibold text-ink">
                    Enregistrer ma position
                  </h2>
                  <p className="mt-1 text-body-sm text-ink-muted">
                    Tu as acheté directement sur Polymarket{"\u00A0"}? Enregistre-la
                    ici pour qu{"\u2019"}elle apparaisse dans ton portfolio.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-ink-muted hover:bg-obsidian-800 hover:text-ink transition-premium cursor-pointer"
                  aria-label="Fermer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Body */}
              <form onSubmit={handleSubmit} className="px-5 py-5 space-y-5">
                {/* Signal summary */}
                <div className="rounded-xl border border-line/70 bg-obsidian-800/40 px-4 py-3">
                  <p className="mb-0.5 font-mono text-[0.625rem] uppercase tracking-[0.14em] text-ink-dim">
                    Signal
                  </p>
                  <p className="line-clamp-2 text-body-md font-medium text-ink">
                    {signal.question}
                  </p>
                  <p className="num mt-0.5 font-mono text-label-xs tracking-wider text-ink-dim">
                    {signal.id}
                  </p>
                </div>

                {/* Direction */}
                <fieldset>
                  <legend className="mb-1.5 block font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                    Direction prise
                  </legend>
                  <div role="radiogroup" aria-label="Direction prise" className="grid grid-cols-2 gap-2">
                    {DIRECTIONS.map((d, i) => {
                      const active = direction === d
                      const isYes = d === "YES"
                      return (
                        <button
                          key={d}
                          ref={(el) => {
                            directionRefs.current.set(d, el)
                          }}
                          type="button"
                          role="radio"
                          aria-checked={active}
                          tabIndex={active ? 0 : -1}
                          {...(i === 0 ? { "data-autofocus": true } : {})}
                          onClick={() => setDirection(d)}
                          onKeyDown={(e) => handleDirectionKey(d, e)}
                          className={cn(
                            "relative inline-flex h-11 items-center justify-center gap-2 rounded-lg border font-mono font-semibold tracking-wider transition-premium cursor-pointer",
                            active
                              ? isYes
                                ? "border-signal-yes/60 bg-signal-yes/10 text-signal-yes"
                                : "border-signal-no/60 bg-signal-no/10 text-signal-no"
                              : "border-line-strong bg-obsidian-800/60 text-ink-muted hover:text-ink hover:border-line/80",
                          )}
                        >
                          <span aria-hidden className="text-xs">
                            {isYes ? "▲" : "▼"}
                          </span>
                          {d}
                        </button>
                      )
                    })}
                  </div>
                </fieldset>

                {/* Amount + Entry price */}
                <div className="grid gap-4 sm:grid-cols-2">
                  {/* Stake */}
                  <div>
                    <label
                      htmlFor="manual-stake"
                      className="mb-1.5 flex items-center justify-between font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim"
                    >
                      <span>Mise (USDC)</span>
                      <span className="normal-case tracking-normal text-ink-dim">
                        ≈ {formatMoney(stake)}
                      </span>
                    </label>
                    <div className="relative">
                      <span
                        aria-hidden
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-body-sm text-ink-dim"
                      >
                        $
                      </span>
                      <input
                        id="manual-stake"
                        type="number"
                        inputMode="decimal"
                        min={1}
                        step={1}
                        value={stake}
                        onChange={(e) => setStake(Number(e.target.value) || 0)}
                        onBlur={() => setTouched((t) => ({ ...t, stake: true }))}
                        aria-invalid={showStakeError ? true : undefined}
                        aria-describedby={showStakeError ? stakeErrorId : undefined}
                        className={cn(
                          "num flex h-11 w-full rounded-md border bg-obsidian-800 pl-8 pr-3.5 text-right font-display text-base font-semibold tracking-tight text-ink focus-visible:outline-none focus-visible:ring-2",
                          showStakeError
                            ? "border-signal-no/60 focus-visible:ring-signal-no/25"
                            : "border-line-strong focus-visible:border-brand-500/60 focus-visible:ring-brand-500/20",
                        )}
                      />
                    </div>
                    {showStakeError && (
                      <p
                        id={stakeErrorId}
                        role="alert"
                        className="mt-1.5 text-body-sm text-signal-no"
                      >
                        {stakeError}
                      </p>
                    )}
                  </div>

                  {/* Entry price */}
                  <div>
                    <label
                      htmlFor="manual-price"
                      className="mb-1.5 block font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim"
                    >
                      Prix d{"\u2019"}entrée (0 - 1)
                    </label>
                    <input
                      id="manual-price"
                      type="number"
                      inputMode="decimal"
                      min={0.01}
                      max={0.99}
                      step={0.01}
                      value={entryPrice}
                      onChange={(e) => setEntryPrice(Number(e.target.value) || 0)}
                      onBlur={() => setTouched((t) => ({ ...t, price: true }))}
                      aria-invalid={showPriceError ? true : undefined}
                      aria-describedby={showPriceError ? priceErrorId : undefined}
                      className={cn(
                        "num flex h-11 w-full rounded-md border bg-obsidian-800 px-3.5 text-right font-display text-base font-semibold tracking-tight text-ink focus-visible:outline-none focus-visible:ring-2",
                        showPriceError
                          ? "border-signal-no/60 focus-visible:ring-signal-no/25"
                          : "border-line-strong focus-visible:border-brand-500/60 focus-visible:ring-brand-500/20",
                      )}
                    />
                    {showPriceError ? (
                      <p
                        id={priceErrorId}
                        role="alert"
                        className="mt-1 text-body-sm text-signal-no"
                      >
                        {priceError}
                      </p>
                    ) : (
                      <p className="mt-1 text-label-xs text-ink-dim">
                        Marché actuel : {signal.marketProbability.toFixed(2)}
                      </p>
                    )}
                  </div>
                </div>

                {/* Footer actions */}
                <div className="flex flex-col-reverse gap-2 border-t border-line/60 pt-4 sm:flex-row sm:justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="md"
                    onClick={onClose}
                    className="sm:w-auto"
                  >
                    Annuler
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    disabled={!formValid || saved}
                  >
                    {saved ? (
                      <>
                        <Check className="h-4 w-4" /> Enregistrée
                      </>
                    ) : (
                      "Enregistrer ma position"
                    )}
                  </Button>
                </div>
              </form>
            </motion.div>
            </FocusLock>
          </div>
        </>
      )}
    </AnimatePresence>
  )
}
