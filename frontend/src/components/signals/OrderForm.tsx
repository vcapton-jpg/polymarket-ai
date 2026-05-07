import { useEffect, useId, useMemo, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowUpRight, Check, ChevronRight, Sparkles, TriangleAlert, X } from "lucide-react"
import type { OrderDraft, Signal, UserProfile } from "@/types/signal"
import { Button } from "@/components/ui/Button"
import { useUserPreferences } from "@/lib/userPreferences"
import { useProfile, getAmountPresets, getDefaultAmount } from "@/lib/useProfile"
import { useToasts } from "@/lib/useToasts"
import { withBuilderCode } from "@/lib/polymarket"
import { DURATIONS, EASE_PREMIUM, useMotionConfig } from "@/lib/motion"
import { cn } from "@/lib/utils"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { PoweredByPolymarket } from "./PoweredByPolymarket"
import {
  MIN_AMOUNT,
  MAX_AMOUNT,
  USD_TO_EUR,
  computeOrderMath,
  isAmountValid,
  parseAmountInput,
} from "@/lib/orderMath"
import { SESSION_KEYS, STORAGE_KEYS } from "@/lib/storageKeys"
import { ApiError } from "@/lib/api/client"
import {
  fetchClobMarketInfo,
  recordOrder,
  type ClobMarketInfo,
} from "@/lib/api/clobTrading"
import { useIsFreePlan } from "@/hooks/useAuth"
import { hasToken } from "@/lib/api/auth"
import { useClobClient } from "@/hooks/useClobClient"
import { useWalletSetup } from "@/hooks/useWalletSetup"
import { WalletSetupModal } from "@/components/trading/WalletSetupModal"

type Direction = "YES" | "NO"
const DIRECTIONS: readonly Direction[] = ["YES", "NO"] as const

type OrderFormProps = {
  signal: Signal
  /** Open the manual-entry modal when the user prefers to log an off-platform trade. */
  onManualEntry?: () => void
  /** Called on successful (mocked) submit. Cursor wires the CLOB client here. */
  onSubmit?: (draft: OrderDraft) => void
  className?: string
}

type ProfileType = UserProfile["type"]

type SizingRange = { type: string; low: number; high: number; pct: string }

const SIZING_BY_TYPE: Record<ProfileType, SizingRange> = {
  Découvreur: { type: "Découvreur", low: 10, high: 25, pct: "2\u20135\u00A0% de ton capital" },
  Actif: { type: "profil Actif", low: 25, high: 100, pct: "5\u201310\u00A0% de ton capital" },
  Confirmé: { type: "Confirmé", low: 100, high: 500, pct: "sizing libre selon conviction" },
}

function buildSizingHint(profileType: ProfileType, currency: "USD" | "EUR"): string {
  const r = SIZING_BY_TYPE[profileType] ?? SIZING_BY_TYPE.Actif
  const usdRange = `${r.low}\u2013${r.high}\u00A0USDC`
  if (currency === "EUR") {
    const euroLow = Math.round(r.low * USD_TO_EUR)
    const euroHigh = Math.round(r.high * USD_TO_EUR)
    const euroRange = `\u2248\u00A0${euroLow}\u2013${euroHigh}\u00A0\u20AC`
    return `Mise suggérée pour un ${r.type}\u00A0: ${usdRange} (${euroRange}) \u2014 ${r.pct}.`
  }
  return `Mise suggérée pour un ${r.type}\u00A0: ${usdRange} \u2014 ${r.pct}.`
}

/**
 * Native Polymarket execution UI (Builder Program).
 *
 * This is the primary CTA on SignalDetail. Foresight places the order via
 * Polymarket's CLOB on the user's behalf — the UI is purely the composer.
 * Actual CLOB submission is backend scope; we log the draft for now.
 */
export function OrderForm({ signal, onManualEntry, onSubmit, className }: OrderFormProps) {
  const { t } = useTranslation()
  const { formatMoney, currency } = useUserPreferences()
  const profile = useProfile()
  const navigate = useNavigate()
  const { addToast } = useToasts()

  const amountPresets = useMemo(() => getAmountPresets(profile), [profile])
  const sizingHint = useMemo(
    () => buildSizingHint(profile.type, currency === "EUR" ? "EUR" : "USD"),
    [profile.type, currency],
  )

  // Onboarding-completion detection. Authoritative source is the
  // `foresight.onboarding` flag (Welcome writes "done" / "skipped"). If the
  // user skipped (or hasn't finished) we show the sizing personalisation
  // nudge — otherwise we hide it.
  const [onboardingComplete, setOnboardingComplete] = useState<boolean>(true)
  const [nudgeDismissed, setNudgeDismissed] = useState<boolean>(false)
  useEffect(() => {
    try {
      setOnboardingComplete(
        window.localStorage.getItem(STORAGE_KEYS.onboarding) === "done",
      )
    } catch {
      setOnboardingComplete(true)
    }
    try {
      setNudgeDismissed(
        window.sessionStorage.getItem(SESSION_KEYS.sizingNudgeDismissed) === "1",
      )
    } catch {
      // ignore
    }
  }, [])
  const dismissNudge = () => {
    setNudgeDismissed(true)
    try {
      window.sessionStorage.setItem(SESSION_KEYS.sizingNudgeDismissed, "1")
    } catch {
      // ignore
    }
  }

  const [direction, setDirection] = useState<Direction>(signal.direction)
  // Amount is a controlled STRING so an empty field stays empty instead of
  // coercing to 0 and rendering "-$0.00" in the Perte grid. We parse on
  // every render for the math, and on submit for validation.
  const [amountRaw, setAmountRaw] = useState<string>(() => String(getDefaultAmount(profile)))
  const [submitted, setSubmitted] = useState(false)
  const [touched, setTouched] = useState(false)
  // Re-hydrate the default when the profile hydrates asynchronously (first
  // paint may see the default profile before the stored one loads).
  useEffect(() => {
    setAmountRaw((prev) => (prev === "" ? String(getDefaultAmount(profile)) : prev))
  }, [profile])

  const motionConfig = useMotionConfig("default")
  const quickMotion = useMotionConfig("quick")
  const errorId = useId()

  // Direction (radiogroup) — roving tabindex refs.
  const directionRefs = useRef<Map<Direction, HTMLButtonElement | null>>(new Map())
  const handleDirectionKey = (d: Direction, e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "ArrowUp" && e.key !== "ArrowDown") return
    e.preventDefault()
    const next: Direction = d === "YES" ? "NO" : "YES"
    setDirection(next)
    directionRefs.current.get(next)?.focus()
  }

  // Amount presets (radiogroup) — roving tabindex refs.
  const presetRefs = useRef<Map<number, HTMLButtonElement | null>>(new Map())
  const handlePresetKey = (
    p: number,
    presets: readonly number[],
    e: React.KeyboardEvent<HTMLButtonElement>,
  ) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) return
    const currentIndex = presets.indexOf(p)
    if (currentIndex === -1) return
    e.preventDefault()
    let next = currentIndex
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (currentIndex + 1) % presets.length
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp")
      next = (currentIndex - 1 + presets.length) % presets.length
    else if (e.key === "Home") next = 0
    else if (e.key === "End") next = presets.length - 1
    const nextVal = presets[next]
    setAmountRaw(String(nextVal))
    presetRefs.current.get(nextVal)?.focus()
  }

  const pricePerShare = signal.marketProbability
  // Derive numeric amount from the controlled string input. `null` (empty
  // field) folds to 0 for display purposes, but isAmountValid() still rejects
  // it so submit is blocked.
  const amount = parseAmountInput(amountRaw) ?? 0
  const { shares, estimatedReturn } = useMemo(
    () => computeOrderMath(amount, pricePerShare),
    [amount, pricePerShare],
  )

  const isContrarian = direction !== signal.direction
  const amountValid = isAmountValid(amount)
  const amountError = !amountValid
    ? amount < MIN_AMOUNT
      ? `Mise minimum\u00A0: ${MIN_AMOUNT}\u00A0USDC.`
      : `Mise maximum\u00A0: ${MAX_AMOUNT.toLocaleString("fr-FR")}\u00A0USDC.`
    : null
  const showError = touched && !!amountError

  // Navigate-after-success timeout. Ref so we can clear on unmount to avoid
  // setting state / navigating on an unmounted form.
  const navTimeoutRef = useRef<number | null>(null)
  useEffect(() => {
    return () => {
      if (navTimeoutRef.current !== null) {
        window.clearTimeout(navTimeoutRef.current)
      }
    }
  }, [])

  const isFreePlan = useIsFreePlan()
  const {
    walletConnected,
    safeAddress,
    step: walletStep,
    error: walletError,
    startSetup,
  } = useWalletSetup()
  const [showWalletModal, setShowWalletModal] = useState(false)
  // CLOB client — null until wallet+safe ready. The hook recreates on
  // safeAddress change so we never hold a stale funder.
  const { client: clobClient, ready: clobReady, reason: clobReason } = useClobClient({
    safeAddress,
  })

  // L&T per-signal stake limits + cooloff blocker were removed
  // 2026-04-27 (per-signal spending caps were not earning their UX cost
  // and were preventing legitimate trades). The legacy USDC input is
  // now the only stake-input path. Free-plan paywalls + Pro-tier
  // gating remain enforced — only the per-signal stake cap is gone.

  /** Extract the `market_id` path segment from a Polymarket URL so the
   *  trade request can reach the right CLOB market. URL shape is
   *  `https://polymarket.com/market/<id>` or `.../event/<id>`. */
  const extractMarketId = (url: string): string | null => {
    const match = url.match(/\/(?:market|event)\/([^/?#]+)/i)
    return match ? match[1] : null
  }

  /**
   * Non-custodial trade execution (Polymarket Builder pattern, post-2026-05-08
   * pivot). Replaces the prior `placeTrade()` custodial flow that tried to
   * sign orders server-side with BUILDER_PRIVATE_KEY (rejected by Polymarket
   * because our deployer Safes don't authorize that key as a signer).
   *
   * Steps:
   *   1. Resolve token_id (YES/NO) and trading params from the backend.
   *   2. Ask the user's MetaMask to sign the order via clobClient (popup).
   *   3. clob-client posts the signed order to clob.polymarket.com,
   *      attaching our HMAC builder headers via /api/polymarket/sign.
   *   4. On success: persist Order via /api/trading/orders/record so the
   *      portfolio + worker poll see it. Show real polymarket_order_id.
   *   5. On any failure: surface the actual error (no more
   *      "ordre en local uniquement" silent-fallback that wrote a fake
   *      Position to localStorage).
   */
  const executeTrade = async () => {
    // Free plan guard: Score 90+ signals are Pro-only. Send users with
    // a reachable /signup flow to /pricing instead of the Stripe path.
    if (isFreePlan && signal.score >= 90) {
      addToast({
        type: "info",
        title: "Signal exceptionnel réservé à Pro",
        description: "Passe Pro pour exécuter sur les signaux Score 90+.",
      })
      navigate("/pricing?plan=pro")
      return
    }

    if (!hasToken()) {
      addToast({
        type: "info",
        title: "Connexion requise",
        description: "Connecte-toi pour passer un ordre.",
      })
      return
    }

    if (!clobReady || !clobClient) {
      // Most likely the wallet is connected but the Safe isn't ready
      // yet, OR walletClient is still rehydrating. Re-open the wallet
      // modal — it covers all of those cases (deploy, reconnect, etc.).
      setShowWalletModal(true)
      addToast({
        type: "info",
        title: "Wallet pas prêt",
        description: clobReason ?? "Connecte ton wallet pour exécuter.",
        duration: 4000,
      })
      return
    }

    const marketId = extractMarketId(signal.polymarketUrl)
    if (!marketId) {
      addToast({
        type: "info",
        title: "Market introuvable",
        description: "Impossible de lire l'identifiant Polymarket de ce signal.",
      })
      return
    }

    const draft: OrderDraft = {
      signalId: signal.id,
      direction,
      amount,
      pricePerShare,
      estimatedShares: shares,
      estimatedReturn,
    }
    onSubmit?.(draft)
    setSubmitted(true)

    const signalIdNum = /^\d+$/.test(signal.id) ? Number(signal.id) : undefined

    let info: ClobMarketInfo
    try {
      info = await fetchClobMarketInfo(marketId)
    } catch (err) {
      setSubmitted(false)
      if (err instanceof ApiError && err.status === 404) {
        addToast({
          type: "info",
          title: "Market introuvable",
          description: "Ce market n'est pas (encore) référencé côté Foresight.",
        })
        return
      }
      addToast({
        type: "info",
        title: "Lookup market échoué",
        description: err instanceof Error ? err.message : String(err),
      })
      return
    }

    const tokenId =
      direction === "YES" ? info.yes_token_id : info.no_token_id
    if (!tokenId) {
      setSubmitted(false)
      addToast({
        type: "info",
        title: "Token Polymarket manquant",
        description: `Le côté ${direction} n'a pas de token_id (market non-binaire ou corrompu).`,
      })
      return
    }

    if (!info.accepting_orders) {
      setSubmitted(false)
      addToast({
        type: "info",
        title: "Market fermé",
        description: "Polymarket n'accepte plus d'ordre sur ce market.",
      })
      return
    }

    // Build the order args using the EXACT shape clob-client expects.
    // We submit a market order (FOK) for amount-based execution. If we
    // ever expose limit orders in the UI, switch to GTC and pass `price`
    // + `size` instead of `amount`.
    let orderResp: { success?: boolean; orderID?: string; errorMsg?: string }
    try {
      // Lazy require — avoids pulling clob-client into pages that don't
      // open the OrderForm.
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const clob = require("@polymarket/clob-client") as typeof import("@polymarket/clob-client")

      // Limit order on the user's stated `pricePerShare` — the user
      // already saw the slippage estimate in the form so honouring the
      // stated price is the right behaviour.
      orderResp = await clobClient.createAndPostOrder(
        {
          tokenID: tokenId,
          price: pricePerShare,
          size: amount,
          side: clob.Side.BUY,
          feeRateBps: 0,
          // builder_code attribution: clob-client splices it from
          // BuilderConfig set up in useClobClient. No need to pass here.
        },
        { tickSize: info.tick_size as "0.1" | "0.01" | "0.001" | "0.0001", negRisk: info.neg_risk },
        clob.OrderType.GTC,
      )
    } catch (err) {
      setSubmitted(false)
      // Distinguish "user rejected in MetaMask" from genuine failures.
      const msg = err instanceof Error ? err.message : String(err)
      const userRejected = /user (rejected|denied)|action_rejected/i.test(msg)
      addToast({
        type: "info",
        title: userRejected ? "Ordre annulé" : "Erreur signature",
        description: userRejected
          ? "Tu as annulé la signature dans MetaMask."
          : msg,
        duration: userRejected ? 3000 : 6000,
      })
      return
    }

    if (!orderResp.success || !orderResp.orderID) {
      setSubmitted(false)
      addToast({
        type: "info",
        title: "Ordre rejeté par Polymarket",
        description: orderResp.errorMsg ?? "Polymarket n'a pas accepté l'ordre.",
        duration: 6000,
      })
      return
    }

    const polymarketOrderId = orderResp.orderID

    // Persist the order metadata so the worker fill-poller picks it up
    // and the Portfolio sees it. Failure here is NOT fatal — the user's
    // money is already moving; surface a soft warning.
    try {
      const recordRes = await recordOrder({
        market_id: marketId,
        polymarket_order_id: polymarketOrderId,
        direction,
        token_id: tokenId,
        size: amount,
        price: pricePerShare,
        order_type: "GTC",
        signal_id: signalIdNum,
      })
      if (!recordRes.success) {
        // Backend rejected the record (e.g., 403 cooloff). The Polymarket
        // order is already on the book — we cannot un-do it. Inform the
        // user clearly so they know what state they're in.
        addToast({
          type: "info",
          title: "Ordre placé, suivi local indisponible",
          description:
            recordRes.error ??
            "Ton ordre est sur Polymarket, mais Foresight ne pourra pas le suivre dans le Portfolio. Voir polymarket.com.",
          duration: 6000,
        })
      }
    } catch (err) {
      // Non-fatal — log and continue. The order EXISTS on Polymarket;
      // recordOrder() failure means our local view is just incomplete.
      console.warn("recordOrder failed:", err)
      addToast({
        type: "info",
        title: "Ordre placé sur Polymarket",
        description:
          "Le suivi dans Foresight pourrait être incomplet. ID Polymarket : " +
          polymarketOrderId.slice(0, 12) +
          "…",
        duration: 6000,
      })
    }

    addToast({
      type: "success",
      title: "Ordre envoyé à Polymarket",
      description: `ID ${polymarketOrderId.slice(0, 16)}…`,
      duration: 3000,
    })

    // Navigate to portfolio so the user sees the order list + (when the
    // worker poll lands) the materialised position. No more
    // optimistic-fake position in localStorage.
    navTimeoutRef.current = window.setTimeout(() => {
      navTimeoutRef.current = null
      navigate("/portfolio")
    }, 1500)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!amountValid) return

    if (!walletConnected) {
      setShowWalletModal(true)
      return
    }

    void executeTrade()
  }

  const handleWalletSuccess = () => {
    setShowWalletModal(false)
    if (amountValid) {
      void executeTrade()
    }
  }

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={motionConfig}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-brand-500/30",
        "bg-gradient-to-br from-brand-500/[0.06] via-obsidian-850/80 to-obsidian-900",
        "p-5 md:p-6",
        className,
      )}
    >
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-brand-500/40 bg-brand-500/10">
            <Sparkles className="h-4 w-4 text-brand-400" />
          </div>
          <div>
            <h2 className="font-display text-body-lg font-semibold text-ink">
              Parier sur ce marché
            </h2>
            <p className="text-body-sm text-ink-muted">
              Exécution directe via Polymarket — aucun redirect.
            </p>
          </div>
        </div>
        <span className="inline-flex h-6 items-center rounded-full border border-brand-500/40 bg-brand-500/10 px-2 text-[0.625rem] font-mono uppercase tracking-wider text-brand-300">
          Native
        </span>
      </div>

      {/* Direction toggle */}
      <fieldset className="mb-4">
        <legend className="mb-1.5 block font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
          Direction
        </legend>
        <div
          role="radiogroup"
          aria-label="Direction"
          className="grid grid-cols-2 gap-2"
        >
          {DIRECTIONS.map((d) => {
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
                onClick={() => setDirection(d)}
                onKeyDown={(e) => handleDirectionKey(d, e)}
                className={cn(
                  "relative inline-flex h-11 items-center justify-center gap-2 rounded-lg border font-mono font-semibold tracking-wider transition-premium cursor-pointer",
                  active
                    ? isYes
                      ? "border-signal-yes/60 bg-signal-yes/10 text-signal-yes shadow-[0_0_0_1px_rgba(34,197,94,0.25)]"
                      : "border-signal-no/60 bg-signal-no/10 text-signal-no shadow-[0_0_0_1px_rgba(239,68,68,0.25)]"
                    : "border-line-strong bg-obsidian-800/60 text-ink-muted hover:text-ink hover:border-line/80",
                )}
              >
                <span aria-hidden className="text-xs">
                  {isYes ? "▲" : "▼"}
                </span>
                BUY {d}
              </button>
            )
          })}
        </div>
        {isContrarian && (
          <p className="mt-2 inline-flex items-start gap-1.5 text-label-sm text-signal-amber">
            <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
            Le signal recommande <span className="font-semibold">{signal.direction}</span> — tu
            achètes à contre-courant.
          </p>
        )}
      </fieldset>

      <div className="mb-4">
        <label
          htmlFor="order-amount"
          className="mb-1.5 flex items-center justify-between font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim"
        >
          <span>{t("orderForm.stakeLabel")}</span>
          <span className="normal-case tracking-normal text-ink-dim">
            ≈ {formatMoney(amount)}
          </span>
        </label>
        <div className="relative mb-2">
          <span
            aria-hidden
            className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-body-sm text-ink-dim"
          >
            $
          </span>
          <input
            id="order-amount"
            type="number"
            inputMode="decimal"
            min={MIN_AMOUNT}
            max={MAX_AMOUNT}
            step={1}
            value={amountRaw}
            onChange={(e) => setAmountRaw(e.target.value)}
            onBlur={() => setTouched(true)}
            onFocus={(e) => {
              // Caret at the right edge of the value (`100|`), not the
              // left (`|100`) — matches the right-aligned visual of the
              // input. `<input type=number>` rejects `setSelectionRange`
              // in some browsers (Safari throws InvalidStateError), so
              // we defer + try/catch and fall back to select-all.
              const el = e.currentTarget
              requestAnimationFrame(() => {
                try {
                  const len = el.value.length
                  el.setSelectionRange(len, len)
                } catch {
                  el.select()
                }
              })
            }}
            aria-invalid={showError || undefined}
            aria-describedby={showError ? errorId : undefined}
            className={cn(
              "num flex h-11 w-full rounded-md border bg-obsidian-800 pl-8 pr-3.5 text-right font-display text-lg font-semibold tracking-tight text-ink",
              "placeholder:text-ink-dim",
              "transition-premium",
              showError
                ? "border-signal-no/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-no/25"
                : "border-line-strong focus-visible:outline-none focus-visible:border-brand-500/60 focus-visible:ring-2 focus-visible:ring-brand-500/20",
            )}
            aria-label={t("orderForm.amountAria")}
          />
        </div>
        <AnimatePresence initial={false}>
          {showError && amountError && (
            <motion.p
              key="order-amount-error"
              id={errorId}
              role="alert"
              initial={{ opacity: 0, y: -2 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -2 }}
              transition={quickMotion}
              className="mt-1.5 text-body-sm text-signal-no"
            >
              {amountError}
            </motion.p>
          )}
        </AnimatePresence>
        <div
          role="radiogroup"
          aria-label={t("orderForm.presetsAria")}
          className="flex flex-wrap gap-1.5"
        >
          {amountPresets.map((p) => {
            const active = amount === p && amountRaw !== ""
            return (
              <button
                key={p}
                ref={(el) => {
                  presetRefs.current.set(p, el)
                }}
                type="button"
                role="radio"
                aria-checked={active}
                tabIndex={active ? 0 : -1}
                onClick={() => setAmountRaw(String(p))}
                onKeyDown={(e) => handlePresetKey(p, amountPresets, e)}
                className={cn(
                  "num inline-flex h-7 items-center rounded-full border px-2.5 font-mono text-label-xs transition-premium cursor-pointer",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40",
                  active
                    ? "border-brand-500/40 bg-brand-500/10 text-brand-300"
                    : "border-line bg-obsidian-800/60 text-ink-muted hover:text-ink hover:border-line-strong",
                )}
              >
                ${p}
              </button>
            )
          })}
        </div>
        <div className="mt-2 flex items-start gap-2 rounded-md border border-brand-500/20 bg-brand-500/[0.04] px-3 py-2 text-body-sm text-ink">
          <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-brand-400" aria-hidden />
          <div className="flex-1 min-w-0">
            <p className="font-medium text-ink">{sizingHint}</p>
            {!onboardingComplete && !nudgeDismissed && (
              <div className="mt-1 flex items-start gap-2">
                <p className="flex-1 text-body-sm text-ink-muted">
                  Ce sizing est générique —{" "}
                  <Link
                    to="/welcome"
                    className="text-brand-400 underline-offset-2 hover:underline"
                  >
                    Personnalise en 30{"\u00A0"}sec →
                  </Link>
                </p>
                <button
                  type="button"
                  onClick={dismissNudge}
                  aria-label="Masquer cette suggestion"
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-dim hover:bg-obsidian-700 hover:text-ink transition-premium cursor-pointer"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Honest Gain/Perte — 2-up equal prominence */}
      <div className="mb-2 grid grid-cols-2 gap-3">
        <div className="rounded-md border border-signal-yes/20 bg-signal-yes/5 p-4">
          <p className="text-label-sm text-ink-readable">{t("orderForm.gainIf")}</p>
          <p className="num mt-1 text-title-md font-semibold text-signal-yes">
            {amountRaw === "" ? "\u2014" : `+$${Math.max(estimatedReturn, 0).toFixed(2)}`}
          </p>
        </div>
        <div className="rounded-md border border-signal-no/20 bg-signal-no/5 p-4">
          <p className="text-label-sm text-ink-readable">{t("orderForm.lossIf")}</p>
          <p className="num mt-1 text-title-md font-semibold text-signal-no">
            {amountRaw === "" ? "\u2014" : `-$${amount.toFixed(2)}`}
          </p>
        </div>
      </div>
      <p className="mb-1 text-label-sm text-ink-dim">{t("orderForm.feesNote")}</p>
      {/* Risk disclosure (DEC-005 + AMF). Same prominence as the Perte
          panel above so the user cannot miss the total-loss framing.
          Required by audit P0-8 (2026-04-27). */}
      <p
        role="note"
        className="mb-2 text-label-sm font-medium text-signal-no"
      >
        {t("orderForm.totalLossWarning")}
      </p>
      <p className="num mb-5 text-label-sm text-ink-dim">
        {shares > 0 ? shares.toFixed(1) : "\u2014"} parts à ${pricePerShare.toFixed(2)}
      </p>

      {/* Submit */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        disabled={!amountValid || submitted}
        className="w-full"
      >
        {submitted ? (
          <>
            <Check className="h-4 w-4" /> {t("orderForm.submittedCta")}
          </>
        ) : (
          <>
            Acheter {shares > 0 ? shares.toFixed(1) : "—"} parts {direction}
            <ChevronRight className="h-4 w-4" />
          </>
        )}
      </Button>

      {/* Success toast */}
      <AnimatePresence>
        {submitted && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: DURATIONS.quick, ease: EASE_PREMIUM }}
            className="mt-3 rounded-md border border-signal-yes/40 bg-signal-yes/10 px-3.5 py-2 text-body-sm text-signal-yes"
            role="status"
          >
            Position {direction} ouverte sur Polymarket · suis-la dans ton portfolio.
          </motion.div>
        )}
      </AnimatePresence>

      {/* Escape hatches — two secondary paths for users who don't want to
          execute natively right now. Kept inside the position-taking zone so
          users never have to hunt for them. The Polymarket link carries our
          builder code so external trades still attribute to Foresight. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <a
          href={withBuilderCode(signal.polymarketUrl)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-body-sm text-ink-muted hover:text-ink underline-offset-4 hover:underline transition-premium cursor-pointer"
        >
          Voir le marché sur Polymarket
          <ArrowUpRight className="h-3.5 w-3.5" />
        </a>
        {onManualEntry && (
          <button
            type="button"
            onClick={onManualEntry}
            className="inline-flex items-center gap-1 text-body-sm text-ink-muted hover:text-ink underline-offset-4 hover:underline transition-premium cursor-pointer"
          >
            J’ai déjà pris position ailleurs
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Footer: partnership line + disclaimer + badge */}
      <div className="mt-4 flex flex-col gap-2 border-t border-line/60 pt-3">
        <p className="inline-flex items-center gap-1.5 text-label-xs leading-relaxed text-ink-dim">
          <span>Exécution via notre partenariat Polymarket Builder Program.</span>
          <InfoTooltip
            label="À propos du Builder Program"
            message="Foresight touche une commission Polymarket sur tes trades — c’est comme ça qu’on reste gratuit."
          />
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-label-xs leading-relaxed text-ink-dim">
            Ordre informatif · signe la transaction Polymarket depuis ton wallet.
          </p>
          <PoweredByPolymarket size="xs" />
        </div>
      </div>
      <WalletSetupModal
        open={showWalletModal}
        onSuccess={handleWalletSuccess}
        onClose={() => setShowWalletModal(false)}
        step={walletStep}
        error={walletError}
        startSetup={startSetup}
      />
    </motion.form>
  )
}

