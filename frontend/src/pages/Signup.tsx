import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useEffect, useRef, useState } from "react"
import { Check, ChevronDown, Eye, EyeOff, Loader2, Sparkles } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { AuthShell } from "@/components/layout/AuthShell"
import { SignalCard } from "@/components/signals/SignalCard"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { MOCK_SIGNALS } from "@/data/signals"
import { cn } from "@/lib/utils"
import { writeAuth, type AuthState } from "@/lib/trial"
import { STORAGE_KEYS } from "@/lib/storageKeys"
import { registerApi, setToken, fetchMe } from "@/lib/api/auth"
import { meToAuthState } from "@/hooks/useAuth"
import { ApiError } from "@/lib/api/client"
import { useMotionConfig } from "@/lib/motion"
import { useToasts } from "@/lib/useToasts"

const SIGNUP_DRAFT_EMAIL_KEY = STORAGE_KEYS.signupDraftEmail

type PlanKey = "free" | "pro" | "api"

const PLAN_COPY: Record<PlanKey, { name: string; price: string; tag: string }> = {
  free: { name: "Free", price: "0\u00A0€", tag: "Pas de carte bancaire" },
  pro: { name: "Pro", price: "29\u00A0€ / mois", tag: "Populaire" },
  api: { name: "API", price: "99\u00A0€ / mois", tag: "Intégration API" },
}

const PROMISES = [
  // De-anglicised: "upgrade" → "passe Pro"
  "5 signaux / jour en Free, passe Pro quand tu veux",
  "Dashboard complet dès l’inscription",
  "Aucune carte bancaire requise",
  "Annulable à tout moment",
]

export default function Signup() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  // Default to Pro when no plan param is present — users land here via
  // "Essayer Pro" CTAs. Only fall back to Free if the user explicitly
  // picked it (?plan=free) or passed an unknown value.
  const rawPlan = params.get("plan") as PlanKey | null
  // Default signup plan is Free unless the user explicitly arrived via a
  // "?plan=pro" CTA. Free-first keeps the signup frictionless.
  const resolvedInitialPlan: PlanKey =
    rawPlan && ["free", "pro", "api"].includes(rawPlan) ? rawPlan : "free"
  const [plan, setPlan] = useState<PlanKey>(resolvedInitialPlan)

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [accept, setAccept] = useState(false)
  const [age18, setAge18] = useState(false)
  const [cguAccepted, setCguAccepted] = useState(false)
  // Legal-PR-1 B3 — declared country at signup. Default empty so the
  // user must explicitly pick (we don't want to default-trust "FR" for a
  // US user landing on the page). Server cross-checks this against
  // `cf-ipcountry` and refuses blocked jurisdictions with HTTP 451.
  const [country, setCountry] = useState<string>("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const motionConfig = useMotionConfig("quick")
  const { addToast } = useToasts()

  // Recover an in-flight signup email draft so users who bounced out don't
  // have to retype. Only hydrates when the field is empty — never clobbers
  // a user's current input.
  useEffect(() => {
    try {
      const draft = localStorage.getItem(SIGNUP_DRAFT_EMAIL_KEY)
      if (draft && draft.trim()) {
        setEmail((prev) => {
          if (prev) return prev
          addToast({
            type: "info",
            title: "On a retrouvé ton\u00A0email — continue ton inscription.",
          })
          return draft
        })
      }
    } catch {
      // ignore — draft recovery is best-effort
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Guard every post-await setState so the unmount-during-submit race
  // doesn't leak React state updates into an already-detached tree.
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password || !accept || !age18 || !cguAccepted || !country) return
    setError(null)
    setLoading(true)
    // Normalise to the two plan states the backend understands.
    // "api" signups fall through as "pro" (same gated features + card later).
    const planForAuth: AuthState["plan"] = plan === "free" ? "free" : "pro"
    try {
      const { token, user } = await registerApi(email, password, planForAuth, {
        age_confirmed_18: true,
        country_residence: country,
      })
      setToken(token)
      // Seed AuthState from the registration response (has plan +
      // trial_ends_at already), then hydrate in background to pick up any
      // server-side overrides (preferences, profile, etc.).
      const initial: AuthState = {
        email: user.email ?? email,
        plan: user.plan === "pro" ? "pro" : "free",
        trial_ends_at: user.trial_ends_at ?? undefined,
        card_attached: user.card_attached,
        has_ever_signed_up: true,
      }
      writeAuth(initial)
      void fetchMe().then((me) => {
        if (me) writeAuth(meToAuthState(me))
      })
      localStorage.setItem(STORAGE_KEYS.onboarding, "pending")
      try {
        localStorage.removeItem(SIGNUP_DRAFT_EMAIL_KEY)
      } catch {
        // ignore
      }
      if (mountedRef.current) setLoading(false)
      navigate("/welcome")
    } catch (err) {
      if (!mountedRef.current) return
      if (err instanceof ApiError && err.status === 409) {
        setError("Cet email est déjà inscrit. Connecte-toi plutôt.")
      } else if (err instanceof ApiError) {
        setError(err.message || "Inscription impossible. Réessaie.")
      } else {
        setError("Inscription impossible. Vérifie tes informations ou réessaie.")
      }
      setLoading(false)
    }
  }

  return (
    <AuthShell
      visual={
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-label-sm font-mono uppercase tracking-[0.18em] text-brand-400">
            <Sparkles className="h-3.5 w-3.5" />
            Aperçu du produit
          </div>

          <SignalCard signal={MOCK_SIGNALS[0]} className="shadow-elevated" />

          <ul className="space-y-2.5 pl-1 text-body-sm text-ink-muted">
            {PROMISES.map((p) => (
              <li key={p} className="flex items-start gap-2.5">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
                <span>{p}</span>
              </li>
            ))}
          </ul>

        </div>
      }
      footer={
        <>
          En créant un compte, tu acceptes nos{" "}
          <Link to="/cgu" className="underline decoration-line-strong hover:text-ink">CGU</Link>
          {" · "}© 2026 Foresight
        </>
      }
    >
      <div className="mb-7">
        <p className="mb-2 font-mono text-eyebrow uppercase text-brand-400">Créer un compte</p>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-ink md:text-[2.25rem]">
          On commence.
        </h1>
        <p className="mt-2 text-[0.9375rem] text-ink-muted">
          30 secondes chrono. Zéro carte bancaire.
        </p>
        {plan === "pro" && (
          // Trial callout — explicit auto-downgrade promise so the user
          // knows nothing auto-charges at the end of the 7 days.
          <p className="mt-3 rounded-lg border border-brand-500/30 bg-brand-500/5 px-3.5 py-2.5 text-body-sm leading-relaxed text-ink-muted">
            <span className="font-medium text-brand-300">Essaie Pro.</span>{" "}
            {"7\u00A0jours gratuits · Aucune carte requise · Passe Free automatiquement à la fin de l\u2019essai"}
          </p>
        )}
      </div>

      {/* Plan selector */}
      <div
        role="radiogroup"
        aria-label="Choix du plan"
        className="mb-5 grid grid-cols-3 gap-1.5 rounded-xl border border-line-strong bg-obsidian-850/50 p-1.5"
      >
        {(Object.keys(PLAN_COPY) as PlanKey[]).map((k) => {
          const active = plan === k
          const isPro = k === "pro"
          return (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={active}
              tabIndex={active ? 0 : -1}
              onClick={() => setPlan(k)}
              onKeyDown={(e) => {
                if (
                  e.key !== "ArrowLeft" &&
                  e.key !== "ArrowRight" &&
                  e.key !== "ArrowUp" &&
                  e.key !== "ArrowDown"
                ) {
                  return
                }
                e.preventDefault()
                const keys = Object.keys(PLAN_COPY) as PlanKey[]
                const idx = keys.indexOf(plan)
                const dir = e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1
                const next = keys[(idx + dir + keys.length) % keys.length]
                setPlan(next)
              }}
              className={cn(
                "relative flex flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left transition-premium cursor-pointer",
                active && isPro
                  ? "bg-brand-500/15 ring-1 ring-brand-500/40 shadow-inset-line"
                  : active
                    ? "bg-obsidian-700 shadow-inset-line"
                    : isPro
                      ? "hover:bg-brand-500/10 ring-1 ring-brand-500/20"
                      : "hover:bg-obsidian-800/70",
              )}
            >
              <span className={cn(
                "text-body-sm font-semibold",
                active && isPro ? "text-brand-300" : active ? "text-ink" : isPro ? "text-brand-400/80" : "text-ink-muted",
              )}>
                {PLAN_COPY[k].name}
              </span>
              <span className={cn(
                "num text-label-xs",
                active && isPro ? "text-brand-400/70" : "text-ink-dim",
              )}>
                {PLAN_COPY[k].price}
              </span>
              {isPro && (
                <span className={cn(
                  "text-[0.625rem] font-medium leading-none",
                  active ? "text-brand-400" : "text-brand-500/60",
                )}>
                  7 jours offerts
                </span>
              )}
            </button>
          )
        })}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-body-sm font-medium text-ink">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="toi@exemple.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => {
              // Persist a draft email on blur so users who bounce out
              // don't lose their progress. Cleared on successful signup.
              const trimmed = email.trim()
              if (!trimmed) return
              try {
                localStorage.setItem(SIGNUP_DRAFT_EMAIL_KEY, trimmed)
              } catch {
                // ignore
              }
            }}
            required
            aria-describedby={error ? "signup-error" : undefined}
            aria-invalid={error ? true : undefined}
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-body-sm font-medium text-ink">
            Mot de passe
          </label>
          <div className="relative">
            <Input
              id="password"
              type={showPw ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Au moins 8 caractères"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="pr-10"
              aria-describedby={error ? "signup-error" : undefined}
              aria-invalid={error ? true : undefined}
            />
            <button
              type="button"
              onClick={() => setShowPw((s) => !s)}
              className="absolute right-1 top-1/2 -translate-y-1/2 grid h-9 w-9 place-items-center rounded-md text-ink-dim hover:text-ink hover:bg-obsidian-700 transition-premium cursor-pointer"
              aria-label={showPw ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            >
              {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="pt-1">
          <label className="flex items-start gap-2.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={accept}
              onChange={(e) => setAccept(e.target.checked)}
              required
              className={cn(
                "mt-0.5 h-4 w-4 rounded border-line-strong bg-obsidian-800 text-brand-500",
                "focus:ring-2 focus:ring-brand-500/30 focus:ring-offset-0 cursor-pointer",
              )}
            />
            <span className="text-body-sm leading-relaxed text-ink-muted">
              {"J\u2019ai compris que Foresight est un outil d\u2019analyse — je reste libre de mes décisions."}
            </span>
          </label>
          {/* Legal-PR-3 (H5): le disclaimer total-loss était caché derrière
              un toggle "En savoir plus" — l'AMF exige une prominence
              équivalente à celle des claims gain. Maintenant visible
              direct, sans interaction requise. */}
          <p
            id="risk-disclosure"
            className="ml-[1.625rem] mt-2 rounded-lg border border-signal-amber/30 bg-signal-amber/[0.06] px-3.5 py-3 text-label-sm leading-relaxed text-ink-muted"
          >
            <strong className="text-signal-amber">{"Risque de perte totale."}</strong>{" "}
            {"Foresight fournit des signaux informatifs issus d\u2019une analyse de sources ouvertes. Nous n\u2019exécutons pas d\u2019ordre en ton nom ni ne te conseillons de parier sur ce marché spécifique. Les marchés de prédiction comportent un risque de perte partielle ou totale. Tu prends chaque décision, en connaissance de cause."}
          </p>
        </div>

        {/* Legal-PR-1 B3 — declared country of residence. Server enforces
            blocked jurisdictions (US/UK/sanctions) with HTTP 451 and
            cross-checks against `cf-ipcountry` if Cloudflare is in front. */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="signup-country" className="text-body-sm text-ink-muted">
            {"Pays de résidence"}
          </label>
          <select
            id="signup-country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            required
            className={cn(
              "h-11 rounded-md border border-line-strong bg-obsidian-800 px-3 text-body-md text-ink",
              "focus:outline-none focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20",
              "cursor-pointer",
            )}
          >
            <option value="" disabled>
              {"Choisis ton pays de résidence"}
            </option>
            <option value="FR">France</option>
            <option value="BE">Belgique</option>
            <option value="CH">Suisse</option>
            <option value="LU">Luxembourg</option>
            <option value="MC">Monaco</option>
            <option value="DE">Allemagne</option>
            <option value="ES">Espagne</option>
            <option value="IT">Italie</option>
            <option value="NL">Pays-Bas</option>
            <option value="PT">Portugal</option>
            <option value="IE">Irlande</option>
            <option value="AT">Autriche</option>
            <option value="DK">Danemark</option>
            <option value="SE">Suède</option>
            <option value="FI">Finlande</option>
            <option value="NO">Norvège</option>
            <option value="PL">Pologne</option>
            <option value="CZ">Tchéquie</option>
            <option value="GR">Grèce</option>
            <option value="HU">Hongrie</option>
            <option value="RO">Roumanie</option>
            <option value="OTHER">{"Autre / non listé"}</option>
          </select>
          <p className="text-label-sm text-ink-dim">
            {"L’accès est interdit depuis certaines juridictions (États-Unis, Royaume-Uni, pays sous sanctions)."}
          </p>
        </div>

        <label className="flex items-start gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={age18}
            onChange={(e) => setAge18(e.target.checked)}
            required
            className={cn(
              "mt-0.5 h-4 w-4 rounded border-line-strong bg-obsidian-800 text-brand-500",
              "focus:ring-2 focus:ring-brand-500/30 focus:ring-offset-0 cursor-pointer",
            )}
          />
          <span className="text-body-sm leading-relaxed text-ink-muted">
            {"J\u2019ai 18 ans ou plus. Les marchés prédictifs peuvent me faire perdre de l\u2019argent."}
          </span>
        </label>

        <label className="flex items-start gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={cguAccepted}
            onChange={(e) => setCguAccepted(e.target.checked)}
            required
            className={cn(
              "mt-0.5 h-4 w-4 rounded border-line-strong bg-obsidian-800 text-brand-500",
              "focus:ring-2 focus:ring-brand-500/30 focus:ring-offset-0 cursor-pointer",
            )}
          />
          <span className="text-body-sm leading-relaxed text-ink-muted">
            {"J\u2019accepte les "}
            <a href="/cgu" target="_blank" className="underline">CGU</a>
            {", la "}
            <a href="/risques" target="_blank" className="underline">politique de risque</a>
            {" et la "}
            <a href="/confidentialite" target="_blank" className="underline">politique de confidentialité</a>
            {"."}
          </span>
        </label>

        {error && (
          <p id="signup-error" role="alert" className="text-signal-no text-body-sm mb-2">
            {error}
          </p>
        )}

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="w-full mt-2"
          disabled={loading || !email || !password || !accept || !age18 || !cguAccepted || !country}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Création du compte…
            </>
          ) : (
            `Créer mon compte ${PLAN_COPY[plan].name}`
          )}
        </Button>
      </form>

      <div className="my-7 flex items-center gap-3">
        <div className="h-px flex-1 bg-line/60" />
        <span className="text-label-xs font-mono uppercase tracking-[0.14em] text-ink-dim">ou</span>
        <div className="h-px flex-1 bg-line/60" />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <OAuthButton provider="google" />
        <OAuthButton provider="twitter" />
      </div>

      <p className="mt-8 text-center text-body-md text-ink-muted">
        {"Tu as déjà un compte\u00A0? "}
        <Link to="/login" className="font-medium text-brand-400 hover:text-brand-300 transition-premium">
          Se connecter
        </Link>
      </p>
    </AuthShell>
  )
}

function OAuthButton({ provider }: { provider: "google" | "twitter" }) {
  const label = provider === "google" ? "Google" : "X / Twitter"
  return (
    <button
      type="button"
      className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line-strong bg-obsidian-800 text-body-md font-medium text-ink hover:border-brand-500/40 hover:bg-obsidian-700 transition-premium cursor-pointer"
    >
      {provider === "google" ? <GoogleIcon /> : <XIcon />}
      {label}
    </button>
  )
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden>
      <path d="M21.35 11.1H12v2.85h5.37c-.23 1.4-1.66 4.1-5.37 4.1a5.95 5.95 0 1 1 0-11.9c1.86 0 3.1.8 3.82 1.48l2.6-2.5C16.66 3.54 14.55 2.6 12 2.6 6.84 2.6 2.65 6.79 2.65 12S6.84 21.4 12 21.4c6.94 0 9.53-4.88 9.53-8.5 0-.57-.06-1.04-.18-1.8z" fill="#E8EAED" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.503 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zM17.08 19.77h1.833L7.084 4.126H5.117L17.08 19.77z" />
    </svg>
  )
}
