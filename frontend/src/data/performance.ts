import type { PerformanceStats } from "@/types/signal"

export const MOCK_PERFORMANCE: PerformanceStats = {
  // ---- User first (Foresight puts the user at the center) ----
  userSignalsFollowed: 12,
  userCorrectPredictions: 8,
  userWinRate: 0.67,
  userBestCategory: "Géopolitique",
  userBestCategoryWinRate: 0.83,
  userEstimatedGain: 47,
  userWinRateByCategory: [
    { category: "Géopolitique", winRate: 0.83, signalCount: 6 },
    { category: "Économie", winRate: 0.67, signalCount: 3 },
    { category: "Crypto", winRate: 0.5, signalCount: 2 },
    { category: "Politique", winRate: 0.33, signalCount: 3 },
    { category: "Sport", winRate: 1.0, signalCount: 1 },
    { category: "Science", winRate: 0.0, signalCount: 1 },
  ],

  // ---- Telegram funnel ----
  telegramAlertsReceived: 14,
  telegramAlertsFollowed: 8,
  telegramFollowRate: 0.57,

  // ---- Platform (displayed as discreet footer) ----
  totalSignalsGenerated: 2847,
  platformWinRate: 0.71,
  platformAvgScore: 68.4,
  avgPipelineDelay: 87,

  // ---- Charts ----
  signalsByCategory: [
    { category: "Géopolitique", count: 968, percentage: 34 },
    { category: "Politique", count: 627, percentage: 22 },
    { category: "Économie", count: 513, percentage: 18 },
    { category: "Crypto", count: 342, percentage: 12 },
    { category: "Sport", count: 228, percentage: 8 },
    { category: "Science", count: 169, percentage: 6 },
  ],

  winRateOverTime: [
    { date: "2026-03-20", platform: 0.68, user: 0.6 },
    { date: "2026-03-27", platform: 0.7, user: 0.65 },
    { date: "2026-04-03", platform: 0.72, user: 0.67 },
    { date: "2026-04-10", platform: 0.71, user: 0.67 },
    { date: "2026-04-17", platform: 0.73, user: 0.67 },
  ],

  gainsOverTime: [
    { week: "2026-W10", gain: -5 },
    { week: "2026-W11", gain: 12 },
    { week: "2026-W12", gain: 18 },
    { week: "2026-W13", gain: -8 },
    { week: "2026-W14", gain: 10 },
    { week: "2026-W15", gain: 5 },
    { week: "2026-W16", gain: 15 },
  ],
}

export type TopSignal = {
  rank: number
  signalId: string
  question: string
  score: number
  marketMove: number
  category: string
}

export const MOCK_TOP_SIGNALS_MONTH: TopSignal[] = [
  { rank: 1, signalId: "SIG-2772", question: "Israël × Liban — échange de prisonniers", score: 84, marketMove: 38, category: "Géopolitique" },
  { rank: 2, signalId: "SIG-2801", question: "Fed rate decision mars 2026", score: 79, marketMove: 22, category: "Économie" },
  { rank: 3, signalId: "SIG-2755", question: "UFC 309 — Makhachev conserve son titre", score: 77, marketMove: 19, category: "Sport" },
  { rank: 4, signalId: "SIG-2720", question: "NASA Artemis III décolle avant fin 2026", score: 74, marketMove: 15, category: "Science" },
  { rank: 5, signalId: "SIG-2740", question: "Trump rencontre le Pape Léon XIV", score: 61, marketMove: -8, category: "Politique" },
]

export type PersonalInsight = {
  type: "positive" | "info" | "warning"
  icon: "bulb" | "alert"
  title: string
  body: string
}

export const MOCK_PERSONAL_INSIGHTS: PersonalInsight[] = [
  {
    type: "positive",
    icon: "bulb",
    title: "Tes meilleurs signaux sont en Géopolitique.",
    body: "Continue à surveiller cette catégorie en priorité.",
  },
  {
    type: "info",
    icon: "bulb",
    title: "Les signaux > 75 sont corrects 81% du temps.",
    body: "Quand le score est fort, la conviction aussi.",
  },
  {
    type: "warning",
    icon: "alert",
    title: "Tu as tendance à sortir trop tôt.",
    body: "3 de tes positions auraient gagné +30% en tenant plus longtemps.",
  },
]

export type ScoreVsMoveDataPoint = {
  score: number
  marketMove: number
  correct: boolean
}

export const MOCK_SCORE_VS_MOVE: ScoreVsMoveDataPoint[] = [
  { score: 92, marketMove: 42, correct: true },
  { score: 88, marketMove: 35, correct: true },
  { score: 86, marketMove: 38, correct: true },
  { score: 84, marketMove: 28, correct: true },
  { score: 81, marketMove: 22, correct: true },
  { score: 79, marketMove: 31, correct: true },
  { score: 77, marketMove: 19, correct: true },
  { score: 76, marketMove: -4, correct: false },
  { score: 74, marketMove: 15, correct: true },
  { score: 72, marketMove: 12, correct: true },
  { score: 71, marketMove: 9, correct: true },
  { score: 69, marketMove: 6, correct: true },
  { score: 67, marketMove: -3, correct: false },
  { score: 66, marketMove: 8, correct: true },
  { score: 64, marketMove: -6, correct: false },
  { score: 61, marketMove: -8, correct: false },
  { score: 58, marketMove: -2, correct: false },
  { score: 54, marketMove: 4, correct: true },
]

export type WeeklyPnLPoint = {
  week: string
  pnl: number
  cumulative: number
}

export const MOCK_WEEKLY_PNL: WeeklyPnLPoint[] = [
  { week: "S-7", pnl: -5, cumulative: -5 },
  { week: "S-6", pnl: 12, cumulative: 7 },
  { week: "S-5", pnl: 18, cumulative: 25 },
  { week: "S-4", pnl: -8, cumulative: 17 },
  { week: "S-3", pnl: 10, cumulative: 27 },
  { week: "S-2", pnl: 5, cumulative: 32 },
  { week: "S-1", pnl: 15, cumulative: 47 },
]
