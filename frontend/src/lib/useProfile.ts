import { useEffect, useState } from "react"
import type { UserProfile } from "@/types/signal"

/**
 * Shared access to the onboarding-derived user profile stored in
 * `localStorage.foresight.profile`. The profile drives pedagogical
 * differentiation (Apprendre) and suggested sizing (Portfolio), so we
 * centralize the read/parse/fallback once.
 *
 * Fallback level when no profile is set is "Actif" — the neutral default
 * that shows standard content without infantilizing a first-time visitor
 * nor dumping technical jargon.
 */
const DEFAULT_PROFILE: UserProfile = {
  type: "Actif",
  experience: "Un peu",
  reaction: "J'attends",
  budget: "50-200€",
  suggestedSizing: "2-5% du capital",
}

export type ProfileLevel = UserProfile["type"]

function readProfile(): UserProfile {
  try {
    const raw = localStorage.getItem("foresight.profile")
    if (!raw) return DEFAULT_PROFILE
    const parsed = JSON.parse(raw) as Partial<UserProfile>
    if (!parsed?.type) return DEFAULT_PROFILE
    return { ...DEFAULT_PROFILE, ...parsed } as UserProfile
  } catch {
    return DEFAULT_PROFILE
  }
}

export function useProfile(): UserProfile {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE)

  useEffect(() => {
    setProfile(readProfile())

    const onStorage = (e: StorageEvent) => {
      if (e.key === "foresight.profile") setProfile(readProfile())
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  return profile
}

/** Non-reactive accessor for callers that only need a one-shot read. */
export function getProfile(): UserProfile {
  return readProfile()
}

/* -------------------------------------------------------------------------- */
/*  Profile-derived pure helpers                                              */
/*                                                                            */
/*  These power the 4-axis personalization (type / experience / reaction /    */
/*  budget). They are pure functions of `UserProfile` so they can be called   */
/*  from components, tests, and server-derived code alike.                    */
/* -------------------------------------------------------------------------- */

/** Budget → French-typography sizing copy (uses NBSP before €). */
export function getSizingCopy(profile: UserProfile): string {
  const map: Record<UserProfile["budget"], string> = {
    "<50€": "moins de 50\u00A0€",
    "50-200€": "50 à 200\u00A0€",
    ">200€": "plus de 200\u00A0€",
  }
  return map[profile.budget] ?? "50 à 200\u00A0€"
}

/** Budget → 3 preset amounts (€) for quick-pick chips. */
export function getAmountPresets(profile: UserProfile): number[] {
  if (profile.budget === "<50€") return [10, 25, 50]
  if (profile.budget === "50-200€") return [50, 100, 200]
  return [200, 500, 1000]
}

/** Budget → reasonable default ticket amount (€). */
export function getDefaultAmount(profile: UserProfile): number {
  return getAmountPresets(profile)[1]
}

/** Type → default sort order on the signals list. */
export function getInitialSort(profile: UserProfile): "score" | "recent" {
  return profile.type === "Découvreur" ? "score" : "recent"
}

/** Type → whether advanced filters panel opens by default. */
export function getAdvancedFiltersExpandedDefault(profile: UserProfile): boolean {
  return profile.type === "Confirmé"
}

/** Experience → depth of pedagogical content to show. */
export function getContentDepth(
  profile: UserProfile,
): "beginner" | "intermediate" | "expert" {
  if (profile.experience === "Jamais") return "beginner"
  if (profile.experience === "Un peu") return "intermediate"
  return "expert"
}

/** Experience → how aggressive tooltips on jargon should be. */
export function getTooltipDensity(
  profile: UserProfile,
): "full" | "light" | "none" {
  if (profile.experience === "Jamais") return "full"
  if (profile.experience === "Un peu") return "light"
  return "none"
}

/** Reaction → % of "vie" remaining that should trigger a soft alert. */
export function getAlertLifeThreshold(profile: UserProfile): number {
  if (profile.reaction === "Sors vite") return 25
  if (profile.reaction === "J'attends") return 15
  return 10
}

/** Reaction → headline copy used on score-decay exit prompts. */
export function getExitCopy(profile: UserProfile): string {
  if (profile.reaction === "Sors vite") return "Vends maintenant\u00A0?"
  if (profile.reaction === "J'attends") return "À surveiller"
  return "Opportunité de renforcer\u00A0?"
}

/** Type → Apprendre welcome banner subtitle. */
export function getApprendreBannerCopy(profile: UserProfile): string {
  if (profile.type === "Découvreur")
    return "Commence par les fondamentaux — on t\u2019accompagne pas à pas."
  if (profile.type === "Actif")
    return "Les concepts qui vont muscler tes décisions."
  return "Méthodes avancées\u00A0: scoring hybride, gestion de capital, exécution optimale."
}
