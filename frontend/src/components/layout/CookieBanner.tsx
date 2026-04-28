/**
 * CNIL-compliant cookie consent banner.
 *
 * Mounts at the App root. Shows on first visit (no decision yet) and
 * after an explicit revoke from Settings. Hides itself the moment the
 * user makes any choice and persists the record in localStorage.
 *
 * UX contract (CNIL deliberation 2020-091):
 *   * "Tout refuser" must be as easy as "Tout accepter" (same prominence,
 *     same number of clicks). Both buttons are visually equal here.
 *   * The banner cannot block the rest of the page (no full-screen
 *     overlay). It sits as a pinned-bottom element.
 *   * Granular toggles are reachable in one click via "Personnaliser".
 *   * Refusing must NOT trigger a re-prompt within the same visit.
 */

import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Link } from "react-router-dom"
import { Cookie, X } from "lucide-react"
import {
  acceptAll,
  refuseAll,
  setConsent,
  useConsent,
} from "@/lib/cookieConsent"
import { useMotionConfig } from "@/lib/motion"
import { cn } from "@/lib/utils"

export function CookieBanner() {
  const consent = useConsent()
  const motionConfig = useMotionConfig("default")
  const [showCustom, setShowCustom] = useState(false)
  const [analytics, setAnalytics] = useState(false)
  const [marketing, setMarketing] = useState(false)

  // Hide once a decision has been recorded.
  if (consent !== null) return null

  return (
    <AnimatePresence>
      <motion.div
        key="cookie-banner"
        role="dialog"
        aria-modal="false"
        aria-labelledby="cookie-banner-title"
        aria-describedby="cookie-banner-body"
        initial={{ y: 16, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 16, opacity: 0 }}
        transition={motionConfig}
        className={cn(
          "fixed inset-x-2 bottom-2 z-[60] mx-auto max-w-3xl",
          "rounded-2xl border border-line-strong bg-obsidian-850/95",
          "px-4 py-4 shadow-elevated backdrop-blur-xl md:px-6",
        )}
      >
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-line bg-obsidian-800 text-brand-300">
            <Cookie className="h-4 w-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <h2
              id="cookie-banner-title"
              className="font-display text-title-sm font-semibold text-ink"
            >
              {"Cookies & stockage local"}
            </h2>
            <p id="cookie-banner-body" className="mt-1 text-body-sm text-ink-muted">
              {"Foresight utilise uniquement le stockage local indispensable au fonctionnement (session, préférences, positions ouvertes). Les mesures d’audience anonymes ne se déclenchent qu’avec ton accord. "}
              <Link to="/cookies" className="underline hover:text-ink">
                {"En savoir plus"}
              </Link>
              {" · "}
              <Link to="/confidentialite" className="underline hover:text-ink">
                {"Politique de confidentialité"}
              </Link>
            </p>

            {showCustom && (
              <div className="mt-4 space-y-2 border-t border-line/60 pt-4">
                <CategoryRow
                  label="Indispensable"
                  description="Authentification, préférences langue/devise, positions ouvertes."
                  checked
                  disabled
                  hint="Toujours activé (exempté CNIL Art. 82 al. 2)"
                />
                <CategoryRow
                  label="Mesure d’audience"
                  description="Compte anonyme du nombre de pages vues / signaux consultés. Aujourd’hui : aucune mesure n’est en place."
                  checked={analytics}
                  onChange={setAnalytics}
                />
                <CategoryRow
                  label="Marketing & re-targeting"
                  description="Pixels publicitaires, audiences personnalisées. Aujourd’hui : aucun script."
                  checked={marketing}
                  onChange={setMarketing}
                />
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => refuseAll()}
                className="inline-flex h-10 items-center rounded-md border border-line-strong bg-obsidian-800 px-4 text-body-sm font-medium text-ink hover:border-line/80 hover:bg-obsidian-700 transition-premium cursor-pointer"
              >
                {"Tout refuser"}
              </button>
              <button
                type="button"
                onClick={() => acceptAll()}
                className="inline-flex h-10 items-center rounded-md bg-brand-500 px-4 text-body-sm font-semibold text-obsidian-950 hover:bg-brand-400 transition-premium cursor-pointer"
              >
                {"Tout accepter"}
              </button>
              {!showCustom ? (
                <button
                  type="button"
                  onClick={() => setShowCustom(true)}
                  className="inline-flex h-10 items-center rounded-md px-3 text-body-sm text-ink-muted underline hover:text-ink transition-premium cursor-pointer"
                >
                  {"Personnaliser"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setConsent({ analytics, marketing })}
                  className="inline-flex h-10 items-center rounded-md border border-brand-500/40 bg-brand-500/10 px-4 text-body-sm text-brand-300 hover:bg-brand-500/15 transition-premium cursor-pointer"
                >
                  {"Confirmer mes choix"}
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => refuseAll()}
            aria-label="Tout refuser et fermer"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-ink-dim hover:bg-obsidian-800 hover:text-ink transition-premium cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

function CategoryRow({
  label,
  description,
  checked,
  onChange,
  disabled,
  hint,
}: {
  label: string
  description: string
  checked: boolean
  onChange?: (next: boolean) => void
  disabled?: boolean
  hint?: string
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-3 rounded-lg border border-line/60 px-3 py-2.5",
        disabled ? "opacity-80 cursor-not-allowed" : "hover:border-line-strong",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange?.(e.target.checked)}
        disabled={disabled}
        className="mt-0.5 h-4 w-4 rounded border-line-strong bg-obsidian-800 text-brand-500 focus:ring-2 focus:ring-brand-500/30 cursor-pointer"
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-ink">{label}</p>
        <p className="mt-0.5 text-label-sm text-ink-muted">{description}</p>
        {hint && <p className="mt-1 text-label-xs text-ink-dim">{hint}</p>}
      </div>
    </label>
  )
}
