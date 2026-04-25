import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useNavigate } from "react-router-dom"
import { Timer, X } from "lucide-react"
import { useMotionConfig } from "@/lib/motion"
import {
  formatTrialEndFR,
  isOnTrial,
  trialDaysRemaining,
  trialEndDate,
} from "@/lib/trial"
import { useAuth } from "@/hooks/useAuth"
import { todayISODate } from "@/lib/utils"
import { trialBannerDismissKey } from "@/lib/storageKeys"

function isDismissedToday(): boolean {
  try {
    return localStorage.getItem(trialBannerDismissKey(todayISODate())) === "1"
  } catch {
    return false
  }
}

function markDismissedToday(): void {
  try {
    localStorage.setItem(trialBannerDismissKey(todayISODate()), "1")
  } catch {
    // ignore — best-effort dismiss persistence
  }
}

export default function TrialBanner() {
  const navigate = useNavigate()
  const motionConfig = useMotionConfig("default")
  // Reactive auth — picks up cross-tab AND same-tab (trial expiry,
  // card attachment) mutations via the shared hook.
  const auth = useAuth()
  const [dismissed, setDismissed] = useState<boolean>(() => isDismissedToday())

  const onTrial = isOnTrial(auth)
  const visible = onTrial && !dismissed

  const days = trialDaysRemaining(auth)
  const end = trialEndDate(auth)
  const dayLabel = days === 1 ? "jour" : "jours"

  return (
    <AnimatePresence initial={false}>
      {visible && (
        <motion.div
          key="trial-banner"
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={motionConfig}
          className="sticky top-0 z-40 flex h-12 w-full items-center gap-3 border-b border-brand-500/20 bg-brand-500/[0.08] px-4 text-ink md:px-6"
        >
          <Timer className="h-4 w-4 shrink-0 text-brand-400" aria-hidden />
          <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <p className="text-body-sm font-medium text-ink">
              {`Essai\u00A0Pro · ${days} ${dayLabel} restants`}
            </p>
            {end && (
              <p className="text-label-sm text-ink-dim">
                {`Se termine le ${formatTrialEndFR(end)}`}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => navigate("/settings#plan")}
            className="inline-flex h-10 md:h-8 shrink-0 items-center rounded-md border border-brand-500/40 bg-brand-500/[0.12] px-3 text-label-sm font-medium text-brand-200 transition-premium hover:bg-brand-500/20 hover:text-ink cursor-pointer"
          >
            Ajouter une carte
          </button>
          <button
            type="button"
            onClick={() => {
              markDismissedToday()
              setDismissed(true)
            }}
            aria-label={"Fermer le bandeau d\u2019essai"}
            className="inline-flex h-10 w-10 md:h-8 md:w-8 shrink-0 items-center justify-center rounded-md text-ink-dim transition-premium hover:bg-obsidian-800 hover:text-ink cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

