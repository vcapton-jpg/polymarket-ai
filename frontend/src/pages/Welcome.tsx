import { forwardRef, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS, STAGGER } from "@/lib/motion"
import { useCountUp } from "@/hooks/useCountUp"
import {
  ArrowRight,
  ArrowLeft,
  Compass,
  Activity,
  Flame,
  Sparkles,
  Target,
  Wallet,
  Check,
} from "lucide-react"
import { Logo } from "@/components/ui/Logo"
import { Button } from "@/components/ui/Button"
import { cn } from "@/lib/utils"
import { PROFILE_EXPLAINERS } from "@/pages/Apprendre"
import type { UserProfile } from "@/types/signal"

import { readAuth } from "@/lib/trial"
import { STORAGE_KEYS } from "@/lib/storageKeys"
import { putProfile } from "@/lib/api/auth"
import { ProfileToLearnTransition } from "@/components/welcome/ProfileToLearnTransition"

/** Mirrors the check in RequireAuth — uses the shared readAuth helper so
 *  the AuthState shape contract lives in exactly one file. */
function isAuthenticated(): boolean {
  const auth = readAuth()
  return Boolean(auth && auth.email)
}

type ProfileState = {
  type?: UserProfile["type"]
  experience?: UserProfile["experience"]
  reaction?: UserProfile["reaction"]
  budget?: UserProfile["budget"]
}

type OptionCard = {
  value: string
  label: string
  description: string
  icon: React.ElementType
}

const TYPES: OptionCard[] = [
  {
    value: "Découvreur",
    label: "Découvreur",
    description: "Je découvre les marchés de prédiction, je veux comprendre avant d’agir.",
    icon: Compass,
  },
  {
    value: "Actif",
    label: "Trader actif",
    description: "Je trade régulièrement sur Polymarket ou d’autres plateformes.",
    icon: Activity,
  },
  {
    value: "Confirmé",
    label: "Confirmé",
    description: "Je suis un trader confirmé, je cherche un edge de détection.",
    icon: Flame,
  },
]

const EXPERIENCE: OptionCard[] = [
  {
    value: "Jamais",
    label: "Jamais utilisé",
    description: "Je n’ai jamais passé d’ordre sur un marché de prédiction.",
    icon: Compass,
  },
  {
    value: "Un peu",
    label: "Quelques fois",
    description: "J’ai déjà joué sur quelques marchés, sans stratégie formelle.",
    icon: Activity,
  },
  {
    value: "Régulièrement",
    label: "Régulièrement",
    description: "Je trade plusieurs fois par semaine sur ces marchés.",
    icon: Flame,
  },
]

const REACTIONS: OptionCard[] = [
  {
    value: "Sors vite",
    label: "Je coupe vite pour limiter les dégâts",
    description: "Dès que le marché bouge contre moi, je coupe la position pour protéger le capital.",
    icon: ArrowLeft,
  },
  {
    value: "J'attends",
    label: "J’attends de voir si ça se stabilise",
    description: "J’attends 2 à 3 autres signaux qui confirment avant d’agir.",
    icon: Target,
  },
  {
    value: "Je renforce",
    label: "J’en profite pour renforcer ma position",
    description: "Si la conviction reste haute, j’en profite pour renforcer ma position.",
    icon: Flame,
  },
]

const BUDGETS: OptionCard[] = [
  {
    value: "<50€",
    label: "Moins de 50\u00A0€",
    description: "Je découvre avec des petits tickets pour apprendre.",
    icon: Wallet,
  },
  {
    value: "50-200€",
    label: "50\u00A0–\u00A0200\u00A0€",
    description: "Mon ticket standard — je trade sérieusement mais je reste mesuré.",
    icon: Target,
  },
  {
    value: ">200€",
    label: "Plus de 200\u00A0€",
    description: "Je trade avec des tickets significatifs — sizing fin essentiel.",
    icon: Flame,
  },
]

const STEP_META = [
  { eyebrow: "1 · Profil", title: "Qui es-tu\u00A0?", subtitle: "Pour calibrer le ton et la densité des signaux." },
  { eyebrow: "2 · Expérience", title: "Tu connais déjà Polymarket\u00A0?", subtitle: "On adapte la pédagogie à ton niveau." },
  { eyebrow: "3 · Réaction", title: "Ta réaction face à une baisse soudaine du marché", subtitle: "Un événement bouge le marché à l\u2019inverse de tes attentes. Tu fais quoi\u00A0?" },
  { eyebrow: "4 · Budget", title: "Quel est ton ticket habituel\u00A0?", subtitle: "Pour te suggérer un sizing réaliste." },
]

export default function Welcome() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [profile, setProfile] = useState<ProfileState>({})
  const [direction, setDirection] = useState<1 | -1>(1)
  // Bridge state for the Welcome → Apprendre cinematic transition.
  // Held inside Welcome (not pushed via navigate) so the recap card,
  // the badge, and the deck preview all live in the same React tree —
  // letting Framer's `layoutId` match the badge across components when
  // we eventually navigate, instead of yanking it across an unmount.
  const [transitioning, setTransitioning] = useState(false)

  const isRecap = step === 4
  const currentOptions = isRecap ? [] : [TYPES, EXPERIENCE, REACTIONS, BUDGETS][step]
  const currentKey = isRecap
    ? ("type" as const)
    : (["type", "experience", "reaction", "budget"] as const)[step]
  const currentValue = isRecap ? undefined : profile[currentKey]

  // Fix 14 — novices (Découvreur + Jamais) get softer, prospective wording on
  // step 3 so the onboarding doesn't assume prior trading reflexes.
  const isNovice = profile.type === "Découvreur" && profile.experience === "Jamais"
  const step3Title = isNovice
    ? "Si le marché se retournait, tu préférerais\u2026"
    : STEP_META[2].title
  const step3Subtitle = isNovice
    ? "On prépare ton premier réflexe."
    : STEP_META[2].subtitle
  const activeTitle = !isRecap && step === 2 ? step3Title : STEP_META[step]?.title
  const activeSubtitle = !isRecap && step === 2 ? step3Subtitle : STEP_META[step]?.subtitle

  const canNext = isRecap ? true : Boolean(currentValue)
  const isLastQuestion = step === 3

  const handleNext = () => {
    if (!canNext) return
    if (isRecap) {
      // Final CTA from recap → conditional route. Découvreurs go through
      // the learn hub first; everyone else jumps into signals.
      try {
        const raw = localStorage.getItem(STORAGE_KEYS.profile)
        const existing = raw ? JSON.parse(raw) : {}
        localStorage.setItem(
          STORAGE_KEYS.profile,
          JSON.stringify({ ...existing, completed: true }),
        )
      } catch {
        // Ignore — onboarding flag below is still authoritative.
      }
      // After the profile step → cinematic transition → Apprendre. We
      // mark onboarding as done here so a hard reload mid-transition
      // doesn't bounce the user back into the quiz; the actual navigate
      // is fired by ProfileToLearnTransition's onComplete callback (or
      // its auto-advance timer) so the user gets to see the deck
      // preview before the route change.
      localStorage.setItem(STORAGE_KEYS.onboarding, "done")
      setTransitioning(true)
      return
    }
    if (!isLastQuestion) {
      setDirection(1)
      setStep((s) => s + 1)
    } else {
      const sizing = deriveSizing(profile)
      localStorage.setItem(
        STORAGE_KEYS.profile,
        JSON.stringify({ ...profile, suggestedSizing: sizing }),
      )
      localStorage.setItem(STORAGE_KEYS.onboarding, "done")
      // Mirror the profile to the backend for multi-device parity. Fire-
      // and-forget — the authoritative copy is local until the next
      // /auth/me merge. For unauth'd users (rare on Welcome) this is a
      // silent no-op.
      void putProfile({
        type: profile.type,
        experience: profile.experience,
        reaction: profile.reaction,
        budget: profile.budget,
        suggested_sizing: sizing,
      }).catch(() => undefined)
      setDirection(1)
      setStep(4)
    }
  }

  const handleBack = () => {
    if (step === 0) {
      // If the user is already authed, "Retour" from step 0 should take
      // them back into the app (not back to /signup, which would be a
      // dead-end loop for existing users revisiting Welcome).
      const authed = isAuthenticated()
      navigate(authed ? "/signals" : "/signup")
      return
    }
    setDirection(-1)
    setStep((s) => (s === 4 ? 3 : s - 1))
  }

  const skip = () => {
    // "Passer" skips the optional profile quiz. With the L&T gates
    // removed, the user can now land directly on the signals feed —
    // Apprendre stays accessible from the nav for whenever they want
    // the educational on-ramp.
    localStorage.setItem(STORAGE_KEYS.onboarding, "skipped")
    navigate("/signals")
  }

  const select = (value: string) => {
    setProfile((p) => ({ ...p, [currentKey]: value }))
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-obsidian-950">
      {/* Cinematic post-recap overlay. Mounted within the same Welcome
          subtree so Framer's `layoutId` continuation can match the
          recap card → badge → Apprendre header anchor. The component
          owns its own timing + auto-advance; we just navigate when it
          calls back. */}
      {transitioning && (
        <ProfileToLearnTransition
          profileType={profile.type ?? "Actif"}
          onComplete={() => navigate("/apprendre", { state: { fromWelcome: true } })}
        />
      )}
      {/* Ambient backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-grid bg-grid-fade opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-[640px] w-[900px] -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: "radial-gradient(50% 50% at 50% 50%, rgba(11,224,166,0.10), transparent 70%)" }}
        aria-hidden
      />

      <div className="relative flex min-h-screen flex-col">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-5 md:px-10">
          <Logo />
          <button
            onClick={skip}
            className="text-body-sm text-ink-muted hover:text-ink transition-premium cursor-pointer"
          >
            Passer
          </button>
        </header>

        {/* Progress bar */}
        <div className="px-6 md:px-10">
          <div className="mx-auto max-w-[720px]">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
                {isRecap ? "Récap · Ton profil" : STEP_META[step].eyebrow}
              </span>
              <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                {isRecap ? "4 / 4 · Récap" : `${step + 1} / 4`}
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-line/60">
              <motion.div
                animate={{ width: `${isRecap ? 100 : ((step + 1) / 4) * 100}%` }}
                transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
                className="h-full bg-gradient-to-r from-brand-500 to-brand-300"
              />
            </div>
          </div>
        </div>

        {/* Main */}
        <main id="main" className="flex flex-1 items-center justify-center px-6 py-8 md:px-10 md:py-12">
          <div className="w-full max-w-[720px]">
            <AnimatePresence mode="wait" custom={direction}>
              <motion.div
                key={step}
                custom={direction}
                initial={{ opacity: 0, x: direction * 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: direction * -24 }}
                transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
              >
                {isRecap ? (
                  <RecapView profile={profile} onEdit={() => { setDirection(-1); setStep(0) }} />
                ) : (
                  <>
                    <div className="mb-8 text-center">
                      <h1
                        id={`welcome-q-${step}`}
                        className="font-display text-[1.875rem] font-semibold tracking-tight text-ink text-balance md:text-[2.25rem]"
                      >
                        {activeTitle}
                      </h1>
                      <p className="mt-2 text-[0.9375rem] text-ink-muted">{activeSubtitle}</p>
                    </div>

                    <OptionRadioGroup
                      options={currentOptions}
                      value={currentValue}
                      onSelect={select}
                      labelledBy={`welcome-q-${step}`}
                    />

                    {isLastQuestion && currentValue && (
                      <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.35, delay: 0.05 }}
                        className="mt-6 rounded-xl border border-brand-500/30 bg-brand-500/[0.05] p-4"
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <Sparkles className="h-4 w-4 text-brand-400" />
                          <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
                            Sizing calibré
                          </span>
                        </div>
                        <p className="text-[0.9375rem] leading-relaxed text-ink/90">
                          Sur chaque signal, on te suggérera{" "}
                          <span className="num font-semibold text-brand-300">{deriveSizing(profile)}</span>{" "}
                          {profile.reaction === "Je renforce"
                            ? "avec une option de renforcement en cas de confirmation."
                            : profile.reaction === "Sors vite"
                              ? "avec une alerte claire dès que le score baisse."
                              : "avec les 2 à 3 confirmations attendues avant action."}
                        </p>
                      </motion.div>
                    )}
                  </>
                )}
              </motion.div>
            </AnimatePresence>

            {/* Nav */}
            <div className="mt-8 flex items-center justify-between gap-3">
              {step > 0 ? (
                <button
                  onClick={handleBack}
                  className="inline-flex items-center gap-1.5 text-body-md text-ink-muted hover:text-ink transition-premium cursor-pointer"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Retour
                </button>
              ) : (
                <span aria-hidden />
              )}

              <Button
                onClick={handleNext}
                disabled={!canNext}
                variant="primary"
                size="lg"
                className="min-w-[180px]"
              >
                {isRecap ? (
                  <>
                    <Check className="h-4 w-4" />
                    {profile.type === "Découvreur"
                      ? "Commencer par comprendre"
                      : "Voir mes premiers signaux"}
                  </>
                ) : isLastQuestion ? (
                  <>
                    Continuer
                    <ArrowRight className="h-4 w-4" />
                  </>
                ) : (
                  <>
                    Continuer
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </main>

        <footer className="px-6 pb-6 text-center text-label-sm text-ink-dim md:px-10">
          Signal informatif · Pas un conseil financier · © 2026 Foresight
        </footer>
      </div>
    </div>
  )
}

function OptionRadioGroup({
  options,
  value,
  onSelect,
  labelledBy,
}: {
  options: OptionCard[]
  value: string | undefined
  onSelect: (v: string) => void
  labelledBy: string
}) {
  const refs = useRef<Map<string, HTMLButtonElement | null>>(new Map())
  // Roving tabindex: selected option is tabbable; if none selected, first is.
  const selectedIndex = options.findIndex((o) => o.value === value)
  const rovingIndex = selectedIndex >= 0 ? selectedIndex : 0

  const handleKey = (e: React.KeyboardEvent<HTMLButtonElement>, idx: number) => {
    if (
      e.key !== "ArrowLeft" &&
      e.key !== "ArrowRight" &&
      e.key !== "ArrowUp" &&
      e.key !== "ArrowDown"
    ) {
      return
    }
    e.preventDefault()
    const dir = e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1
    const nextIdx = (idx + dir + options.length) % options.length
    const next = options[nextIdx]
    onSelect(next.value)
    refs.current.get(next.value)?.focus()
  }

  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="grid gap-3 md:gap-4">
      {options.map((opt, i) => (
        <OptionButton
          key={opt.value}
          ref={(el) => {
            refs.current.set(opt.value, el)
          }}
          option={opt}
          active={value === opt.value}
          tabIndex={i === rovingIndex ? 0 : -1}
          onClick={() => onSelect(opt.value)}
          onKeyDown={(e) => handleKey(e, i)}
        />
      ))}
    </div>
  )
}

const OptionButton = forwardRef<HTMLButtonElement, {
  option: OptionCard
  active: boolean
  onClick: () => void
  tabIndex?: number
  onKeyDown?: (e: React.KeyboardEvent<HTMLButtonElement>) => void
}>(function OptionButton({ option, active, onClick, tabIndex, onKeyDown }, ref) {
  const Icon = option.icon
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      onKeyDown={onKeyDown}
      role="radio"
      aria-checked={active}
      tabIndex={tabIndex}
      className={cn(
        "group relative flex items-start gap-4 rounded-xl border p-4 md:p-5 text-left transition-premium cursor-pointer",
        active
          ? "border-brand-500/50 bg-brand-500/[0.06] shadow-brand-glow"
          : "border-line-strong bg-obsidian-850/50 hover:border-line-strong hover:bg-obsidian-800/60",
      )}
    >
      <span
        className={cn(
          "grid h-10 w-10 shrink-0 place-items-center rounded-lg border transition-premium",
          active
            ? "border-brand-500/40 bg-brand-500/10 text-brand-300"
            : "border-line bg-obsidian-800 text-ink-muted",
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="flex-1 min-w-0">
        <span className="block font-display text-body-lg font-medium text-ink">
          {option.label}
        </span>
        <span className="mt-0.5 block text-body-md text-ink-muted">{option.description}</span>
      </span>
      <span
        className={cn(
          "mt-1 grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-premium",
          active ? "border-brand-400 bg-brand-500 text-obsidian-900" : "border-line-strong",
        )}
        aria-hidden
      >
        {active && <Check className="h-3 w-3" />}
      </span>
    </button>
  )
})

function deriveSizing(p: ProfileState): string {
  const base =
    p.budget === "<50€"
      ? "5\u00A0–\u00A015\u00A0€"
      : p.budget === "50-200€"
        ? "20\u00A0–\u00A050\u00A0€"
        : "80\u00A0–\u00A0150\u00A0€"
  if (p.reaction === "Je renforce") return `${base} + renfort`
  return base
}

/** Upper-bound of suggested sizing in euros — used for the count-up reveal. */
function deriveSizingTarget(p: ProfileState): number {
  if (p.budget === "<50€") return 15
  if (p.budget === "50-200€") return 50
  return 150
}

/** Letter-by-letter reveal. Splits on chars, preserves NBSP, wraps each in a span. */
function AnimatedLetters({
  text,
  className,
  staggerChildren,
}: {
  text: string
  className?: string
  staggerChildren: number
}) {
  const container = {
    hidden: {},
    visible: {
      transition: { staggerChildren, delayChildren: 0.05 },
    },
  }
  const child = {
    hidden: { opacity: 0, y: 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: DURATIONS.default, ease: EASE_PREMIUM },
    },
  }
  return (
    <>
      <motion.span
        aria-hidden="true"
        className={className}
        variants={container}
        initial="hidden"
        animate="visible"
      >
        {Array.from(text).map((ch, i) => (
          <motion.span
            key={`${ch}-${i}`}
            variants={child}
            aria-hidden
            className="inline-block"
            style={{ whiteSpace: "pre" }}
          >
            {ch === " " ? "\u00A0" : ch}
          </motion.span>
        ))}
      </motion.span>
      <span className="sr-only">{text}</span>
    </>
  )
}

function RecapView({
  profile,
  onEdit,
}: {
  profile: ProfileState
  onEdit: () => void
}) {
  // Types guaranteed once we reach recap (step 4 is only reachable after 4 selections),
  // but keep a defensive fallback so React never renders `undefined`.
  const profileType = profile.type ?? "Actif"
  const experience = profile.experience ?? "—"
  const reaction = profile.reaction ?? "—"
  const budget = profile.budget ?? "—"
  const sizing = deriveSizing(profile)
  const sizingTarget = deriveSizingTarget(profile)
  const explainer = PROFILE_EXPLAINERS[profileType] ?? PROFILE_EXPLAINERS.Actif
  const reduced = useReducedMotion()

  // Count-up for the sizing upper bound — ~900ms, respects reduced-motion.
  const { ref: countRef, display: sizingCount } = useCountUp(sizingTarget, {
    duration: reduced ? 0 : 900,
    decimals: 0,
  })

  // TODO: confetti — add `canvas-confetti` dep for an optional celebratory burst.

  return (
    <div>
      <div className="mb-8 text-center">
        <AnimatedLetters
          text="Ton profil"
          staggerChildren={reduced ? 0 : STAGGER.hero}
          className="mb-2 block font-mono text-eyebrow uppercase tracking-[0.18em] text-brand-400"
        />
        <h1 className="font-display text-[1.875rem] font-semibold tracking-tight text-ink text-balance md:text-[2.25rem]">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              duration: reduced ? 0 : DURATIONS.default,
              delay: reduced ? 0 : 0.25,
              ease: EASE_PREMIUM,
            }}
          >
            Tu es{" "}
            <span className="bg-gradient-to-r from-brand-300 via-brand-400 to-brand-500 bg-clip-text font-bold text-transparent">
              {profileType}
            </span>
            .
          </motion.span>
        </h1>
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: reduced ? 0 : DURATIONS.default,
            delay: reduced ? 0 : 0.45,
            ease: EASE_PREMIUM,
          }}
          className="mx-auto mt-3 max-w-xl text-[0.9375rem] leading-relaxed text-ink-muted"
        >
          {explainer}
        </motion.p>
      </div>

      {/* Profile card — fade + scale + pulsing brand-glow on arrival */}
      <motion.div
        initial={{ opacity: 0, scale: 0.94, boxShadow: "0 0 0 rgba(11,224,166,0)" }}
        animate={{
          opacity: 1,
          scale: 1,
          boxShadow: reduced
            ? "0 0 0 rgba(11,224,166,0)"
            : [
                "0 0 0 rgba(11,224,166,0)",
                "0 0 48px rgba(11,224,166,0.35)",
                "0 0 16px rgba(11,224,166,0.18)",
              ],
        }}
        transition={{
          duration: reduced ? 0 : DURATIONS.expressive,
          delay: reduced ? 0 : 0.3,
          ease: EASE_PREMIUM,
          boxShadow: { duration: reduced ? 0 : 1.4, times: [0, 0.55, 1] },
        }}
        className="rounded-xl border border-line-strong bg-obsidian-850/60 divide-y divide-line/60 shadow-brand-glow"
      >
        <RecapRow label="Expérience" value={experience} />
        <RecapRow label="Réaction préférée" value={reaction} />
        <RecapRow label="Budget" value={budget} />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: reduced ? 0 : DURATIONS.default,
          delay: reduced ? 0 : 0.7,
          ease: EASE_PREMIUM,
        }}
        className="mt-4 inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/[0.06] px-3 py-1.5"
      >
        <Sparkles className="h-3.5 w-3.5 text-brand-400" aria-hidden />
        <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
          Sizing calibré
        </span>
        <span className="num text-body-sm font-semibold text-ink">
          {/* Count-up target (upper-bound €) for impact, full range in title */}
          <span
            ref={countRef}
            className="inline-block"
            title={sizing}
            aria-label={sizing}
          >
            jusqu{"\u2019"}à {sizingCount}{"\u00A0"}€
          </span>
        </span>
      </motion.div>

      <div className="mt-6 text-center">
        <button
          type="button"
          onClick={onEdit}
          className="text-body-sm text-ink-muted hover:text-ink underline-offset-4 hover:underline transition-premium cursor-pointer"
        >
          Modifier mes réponses
        </button>
      </div>
    </div>
  )
}

function RecapRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 md:px-5 md:py-3.5">
      <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
        {label}
      </span>
      <span className="text-[0.9375rem] font-medium text-ink">{value}</span>
    </div>
  )
}
