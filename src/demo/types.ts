// Modèle de données de la démo (UHM). Tout est mocké ; voir requests.ts.

export type Channel = 'email' | 'form' | 'phone' | 'instagram' | 'facebook' | 'courrier'
export type Category = 'livraison' | 'abonnement' | 'facturation' | 'produit' | 'reclamation'
export type Priority = 'haute' | 'moyenne' | 'basse'
export type Sentiment = 'neutre' | 'mecontent' | 'urgent'
export type ActionType = 'auto' | 'draft' | 'escalate'

/** Résultat de l'analyse IA d'une demande (catégorisation + décision). */
export interface Analysis {
  category: Category
  priority: Priority
  sentiment: Sentiment
  confidence: number // 0–100
  action: ActionType
  reply?: string // si action = auto : la réponse rédigée dans le ton de la marque
  escalationReason?: string // si action = escalate
  escalationTo?: string // l'équipe/agent destinataire
}

/** Une demande entrante. `analysis` = la vérité mockée (ce que renverra l'IA). */
export interface Request {
  id: string
  channel: Channel
  sender: string
  senderRole?: string // « Parent abonné », « Grand-père de Léo », « Comité d'entreprise »…
  message: string
  magazine?: string // produit / titre concerné
  subscriberId?: string // n° d'abonné fictif
  receivedAt: string // heure d'arrivée (affichage)
  analysis: Analysis
  /** Fil omnicanal : des demandes partageant le même threadId = même client/conversation. */
  threadId?: string
  /** Historique client (faux) affiché dans le détail. */
  history?: { label: string; detail: string }[]
}
