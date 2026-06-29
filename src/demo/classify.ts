import type { Analysis, Request } from './types'

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/**
 * ⚙️ POINT DE BRANCHEMENT IA — LA fonction à remplacer pour passer en réel.
 *
 * En démo : on simule le temps d'analyse puis on renvoie l'analyse pré-écrite.
 * En production : ici tournerait le vrai modèle (appel API) qui lit le message,
 * détecte catégorie / priorité / sentiment, calcule un score de confiance et
 * décide de l'action (réponse auto rédigée OU escalade humaine).
 * La signature ne change pas — seul le corps est à remplacer.
 */
export async function classifyRequest(req: Request): Promise<Analysis> {
  await wait(750 + Math.random() * 450) // ≈ temps d'analyse perçu
  return req.analysis
}
