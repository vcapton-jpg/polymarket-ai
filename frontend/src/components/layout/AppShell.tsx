import { NavLink, Link, useNavigate } from "react-router-dom"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import FocusLock from "react-focus-lock"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { useEffect, useState } from "react"
import TrialBanner from "@/components/layout/TrialBanner"
import EndOfTrialModal from "@/components/layout/EndOfTrialModal"
import { isOnTrial, clearAuth } from "@/lib/trial"
import { useAuth } from "@/hooks/useAuth"
import { logoutApi } from "@/lib/api/auth"
import {
  Radio,
  Briefcase,
  LineChart,
  Settings as SettingsIcon,
  Crown,
  LogOut,
  ChevronRight,
  Menu,
  X,
  BookOpen,
  Globe,
} from "lucide-react"
import { Logo } from "@/components/ui/Logo"
import { LivePill } from "@/components/signals/badges"
import { PreferenceToggles } from "@/components/layout/PreferenceToggles"
import { useUserPreferences } from "@/lib/userPreferences"
import type { SupportedLanguage } from "@/lib/i18n"
import type { Currency } from "@/lib/formatCurrency"
import { MOCK_POSITIONS } from "@/data/positions"
import { useManualPositions } from "@/lib/useManualPositions"
import { OfflineBanner } from "@/components/layout/OfflineBanner"
import { ToastViewport } from "@/lib/useToasts"
import { useVendreNotifications } from "@/lib/useVendreNotifications"
import { cn } from "@/lib/utils"

type NavItem = {
  to: string
  label: string
  icon: typeof Radio
  /** When provided, a numeric badge is rendered. `0` stays visible — the spec
   * (README-V2 line 96) requires the Portfolio badge to be shown even at 0 so
   * the user has a consistent visual anchor. */
  badge?: number
}

type NavGroup = {
  heading: string
  items: NavItem[]
}

/**
 * Build the three-group navigation for the current session.
 *
 * The Portfolio badge is computed from two sources: the baseline mocks
 * plus whatever manual positions the user has persisted in localStorage.
 * This matches the Portfolio page itself and makes the sidebar stay in
 * sync when the user opens a manual position from the modal.
 */
function useNavGroups(manualPositionCount: number): NavGroup[] {
  const portfolioCount = MOCK_POSITIONS.length + manualPositionCount

  return [
    {
      heading: "Feed",
      items: [
        { to: "/signals", label: "Signaux", icon: Radio },
        {
          to: "/portfolio",
          label: "Portfolio",
          icon: Briefcase,
          badge: portfolioCount,
        },
      ],
    },
    {
      heading: "Guide",
      items: [{ to: "/apprendre", label: "Apprendre", icon: BookOpen }],
    },
    {
      heading: "Analyse",
      items: [{ to: "/performance", label: "Performance", icon: LineChart }],
    },
    {
      heading: "Compte",
      items: [
        { to: "/settings", label: "Réglages", icon: SettingsIcon },
      ],
    },
  ]
}

type AppShellProps = {
  children: React.ReactNode
  title?: string
  breadcrumb?: Array<{ label: string; to?: string }>
  topbarRight?: React.ReactNode
  showLive?: boolean
  liveCount?: number
}

export function AppShell({
  children,
  breadcrumb,
  topbarRight,
  showLive = true,
  liveCount,
}: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { positions: manualPositions } = useManualPositions()
  const navGroups = useNavGroups(manualPositions.length)
  const navigate = useNavigate()

  const handleLogout = async () => {
    // Clear local state first so the UI flips immediately even if the
    // server call is slow or offline. logoutApi() is fire-and-forget —
    // it also clears the JWT token on failure.
    clearAuth()
    void logoutApi().catch(() => undefined)
    navigate("/login")
  }

  // Close mobile drawer on Escape — matches the modal a11y pattern.
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [mobileOpen])

  // Fire browser notification + simulated Telegram alert whenever a new
  // position enters "vendre" status. Mounted here so it's active on every
  // page in the authenticated shell.
  useVendreNotifications()

  // Trial-aware main padding. TrialBanner self-hides when not on trial;
  // we read the same source to know whether to reserve space for it.
  // Reactive: useAuth picks up cross-tab and same-tab auth mutations
  // (trial expiry auto-downgrade, card attachment) without a remount.
  const auth = useAuth()
  const trialActive = isOnTrial(auth)
  const isProUser = auth?.plan === "pro"

  return (
    <div className="min-h-screen bg-obsidian-900" data-trial-active={trialActive ? "1" : undefined}>
      <TrialBanner />
      <EndOfTrialModal />
      <OfflineBanner />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-brand-500 focus:px-4 focus:py-2 focus:text-obsidian-900 focus:font-medium"
      >
        Aller au contenu
      </a>
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] border-r border-line/60 bg-obsidian-850 lg:flex lg:flex-col">
        <div className="flex h-16 items-center border-b border-line/60 px-5">
          <Link to="/" className="flex items-center gap-2">
            <Logo />
          </Link>
        </div>

        <nav aria-label="Principal" className="flex-1 flex flex-col p-3">
          {navGroups.map((group, groupIndex) => (
            <div key={group.heading} className={groupIndex > 0 ? "mt-5" : ""}>
              <div className="px-2 pb-2 pt-1 text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim">
                {group.heading}
              </div>
              <ul role="list" className="flex flex-col gap-1">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-premium",
                          isActive
                            ? "bg-obsidian-750 text-ink border border-line-strong"
                            : "text-ink-muted hover:text-ink hover:bg-obsidian-800 border border-transparent",
                        )
                      }
                    >
                      <item.icon className="h-4 w-4" />
                      <span className="flex-1">{item.label}</span>
                      {item.badge !== undefined && (
                        <>
                          <span
                            aria-hidden="true"
                            className={cn(
                              "num inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[0.6875rem] font-semibold ring-1",
                              item.badge > 0
                                ? "bg-brand-500/20 text-brand-300 ring-brand-500/30"
                                : "bg-obsidian-800 text-ink-dim ring-line/60",
                            )}
                          >
                            {item.badge}
                          </span>
                          <span className="sr-only"> · {item.badge} positions actives</span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* Upgrade CTA — rotating micro-pitch (Fix 16). Sits below all
              groups as a standalone anchor, not a nav item. Hidden
              entirely for Pro users (on-trial Pro still sees it as a
              reminder to attach a card — `isOnTrial` gate would flip it
              off the moment card_attached flips to true). */}
          {!isProUser && <ProUpsellCTA />}

          <p className="mt-4 px-3 text-label-xs font-medium text-ink-dim">
            Partenaire Polymarket
          </p>
        </nav>

      </aside>

      {/* Mobile topbar */}
      <div className="lg:hidden sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line/60 bg-obsidian-900/90 backdrop-blur-xl px-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMobileOpen(true)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink hover:bg-obsidian-800 cursor-pointer"
            aria-label="Menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link to="/" className="flex items-center gap-2">
            <Logo showWordmark={false} size={24} />
            <span className="font-display text-[0.95rem] font-semibold">Foresight</span>
          </Link>
        </div>
        {showLive && <LivePill />}
      </div>

      {/* Mobile sidebar drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-40 bg-obsidian-950/80 backdrop-blur-sm lg:hidden"
            />
            <FocusLock returnFocus disabled={!mobileOpen}>
            <motion.aside
              role="dialog"
              aria-modal="true"
              aria-labelledby="mobile-nav-title"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: DURATIONS.default, ease: EASE_PREMIUM }}
              className="fixed inset-y-0 left-0 z-50 w-[280px] border-r border-line bg-obsidian-850 lg:hidden flex flex-col"
            >
              <h2 id="mobile-nav-title" className="sr-only">Navigation</h2>
              <div className="flex h-14 items-center justify-between px-4 border-b border-line/60">
                <Link to="/" className="flex items-center gap-2">
                  <Logo />
                </Link>
                <button
                  onClick={() => setMobileOpen(false)}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink hover:bg-obsidian-800"
                  aria-label="Fermer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <nav aria-label="Principal" className="flex-1 p-3 flex flex-col">
                {navGroups.map((group, groupIndex) => (
                  <div key={group.heading} className={groupIndex > 0 ? "mt-5" : ""}>
                    <div className="px-2 pb-2 pt-1 text-[0.6875rem] font-mono uppercase tracking-[0.14em] text-ink-dim">
                      {group.heading}
                    </div>
                    <ul role="list" className="flex flex-col gap-1">
                      {group.items.map((item) => (
                        <li key={item.to}>
                          <NavLink
                            to={item.to}
                            onClick={() => setMobileOpen(false)}
                            className={({ isActive }) =>
                              cn(
                                "flex items-center gap-2.5 rounded-md px-3 py-3 text-sm",
                                isActive
                                  ? "bg-obsidian-750 text-ink"
                                  : "text-ink-muted hover:bg-obsidian-800",
                              )
                            }
                          >
                            <item.icon className="h-4 w-4" />
                            <span className="flex-1">{item.label}</span>
                            {item.badge !== undefined && (
                              <>
                                <span
                                  aria-hidden="true"
                                  className={cn(
                                    "num inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[0.6875rem] font-semibold ring-1",
                                    item.badge > 0
                                      ? "bg-brand-500/20 text-brand-300 ring-brand-500/30"
                                      : "bg-obsidian-800 text-ink-dim ring-line/60",
                                  )}
                                >
                                  {item.badge}
                                </span>
                                <span className="sr-only"> · {item.badge} positions actives</span>
                              </>
                            )}
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <Link
                  to="/pricing"
                  onClick={() => setMobileOpen(false)}
                  className="mt-6 flex items-center gap-2 rounded-md border border-brand-500/30 bg-brand-500/10 px-3 py-3 text-sm text-ink"
                >
                  <Crown className="h-4 w-4 text-brand-400" />
                  Passer Pro
                </Link>
                <p className="mt-4 px-3 text-label-xs font-medium text-ink-dim">
                  Partenaire Polymarket
                </p>
              </nav>
              <div className="border-t border-line/60 p-4">
                <PreferenceToggles compact />
              </div>
            </motion.aside>
            </FocusLock>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="lg:pl-[248px]">
        {/* Desktop topbar */}
        <header
          role="banner"
          className="sticky top-0 z-20 hidden lg:flex h-16 items-center justify-between border-b border-line/60 bg-obsidian-900/75 backdrop-blur-xl px-6"
        >
          <div className="flex items-center gap-3 text-sm">
            {breadcrumb && (
              <nav className="flex items-center gap-2 text-ink-muted">
                {breadcrumb.map((b, i) => (
                  <span key={i} className="flex items-center gap-2">
                    {b.to ? (
                      <Link to={b.to} className="hover:text-ink">
                        {b.label}
                      </Link>
                    ) : (
                      <span className={i === breadcrumb.length - 1 ? "text-ink" : ""}>{b.label}</span>
                    )}
                    {i < breadcrumb.length - 1 && <ChevronRight className="h-3.5 w-3.5 text-ink-dim" />}
                  </span>
                ))}
              </nav>
            )}
            {liveCount !== undefined && (
              <>
                <span className="text-line-strong">·</span>
                <span className="text-ink-muted">
                  <span className="num font-medium text-ink">{liveCount}</span> signaux aujourd’hui
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            {showLive && <LivePill />}
            <PreferenceToggles />
            {topbarRight}
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-muted hover:text-ink hover:bg-obsidian-800 cursor-pointer"
              aria-label="Déconnexion"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main id="main" className={trialActive ? "pt-12" : undefined}>
          <div className="mx-auto w-full max-w-[1440px]">{children}</div>
        </main>
      </div>

      {/* Toast layer — rendered at the shell level so transient alerts
          (e.g. "Alerte Telegram envoyée" on vendre status) float above
          any page content without being clipped by page containers. */}
      <ToastViewport />
    </div>
  )
}

const PRO_PITCHES = [
  "Signaux\u00A090+ débloqués",
  "Alertes Telegram temps\u00A0réel",
  "Latence <\u00A090\u00A0s",
  "Historique illimité",
] as const

/**
 * Rotating Pro upsell in the sidebar. Cross-fades between four micro-pitches
 * on an 8s cadence. Respects reduced-motion by pinning to the first pitch.
 */
function ProUpsellCTA() {
  const reduced = useReducedMotion()
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    if (reduced) return
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % PRO_PITCHES.length)
    }, 8000)
    return () => window.clearInterval(id)
  }, [reduced])

  const pitch = reduced ? PRO_PITCHES[0] : PRO_PITCHES[idx]

  return (
    <Link
      to="/pricing?plan=pro"
      className="group mt-6 flex items-start gap-2.5 rounded-md border border-brand-500/30 bg-gradient-to-br from-brand-500/10 to-transparent px-3 py-2.5 text-sm text-ink hover:border-brand-500/50 transition-premium"
      aria-label="Passer Pro — essai 7 jours"
    >
      <Crown className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
      <span className="flex-1 min-w-0">
        <span className="block font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-brand-300">
          Passer Pro
        </span>
        <span
          className="relative mt-0.5 block h-[1.125rem] overflow-hidden text-[0.8125rem] text-ink"
          aria-hidden="true"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={pitch}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
              className="absolute inset-0 block truncate"
            >
              {pitch}
            </motion.span>
          </AnimatePresence>
        </span>
        <span className="sr-only" aria-live="polite">
          {pitch}
        </span>
        <span className="mt-1.5 inline-flex items-center rounded-full border border-brand-500/30 bg-brand-500/10 px-1.5 py-0.5 font-mono text-[0.625rem] uppercase tracking-[0.12em] text-brand-300">
          {"Essai\u00A07\u00A0jours"}
        </span>
      </span>
      <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400 transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}
