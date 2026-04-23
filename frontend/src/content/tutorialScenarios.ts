/**
 * Hardcoded tutorial scenarios for the Learn & Trade onboarding flow.
 *
 * Each scenario teaches a specific trading lesson via a paper trade (5€
 * virtual stake, `is_tutorial=true`). The 5 scenarios cover momentum +
 * source quality + price level + risk/reward heuristics.
 *
 * `correctDirection` drives the feedback text only — every trade is
 * recorded, regardless of the user's answer, so the backend can count
 * tutorial_trades_count → tutorial_done gate (5 trades required).
 */

export type TutorialScenario = {
  id: string
  marketId: string
  question: string
  category: string
  entryPrice: number
  narrative: string
  correctDirection: "YES" | "NO"
  explanation: string
}

export const TUTORIAL_SCENARIOS: TutorialScenario[] = [
  {
    id: "s1",
    marketId: "tutorial_1",
    question: "L'équipe X va-t-elle gagner le championnat ?",
    category: "sports",
    entryPrice: 0.35,
    narrative:
      "L'équipe X vient de gagner 4 matchs d'affilée. Le marché a bougé de 0.20 à 0.35 en 48h.",
    correctDirection: "YES",
    explanation:
      "Quand le momentum news + marché s'alignent (4 victoires + hausse de prix), la direction YES est souvent la bonne. Attention cependant : le prix a déjà bougé, une partie du gain potentiel est déjà prise.",
  },
  {
    id: "s2",
    marketId: "tutorial_2",
    question: "Le gouvernement Y va-t-il passer la loi avant fin d'année ?",
    category: "politics",
    entryPrice: 0.78,
    narrative:
      "Le marché est à 0.78. Une news tombe : 3 députés clés annoncent qu'ils voteront contre.",
    correctDirection: "NO",
    explanation:
      "Une news négative sur un marché déjà haut (0.78) crée souvent un retour vers le bas. BUY_NO est justifié quand le marché semblait trop confiant.",
  },
  {
    id: "s3",
    marketId: "tutorial_3",
    question: "Le prix du bitcoin dépassera-t-il 100k$ ce mois ?",
    category: "crypto",
    entryPrice: 0.5,
    narrative:
      "Le marché est pile à 0.50. Une seule news tier-3 dit que 'Elon pense que oui'. Aucune autre source.",
    correctDirection: "NO",
    explanation:
      "Une source unique, tier-3, sur un marché à 0.50 = signal faible. L'habitude du marché quand l'info est mince = il ne bouge pas vraiment, souvent léger retour à la moyenne. Ne jamais trader sur une source unique.",
  },
  {
    id: "s4",
    marketId: "tutorial_4",
    question: "Le taux directeur de la BCE va-t-il baisser en juin ?",
    category: "economics",
    entryPrice: 0.42,
    narrative:
      "3 sources tier-1 (Bloomberg, Reuters, FT) rapportent dans la même heure que Lagarde a laissé entendre une baisse. Prix monte de 0.30 à 0.42.",
    correctDirection: "YES",
    explanation:
      "3 sources tier-1 convergentes = signal fort. Le prix a bougé mais reste dans une zone où il y a de la marge (0.42 → potentiellement 0.70+ si confirmé). Bon setup.",
  },
  {
    id: "s5",
    marketId: "tutorial_5",
    question: "Le pays Z va-t-il ratifier l'accord climat avant la COP ?",
    category: "geopolitics",
    entryPrice: 0.88,
    narrative:
      "Le marché est à 0.88. Une source tier-2 rapporte une déclaration du premier ministre : 'on est presque prêts'.",
    correctDirection: "NO",
    explanation:
      "Un marché à 0.88 a déjà pricé l'accord. Même une news positive n'apporte quasi rien (peu d'upside). Un signal à ce niveau de prix a souvent un mauvais rapport risque/rendement — on s'abstient ou on prend le contre (BUY_NO) en pariant que la résolution finale sera moins nette que prévu.",
  },
]
