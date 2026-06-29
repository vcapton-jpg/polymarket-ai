import {
  LayoutDashboard,
  Inbox,
  Tags,
  Sparkles,
  PencilLine,
  ShieldAlert,
  BarChart3,
  Rocket,
  Settings,
} from 'lucide-react'
import type { ComponentType } from 'react'

export type View =
  | 'overview'
  | 'inbox'
  | 'categories'
  | 'replies'
  | 'brouillons'
  | 'escalations'
  | 'analytics'
  | 'onboarding'
  | 'settings'

export type NavItem = {
  id: View
  label: string
  icon: ComponentType<{ className?: string }>
  sub?: string
}

/** Vues principales (haut de la sidebar). */
export const NAV_MAIN: NavItem[] = [
  { id: 'overview', label: "Vue d'ensemble", icon: LayoutDashboard, sub: "État du service client" },
  { id: 'inbox', label: 'Boîte unifiée', icon: Inbox, sub: 'Tous les canaux, une file' },
  { id: 'categories', label: 'Catégories', icon: Tags, sub: 'Demandes triées & classées' },
  { id: 'replies', label: 'Réponses auto', icon: Sparkles, sub: 'Modèles dans votre ton' },
  { id: 'brouillons', label: 'Brouillons', icon: PencilLine, sub: 'À valider en un clic' },
  { id: 'escalations', label: 'Escalades', icon: ShieldAlert, sub: 'Transmis à un humain' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, sub: 'Performance & coûts' },
]

/** Vues secondaires (bas de la sidebar). */
export const NAV_FOOTER: NavItem[] = [
  { id: 'onboarding', label: 'Démarrage', icon: Rocket, sub: 'Pilote sans risque' },
  { id: 'settings', label: 'Paramètres', icon: Settings },
]

export const ALL_VIEWS = [...NAV_MAIN, ...NAV_FOOTER]
