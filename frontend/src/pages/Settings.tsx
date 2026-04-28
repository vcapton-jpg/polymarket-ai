import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import {
  Mail,
  Send,
  Bell,
  SlidersHorizontal,
  Cookie,
  Crown,
  LogOut,
  Trash2,
  Check,
  ExternalLink,
  Sparkles,
  Edit3,
} from "lucide-react"
import { AppShell } from "@/components/layout/AppShell"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { PaywallChip } from "@/components/ui/PaywallChip"
import {
  getNotificationPermission,
  requestNotificationPermission,
  supportsNotifications,
} from "@/lib/notifications"
import { useToasts } from "@/lib/useToasts"
import { cn } from "@/lib/utils"
import {
  clearAuth,
  formatTrialEndFR,
  isOnTrial,
  trialEndDate,
  type AuthState as TrialAuthState,
} from "@/lib/trial"
import { deleteAccountApi, logoutApi } from "@/lib/api/auth"
import { openStripePortal } from "@/lib/api/subscriptions"
import { revoke as revokeConsent } from "@/lib/cookieConsent"
import { STORAGE_KEYS, AUTH_CHANGED_EVENT } from "@/lib/storageKeys"
import ConfirmDeleteAccountModal from "@/components/modals/ConfirmDeleteAccountModal"
import type { UserProfile } from "@/types/signal"

type AuthState = {
  email: string
  plan: "free" | "pro" | "api"
  createdAt?: string
  trial_ends_at?: string
  card_attached?: boolean
}

const CATEGORIES = [
  { value: "geopolitics", label: "🌍 Géopolitique" },
  { value: "politics", label: "🏛️ Politique" },
  { value: "economics", label: "📈 Économie" },
  { value: "crypto", label: "₿ Crypto" },
  { value: "sports", label: "⚽ Sport" },
  { value: "science", label: "🔬 Science" },
]

const SCORE_THRESHOLDS = [
  { value: 0, label: "Tous" },
  { value: 60, label: "60+" },
  { value: 75, label: "75+" },
  { value: 90, label: "90+" },
]

const DIRECTIONS = [
  { value: "all", label: "Tous" },
  { value: "YES", label: "▲ YES" },
  { value: "NO", label: "▼ NO" },
]

const TOC_SECTIONS: Array<{ id: string; labelKey: string }> = [
  { id: "section-identite", labelKey: "settings.toc.identity" },
  { id: "section-profil", labelKey: "settings.toc.tradingProfile" },
  { id: "section-notifications", labelKey: "settings.toc.notifications" },
  { id: "section-filtres", labelKey: "settings.toc.defaultFilters" },
  { id: "section-plan", labelKey: "settings.toc.planBilling" },
  { id: "section-danger", labelKey: "settings.toc.dangerZone" },
]

const PLAN_COPY = {
  free: { name: "Free", price: "0\u00A0€", limit: "5 signaux / jour" },
  pro: { name: "Pro", price: "29\u00A0€ / mois", limit: "Illimité" },
  api: { name: "API", price: "99\u00A0€ / mois", limit: "Illimité + API" },
}

export default function Settings() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { addToast } = useToasts()

  const [confirmDelete, setConfirmDelete] = useState(false)
  const [auth, setAuth] = useState<AuthState>({ email: "—", plan: "free" })
  const [profile, setProfile] = useState<Partial<UserProfile>>({})
  const [telegramConnected, setTelegramConnected] = useState(false)
  const [emailNotif, setEmailNotif] = useState(true)
  const [emailThreshold, setEmailThreshold] = useState(75)
  const [pushNotif, setPushNotif] = useState(false)
  const [pushPermission, setPushPermission] = useState<NotificationPermission>(
    getNotificationPermission(),
  )
  const [defaultScore, setDefaultScore] = useState(0)
  const [defaultDirection, setDefaultDirection] = useState<string>("all")
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    CATEGORIES.map((c) => c.value),
  )
  const [saved, setSaved] = useState(false)
  const [signalsUsed] = useState(3)
  const [activeTocId, setActiveTocId] = useState<string | null>(
    TOC_SECTIONS[0]?.id ?? null,
  )
  const observedRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    try {
      const authRaw = localStorage.getItem(STORAGE_KEYS.auth)
      if (authRaw) {
        // Spread into the default so missing fields (e.g. `plan`) stay
        // defaulted — older sessions may have persisted auth without a
        // plan, and we never want that to crash the page lookup below.
        const parsed = JSON.parse(authRaw)
        setAuth((prev) => ({ ...prev, ...parsed }))
      }
      const profileRaw = localStorage.getItem(STORAGE_KEYS.profile)
      if (profileRaw) setProfile(JSON.parse(profileRaw))
      const settingsRaw = localStorage.getItem("foresight.settings")
      if (settingsRaw) {
        const s = JSON.parse(settingsRaw)
        if (typeof s.telegramConnected === "boolean") setTelegramConnected(s.telegramConnected)
        if (typeof s.emailNotif === "boolean") setEmailNotif(s.emailNotif)
        if (typeof s.emailThreshold === "number") setEmailThreshold(s.emailThreshold)
        if (typeof s.pushNotif === "boolean") setPushNotif(s.pushNotif)
        if (typeof s.defaultScore === "number") setDefaultScore(s.defaultScore)
        if (typeof s.defaultDirection === "string") setDefaultDirection(s.defaultDirection)
        if (Array.isArray(s.selectedCategories)) setSelectedCategories(s.selectedCategories)
      }
    } catch {
      // ignore
    }
  }, [])

  // Highlight the visible section in the right-rail TOC.
  useEffect(() => {
    const elements = TOC_SECTIONS
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null)
    if (!elements.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
        if (visible[0]?.target.id) {
          setActiveTocId(visible[0].target.id)
        }
      },
      { rootMargin: "-30% 0px -55% 0px", threshold: [0, 0.25, 0.5, 1] },
    )
    elements.forEach((el) => observer.observe(el))
    observedRef.current = observer
    return () => observer.disconnect()
  }, [])

  const save = () => {
    try {
      localStorage.setItem(
        "foresight.settings",
        JSON.stringify({
          telegramConnected,
          emailNotif,
          emailThreshold,
          pushNotif,
          defaultScore,
          defaultDirection,
          selectedCategories,
        }),
      )
      setSaved(true)
      setTimeout(() => setSaved(false), 1800)
      addToast({ type: "success", title: t("settings.savedToast") })
    } catch {
      addToast({
        type: "info",
        title: "Impossible d'enregistrer. Vérifie que le navigateur accepte le stockage local.",
      })
    }
    // Mirror notification preferences to the backend for multi-device
    // parity. Fire-and-forget; unauth'd users silently no-op on 401.
    import("@/lib/api/auth")
      .then(({ putPreferences }) =>
        putPreferences({
          notif_email: emailNotif,
          notif_push: pushNotif,
          notif_telegram: telegramConnected,
        }).catch(() => undefined),
      )
      .catch(() => undefined)
  }

  const toggleCategory = (v: string) => {
    setSelectedCategories((prev) =>
      prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v],
    )
  }

  /**
   * Toggles the browser-push preference. When enabling from scratch we
   * must request the Web Notification permission on user gesture —
   * browsers reject the prompt if it's not invoked from a click handler.
   * If the user denies, we revert the toggle to keep the UI honest.
   */
  const togglePushNotif = async (next: boolean) => {
    if (!next) {
      setPushNotif(false)
      return
    }
    if (!supportsNotifications()) {
      addToast({
        type: "info",
        title: "Notifications non disponibles",
        description: "Ton navigateur ne supporte pas les notifications.",
      })
      return
    }
    const permission = await requestNotificationPermission()
    setPushPermission(permission)
    if (permission === "granted") {
      setPushNotif(true)
      addToast({
        type: "success",
        title: "Alertes navigateur activées",
        description: "Tu seras prévenu dès qu’une position passe en\u00A0«\u00A0vendre\u00A0».",
      })
    } else {
      setPushNotif(false)
      addToast({
        type: "info",
        title: "Permission refusée",
        description:
          "Active les notifications dans les réglages de ton navigateur pour cette page.",
      })
    }
  }

  const logout = () => {
    try {
      // clearAuth() keeps `has_ever_signed_up` so returning users get
      // routed to /login (not /signup) on next visit, and dispatches
      // AUTH_CHANGED_EVENT so in-tab subscribers (AppShell, TrialBanner,
      // ProUpsellCTA gate) re-render immediately. Fire-and-forget the
      // backend /auth/logout so the server can invalidate the session
      // even if the local clear already happened.
      clearAuth()
      void logoutApi().catch(() => undefined)
      localStorage.removeItem(STORAGE_KEYS.profile)
      localStorage.removeItem(STORAGE_KEYS.onboarding)
    } catch {
      addToast({
        type: "info",
        title: "Impossible d'enregistrer. Vérifie que le navigateur accepte le stockage local.",
      })
    }
    navigate("/login")
  }

  // Defensive fallback: if localStorage contains a legacy auth payload
  // without a `plan` field, coalesce to "free" so the page never renders
  // with an undefined plan lookup.
  const planInfo = PLAN_COPY[auth.plan] ?? PLAN_COPY.free
  const quota = (auth.plan ?? "free") === "free" ? { used: signalsUsed, max: 5 } : null

  // Trial visibility shares the same predicate used by TrialBanner so the
  // two surfaces never disagree. We narrow to the canonical AuthState shape
  // (free|pro only) before handing to the helper.
  const trialAuth: TrialAuthState | null =
    auth.plan === "pro" || auth.plan === "free"
      ? {
          email: auth.email,
          plan: auth.plan,
          trial_ends_at: auth.trial_ends_at,
          card_attached: auth.card_attached,
        }
      : null
  const onTrial = isOnTrial(trialAuth)
  const trialEnd = trialEndDate(trialAuth)

  return (
    <AppShell breadcrumb={[{ label: t("settings.breadcrumb") }]} showLive={true}>
      <div className="mx-auto grid max-w-[1080px] gap-8 px-4 py-8 md:px-6 md:py-12 lg:grid-cols-[minmax(0,720px)_220px]">
        <div>
        <motion.header
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.default }}
          className="mb-8"
        >
          <p className="mb-2 font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
            Compte
          </p>
          <h1 className="font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2rem]">
            Réglages
          </h1>
          <p className="mt-1.5 text-[0.9375rem] text-ink-muted">
            Profile, notifications et filtres par défaut.
          </p>
        </motion.header>

        <div className="space-y-5">
          {/* COMPTE */}
          <Section
            id="section-identite"
            eyebrow="01 · Identité"
            title="Compte"
            subtitle="Email et mot de passe."
          >
            <div className="space-y-4">
              <Field label="Email" htmlFor="settings-email">
                <div className="flex items-center gap-2">
                  <Input id="settings-email" value={auth.email} readOnly className="flex-1 cursor-default" />
                  <Button variant="outline" size="md" className="shrink-0">
                    Modifier
                  </Button>
                </div>
              </Field>
              <Field label="Mot de passe" htmlFor="settings-password">
                <div className="flex items-center gap-2">
                  <Input
                    id="settings-password"
                    type="password"
                    value="••••••••••"
                    readOnly
                    className="flex-1 cursor-default font-mono tracking-widest"
                  />
                  <Button variant="outline" size="md" className="shrink-0">
                    Changer
                  </Button>
                </div>
              </Field>
            </div>
          </Section>

          {/* PROFIL TRADING */}
          <Section
            id="section-profil"
            eyebrow="02 · Profil de trading"
            title="Comment on te calibre"
            subtitle="Ces réponses ajustent le ton, le sizing et les alertes."
            action={
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/welcome")}
                className="text-brand-400 hover:text-brand-300"
              >
                <Edit3 className="h-3.5 w-3.5" />
                Modifier
              </Button>
            }
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Stat label="Profil" value={profile.type ?? "—"} />
              <Stat label="Expérience" value={profile.experience ?? "—"} />
              <Stat label="Réaction score" value={profile.reaction ?? "—"} />
              <Stat label="Budget" value={profile.budget ?? "—"} />
            </div>
            {profile.suggestedSizing && (
              <div className="mt-4 flex items-center gap-2.5 rounded-lg border border-brand-500/25 bg-brand-500/[0.05] px-4 py-3">
                <Sparkles className="h-4 w-4 shrink-0 text-brand-400" />
                <span className="text-body-md text-ink-muted">
                  Sizing suggéré ·{" "}
                  <span className="num font-semibold text-brand-300">{profile.suggestedSizing}</span>
                </span>
              </div>
            )}
          </Section>

          {/* NOTIFICATIONS */}
          <Section
            id="section-notifications"
            eyebrow="03 · Notifications"
            title="Où recevoir les signaux"
            subtitle="Tu choisis le canal et le seuil."
          >
            <div className="space-y-4">
              {/* Telegram */}
              <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-obsidian-850/60 p-4">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line-strong bg-obsidian-800">
                    <Send className="h-4 w-4 text-brand-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-medium text-ink">
                      Telegram
                      <PaywallChip />
                    </p>
                    <p className="mt-0.5 text-body-sm text-ink-muted">
                      {telegramConnected
                        ? "Connecté à @foresight_bot · signaux 60+ envoyés instantanément"
                        : "Push instantané sur ton Telegram dès qu’un signal 60+ atterrit."}
                    </p>
                  </div>
                </div>
                <Button
                  variant={telegramConnected ? "outline" : "primary"}
                  size="sm"
                  onClick={() => setTelegramConnected((v) => !v)}
                  className="shrink-0"
                >
                  {telegramConnected ? (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      Connecté
                    </>
                  ) : (
                    <>
                      Connecter
                      <ExternalLink className="h-3.5 w-3.5" />
                    </>
                  )}
                </Button>
              </div>

              {/* Email */}
              <div className="rounded-lg border border-line bg-obsidian-850/60 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line-strong bg-obsidian-800">
                      <Mail className="h-4 w-4 text-ink-muted" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-ink">Email</p>
                      <p className="mt-0.5 text-body-sm text-ink-muted">
                        Résumé email avec screenshots des signaux au-dessus du seuil.
                      </p>
                    </div>
                  </div>
                  <Toggle checked={emailNotif} onChange={setEmailNotif} label="Notifications email" />
                </div>
                {emailNotif && (
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line/60 pt-3">
                    <span id="email-threshold-label" className="text-body-sm text-ink-muted">Seuil</span>
                    <div role="radiogroup" aria-labelledby="email-threshold-label" className="flex gap-1">
                      {[60, 75, 90].map((t) => (
                        <button
                          key={t}
                          type="button"
                          role="radio"
                          aria-checked={emailThreshold === t}
                          tabIndex={emailThreshold === t ? 0 : -1}
                          onClick={() => setEmailThreshold(t)}
                          className={cn(
                            "rounded-md border px-2.5 py-1 text-label-sm font-mono transition-premium cursor-pointer",
                            emailThreshold === t
                              ? "border-brand-500/40 bg-brand-500/[0.08] text-brand-300"
                              : "border-line bg-obsidian-800 text-ink-muted hover:border-line-strong hover:text-ink",
                          )}
                        >
                          {t}+
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Push */}
              <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-obsidian-850/60 p-4">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line-strong bg-obsidian-800">
                    <Bell className="h-4 w-4 text-ink-muted" />
                  </div>
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-medium text-ink">
                      Push navigateur
                      <PaywallChip />
                    </p>
                    <p className="mt-0.5 text-body-sm text-ink-muted">
                      Alerte dès qu’un signal passe en «&nbsp;vendre&nbsp;», tant que l’onglet est ouvert.
                    </p>
                    {pushPermission === "denied" && (
                      <p className="mt-1 text-label-sm text-signal-no/90">
                        Permission refusée — réactive-la dans les réglages du navigateur.
                      </p>
                    )}
                  </div>
                </div>
                <Toggle
                  checked={pushNotif && pushPermission === "granted"}
                  onChange={(v) => {
                    void togglePushNotif(v)
                  }}
                  label="Push navigateur"
                />
              </div>
            </div>
          </Section>

          {/* FILTRES */}
          <Section
            id="section-filtres"
            eyebrow="04 · Filtres par défaut"
            title="Ta vue Signaux"
            subtitle="Appliqués à l’ouverture de la page Signaux."
            icon={SlidersHorizontal}
          >
            <div className="space-y-5">
              <div>
                <span id="score-radiogroup-label" className="mb-2 block text-body-sm font-medium text-ink">
                  Score minimum
                </span>
                <div role="radiogroup" aria-labelledby="score-radiogroup-label" className="flex flex-wrap gap-1.5">
                  {SCORE_THRESHOLDS.map((s) => {
                    const active = defaultScore === s.value
                    return (
                      <PillButton
                        key={s.value}
                        active={active}
                        role="radio"
                        tabIndex={active ? 0 : -1}
                        onClick={() => setDefaultScore(s.value)}
                      >
                        {s.label}
                      </PillButton>
                    )
                  })}
                </div>
              </div>

              <div>
                <span id="direction-radiogroup-label" className="mb-2 block text-body-sm font-medium text-ink">
                  Direction préférée
                </span>
                <div role="radiogroup" aria-labelledby="direction-radiogroup-label" className="flex flex-wrap gap-1.5">
                  {DIRECTIONS.map((d) => {
                    const active = defaultDirection === d.value
                    return (
                      <PillButton
                        key={d.value}
                        active={active}
                        role="radio"
                        tabIndex={active ? 0 : -1}
                        onClick={() => setDefaultDirection(d.value)}
                      >
                        {d.label}
                      </PillButton>
                    )
                  })}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span id="categories-group-label" className="block text-body-sm font-medium text-ink">
                    Catégories actives
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedCategories(
                        selectedCategories.length === CATEGORIES.length
                          ? []
                          : CATEGORIES.map((c) => c.value),
                      )
                    }
                    className="text-label-sm text-brand-400 hover:text-brand-300 transition-premium cursor-pointer"
                  >
                    {selectedCategories.length === CATEGORIES.length ? "Tout désélectionner" : "Tout sélectionner"}
                  </button>
                </div>
                <div role="group" aria-labelledby="categories-group-label" className="flex flex-wrap gap-1.5">
                  {CATEGORIES.map((c) => (
                    <PillButton
                      key={c.value}
                      active={selectedCategories.includes(c.value)}
                      role="checkbox"
                      onClick={() => toggleCategory(c.value)}
                    >
                      {c.label}
                    </PillButton>
                  ))}
                </div>
              </div>
            </div>
          </Section>

          {/* PLAN */}
          <Section
            id="section-plan"
            eyebrow="05 · Plan & facturation"
            title={`Plan ${planInfo.name}`}
            subtitle={planInfo.limit}
            icon={Crown}
          >
            {onTrial && trialEnd && (
              <div className="mb-3 rounded-lg border border-brand-500/30 bg-brand-500/[0.06] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-display text-title-sm font-semibold text-ink">
                      {`Essai\u00A0Pro · Se termine le ${formatTrialEndFR(trialEnd)}`}
                    </p>
                    <p className="mt-1 text-body-sm leading-relaxed text-ink-muted">
                      {"Ajoute une carte pour continuer après l\u2019essai. Sinon, tu repasses automatiquement en Free."}
                    </p>
                  </div>
                  <Button
                    variant="primary"
                    size="md"
                    className="shrink-0"
                    onClick={() => {
                      // TODO: wire card collection — Cursor will replace
                      // this with the real Stripe / payment method flow.
                      // eslint-disable-next-line no-console
                      console.log("TODO: wire card collection")
                      navigate("/pricing?plan=pro")
                    }}
                  >
                    Ajouter une carte
                  </Button>
                </div>
              </div>
            )}
            <div className="rounded-lg border border-line bg-obsidian-850/60 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-display text-title-md font-semibold text-ink">
                      {planInfo.name}
                    </span>
                    <span className="rounded-full border border-brand-500/30 bg-brand-500/[0.08] px-2 py-0.5 text-label-xs font-mono uppercase tracking-[0.12em] text-brand-300">
                      {t("settings.plan.currentBadge")}
                    </span>
                  </div>
                  <p className="num mt-1 text-body-sm text-ink-muted">{planInfo.price}</p>
                </div>
                {auth.plan === "free" && (
                  <Button variant="primary" size="md" onClick={() => navigate("/pricing")} className="shrink-0">
                    <Crown className="h-3.5 w-3.5" />
                    Passer Pro
                  </Button>
                )}
                {auth.plan !== "free" && (
                  <Button
                    variant="outline"
                    size="md"
                    className="shrink-0"
                    onClick={async () => {
                      // Legal-PR-1 M1 — DSA art. 25: subscribe-then-cancel
                      // friction must be symmetric. The Stripe customer
                      // portal is the user's one-click path to cancel,
                      // download invoices, update payment method.
                      try {
                        const url = await openStripePortal()
                        window.location.assign(url)
                      } catch {
                        addToast({
                          type: "info",
                          title: "Portail indisponible",
                          description:
                            "Réessaie dans un instant ou contacte le support.",
                        })
                      }
                    }}
                  >
                    Gérer mon abonnement
                  </Button>
                )}
              </div>

              {quota && (
                <div className="mt-4 border-t border-line/60 pt-4">
                  <div className="mb-1.5 flex items-center justify-between text-body-sm">
                    <span className="text-ink-muted">Signaux consultés aujourd’hui</span>
                    <span className="num text-ink">
                      {quota.used} <span className="text-ink-dim">/ {quota.max}</span>
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-line/60">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(quota.used / quota.max) * 100}%` }}
                      transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
                      className="h-full bg-gradient-to-r from-brand-500 to-brand-300"
                    />
                  </div>
                </div>
              )}
            </div>
          </Section>

          {/* DANGER ZONE */}
          <Section
            id="section-danger"
            eyebrow="06 · Zone danger"
            title="Déconnexion & suppression"
            subtitle="Actions irréversibles. Pense à exporter ton historique d’abord."
          >
            <div className="space-y-2.5">
              <button
                onClick={logout}
                className="group flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-obsidian-850/60 px-4 py-3.5 text-left transition-premium hover:border-line-strong hover:bg-obsidian-800 cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line-strong bg-obsidian-800 text-ink-muted group-hover:text-ink">
                    <LogOut className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium text-ink">Se déconnecter</p>
                    <p className="text-body-sm text-ink-muted">
                      Termine la session sur cet appareil.
                    </p>
                  </div>
                </div>
              </button>

              {/* Revoke cookie consent — required by CNIL: the user must be
                  able to revisit their choice with the same ease as making
                  it. Resets the consent record so the banner reappears. */}
              <button
                type="button"
                onClick={() => {
                  revokeConsent()
                  addToast({
                    type: "success",
                    title: "Choix de cookies effacé",
                    description:
                      "Le bandeau s’affichera lors de ta prochaine action.",
                  })
                }}
                className="group flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-obsidian-850/60 px-4 py-3.5 text-left transition-premium hover:border-line-strong hover:bg-obsidian-800 cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line-strong bg-obsidian-800 text-ink-muted group-hover:text-ink">
                    <Cookie className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium text-ink">Revoir mes choix de cookies</p>
                    <p className="text-body-sm text-ink-muted">
                      Réaffiche le bandeau de consentement et permet de
                      modifier les catégories.
                    </p>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="group flex w-full items-center justify-between gap-3 rounded-lg border border-signal-no/20 bg-signal-no/[0.04] px-4 py-3.5 text-left transition-premium hover:border-signal-no/40 hover:bg-signal-no/[0.08] cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-signal-no/30 bg-signal-no/[0.08] text-signal-no">
                    <Trash2 className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium text-ink">Supprimer mon compte</p>
                    <p className="text-body-sm text-ink-muted">
                      Historique, profil et abonnement effacés définitivement.
                    </p>
                  </div>
                </div>
              </button>
            </div>
          </Section>
        </div>

        {/* Save bar */}
        <div className="sticky bottom-4 mt-8 flex items-center justify-between gap-3 rounded-xl border border-line-strong bg-obsidian-850/95 p-3 backdrop-blur-xl shadow-elevated">
          <p className="pl-2 text-body-sm text-ink-muted">
            {saved ? (
              <span className="inline-flex items-center gap-1.5 text-brand-400">
                <Check className="h-3.5 w-3.5" />
                Préférences enregistrées
              </span>
            ) : (
              "Les changements sont locaux pour l’instant."
            )}
          </p>
          <Button variant="primary" size="md" onClick={save} className="min-w-[140px]">
            Enregistrer
          </Button>
        </div>
        </div>

        <TOC activeId={activeTocId} />
      </div>
      <ConfirmDeleteAccountModal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={async () => {
          // Legal-PR-1 B7 — RGPD Art. 17 (right to erasure). Pre-fix this
          // handler ONLY cleared localStorage; the user's row stayed in
          // Postgres and the "delete" was a polite lie. Now: server
          // delete first, local clear second, redirect last.
          try {
            await deleteAccountApi()
          } catch (e) {
            addToast({
              type: "info",
              title: "Suppression impossible",
              description:
                "Le serveur n’a pas pu confirmer la suppression. Réessaie ou contacte le support.",
            })
            // Don't clear local state — that would lock the user out of
            // their still-active account.
            // eslint-disable-next-line no-console
            console.warn("deleteAccountApi failed", e)
            return
          }
          try {
            localStorage.clear()
            window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT))
          } catch {
            // ignore storage errors
          }
          setConfirmDelete(false)
          navigate("/")
        }}
      />
    </AppShell>
  )
}

function TOC({ activeId }: { activeId: string | null }) {
  const { t } = useTranslation()
  return (
    <aside
      aria-label={t("settings.toc.ariaLabel")}
      className="hidden lg:block"
    >
      <nav className="sticky top-24">
        <p className="mb-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
          Sommaire
        </p>
        <ol className="flex flex-col gap-2 text-body-sm">
          {TOC_SECTIONS.map((s, i) => {
            const active = activeId === s.id
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className={cn(
                    "flex items-baseline gap-2 rounded-md px-2 py-1 transition-premium",
                    active
                      ? "text-brand-400"
                      : "text-ink-muted hover:text-ink",
                  )}
                >
                  <span className="num font-mono text-label-xs text-ink-dim">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{t(s.labelKey)}</span>
                </a>
              </li>
            )
          })}
        </ol>
      </nav>
    </aside>
  )
}

function Section({
  eyebrow,
  title,
  subtitle,
  action,
  icon: Icon,
  id,
  children,
}: {
  eyebrow: string
  title: string
  subtitle?: string
  action?: React.ReactNode
  icon?: React.ElementType
  id?: string
  children: React.ReactNode
}) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default }}
      className="scroll-mt-24 rounded-xl border border-line/70 bg-obsidian-850/40 p-5 md:p-6"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="mb-1 font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
            {eyebrow}
          </p>
          <div className="flex items-center gap-2">
            {Icon && <Icon className="h-4 w-4 text-ink-muted" />}
            <h2 className="font-display text-title-sm font-medium text-ink">{title}</h2>
          </div>
          {subtitle && <p className="mt-0.5 text-body-md text-ink-muted">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </motion.section>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-body-sm font-medium text-ink">
        {label}
      </label>
      {children}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-obsidian-850/60 px-3.5 py-3">
      <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">{label}</p>
      <p className="mt-0.5 text-[0.9375rem] text-ink">{value}</p>
    </div>
  )
}

function PillButton({
  active,
  onClick,
  children,
  role,
  tabIndex,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  role?: "radio" | "checkbox"
  tabIndex?: number
}) {
  const extraAria =
    role === "radio"
      ? { "aria-checked": active as boolean }
      : role === "checkbox"
        ? { "aria-checked": active as boolean }
        : {}
  return (
    <button
      type="button"
      onClick={onClick}
      role={role}
      tabIndex={tabIndex}
      {...extraAria}
      className={cn(
        "rounded-md border px-3 py-1.5 text-body-sm transition-premium cursor-pointer",
        active
          ? "border-brand-500/40 bg-brand-500/[0.08] text-brand-300"
          : "border-line bg-obsidian-800 text-ink-muted hover:border-line-strong hover:text-ink",
      )}
    >
      {children}
    </button>
  )
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full border transition-premium cursor-pointer",
        checked
          ? "border-brand-500/40 bg-brand-500"
          : "border-line-strong bg-obsidian-800",
      )}
    >
      <motion.span
        animate={{ x: checked ? 20 : 2 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className={cn(
          "absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full shadow-sm motion-reduce:transition-none",
          checked ? "bg-obsidian-900" : "bg-ink-muted",
        )}
      />
    </button>
  )
}
