import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useState } from "react"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { AuthShell } from "@/components/layout/AuthShell"
import { SignalCard } from "@/components/signals/SignalCard"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { MOCK_SIGNALS } from "@/data/signals"
import { cn } from "@/lib/utils"
import { usePublicStats } from "@/hooks/usePublicStats"
import { EMPTY_STAT_PLACEHOLDER, formatStat } from "@/lib/stats"
import { readAuth, writeAuth } from "@/lib/trial"
import { STORAGE_KEYS } from "@/lib/storageKeys"
import { loginApi, setToken, fetchMe } from "@/lib/api/auth"
import { meToAuthState } from "@/hooks/useAuth"
import { ApiError } from "@/lib/api/client"

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // Legal-PR-3 (B8): live counter from /api/stats/public so we never
  // brag about a market count that doesn't match the database.
  const { data: publicStats } = usePublicStats()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setError(null)
    setLoading(true)
    try {
      const { token, user } = await loginApi(email, password)
      setToken(token)
      // Preserve has_ever_signed_up across logout cycles so returning
      // users keep the right entry point if they log out again.
      const existing = readAuth()
      writeAuth({
        email: user.email ?? email,
        plan: user.plan === "pro" ? "pro" : "free",
        trial_ends_at: user.trial_ends_at ?? undefined,
        card_attached: user.card_attached,
        has_ever_signed_up: existing?.has_ever_signed_up ?? true,
      })
      void fetchMe().then((me) => {
        if (me) writeAuth(meToAuthState(me))
      })

      const next = searchParams.get("next")
      const onboarding = localStorage.getItem(STORAGE_KEYS.onboarding)
      if (next) {
        navigate(next)
      } else if (onboarding !== "done" && onboarding !== "skipped") {
        navigate("/welcome")
      } else {
        navigate("/signals")
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Identifiants incorrects. Réessaie ou crée un compte.")
      } else if (err instanceof ApiError) {
        setError(err.message || "Connexion impossible. Réessaie.")
      } else {
        setError("Connexion impossible. Vérifie ta connexion et réessaie.")
      }
      setLoading(false)
    }
  }

  return (
    <AuthShell
      visual={
        <div className="space-y-5">
          <div className="flex items-center gap-2 text-label-sm font-mono uppercase tracking-[0.18em] text-brand-400">
            <span className="relative inline-flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-ping motion-reduce:animate-none rounded-full bg-brand-500 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-500" />
            </span>
            Signal live · il y a 2 min
          </div>
          <SignalCard signal={MOCK_SIGNALS[0]} variant="compact" className="shadow-elevated" />
          <p className="pl-1 text-body-sm leading-relaxed text-ink-muted">
            Pendant que tu lis ça, le pipeline surveille{" "}
            <span className="num font-medium text-ink">
              {publicStats
                ? formatStat(publicStats.markets_monitored)
                : EMPTY_STAT_PLACEHOLDER}
            </span>{" "}
            marchés Polymarket. Dès qu’un signal est détecté, il atterrit ici.
          </p>
        </div>
      }
      footer={<>© 2026 Foresight</>}
    >
      <div className="mb-8">
        <p className="mb-2 font-mono text-eyebrow uppercase text-brand-400">Bienvenue</p>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-ink md:text-[2.25rem]">
          Se connecter
        </h1>
        <p className="mt-2 text-[0.9375rem] text-ink-muted">
          Retrouve tes signaux et ton historique.
        </p>
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
            required
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="block text-body-sm font-medium text-ink">
              Mot de passe
            </label>
            <Link
              to="#"
              className="text-label-sm text-brand-400 hover:text-brand-300 transition-premium"
            >
              {"Oublié\u00A0?"}
            </Link>
          </div>
          <div className="relative">
            <Input
              id="password"
              type={showPw ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="pr-10"
              aria-describedby={error ? "login-error" : undefined}
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

        <label htmlFor="remember-me" className="flex items-center gap-2 cursor-pointer select-none">
          <input
            id="remember-me"
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className={cn(
              "h-4 w-4 rounded border-line-strong bg-obsidian-800 text-brand-500",
              "focus:ring-2 focus:ring-brand-500/30 focus:ring-offset-0 cursor-pointer",
            )}
          />
          <span className="text-body-sm text-ink-muted">Se souvenir de moi</span>
        </label>

        {error && (
          <p id="login-error" role="alert" className="text-signal-no text-body-sm mb-2">
            {error}
          </p>
        )}

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="w-full mt-2"
          disabled={loading || !email || !password}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Connexion…
            </>
          ) : (
            "Se connecter"
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
        {"Pas encore de compte\u00A0? "}
        <Link to="/signup" className="font-medium text-brand-400 hover:text-brand-300 transition-premium">
          Créer un compte
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
