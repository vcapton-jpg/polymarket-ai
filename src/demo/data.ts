// ─────────────────────────────────────────────────────────────────────────────
//  DONNÉES DE LA DÉMO — 100 % mockées, en dur. Aucune API.
//  Tout est pré-écrit pour donner l'illusion d'un produit qui tourne.
//  Pour réadapter à un autre prospect : on édite ce fichier.
// ─────────────────────────────────────────────────────────────────────────────

/** Indicateurs clés affichés sur la Vue d'ensemble. */
export const KPIS = {
  treatedToday: 1247,
  avgResponseSec: 8,
  manualResponse: '4 h 30',
  automationRate: 73,
  hoursSavedWeek: 142,
} as const

/** Volume de demandes entrantes sur la journée (par tranche horaire). */
export const HOURLY_VOLUME: { h: string; v: number }[] = [
  { h: '7h', v: 28 },
  { h: '8h', v: 64 },
  { h: '9h', v: 118 },
  { h: '10h', v: 142 },
  { h: '11h', v: 131 },
  { h: '12h', v: 86 },
  { h: '13h', v: 73 },
  { h: '14h', v: 128 },
  { h: '15h', v: 121 },
  { h: '16h', v: 97 },
  { h: '17h', v: 79 },
  { h: '18h', v: 52 },
]

/** Répartition des demandes par canal (omnicanal). */
export const CHANNELS: { label: string; value: number; color: string }[] = [
  { label: 'Email', value: 47, color: '#7c5cff' },
  { label: 'Formulaire web', value: 22, color: '#34d399' },
  { label: 'Téléphone', value: 16, color: '#fbbf24' },
  { label: 'Réseaux sociaux', value: 11, color: '#60a5fa' },
  { label: 'Courrier', value: 4, color: '#f472b6' },
]

/** Répartition des demandes par catégorie. */
export const CATEGORIES: { label: string; value: number; color: string }[] = [
  { label: 'Livraison', value: 34, color: '#7c5cff' },
  { label: 'Abonnement', value: 27, color: '#9a82ff' },
  { label: 'Facturation', value: 18, color: '#34d399' },
  { label: 'Produit / éditorial', value: 13, color: '#60a5fa' },
  { label: 'Réclamation', value: 8, color: '#fb7185' },
]
