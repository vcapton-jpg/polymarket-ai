import { apiGet, apiPost } from "./client"

export type OnboardingStatus = {
  profileDone: boolean
  tutorialTradesCount: number
  tutorialDone: boolean
  quizDone: boolean
  budgetDone: boolean
  canTradeReal: boolean
}

type WireOnboardingStatus = {
  profile_done: boolean
  tutorial_trades_count: number
  tutorial_done: boolean
  quiz_done: boolean
  budget_done: boolean
  can_trade_real: boolean
}

function hydrateStatus(w: WireOnboardingStatus): OnboardingStatus {
  return {
    profileDone: w.profile_done,
    tutorialTradesCount: w.tutorial_trades_count,
    tutorialDone: w.tutorial_done,
    quizDone: w.quiz_done,
    budgetDone: w.budget_done,
    canTradeReal: w.can_trade_real,
  }
}

export async function fetchOnboardingStatus(): Promise<OnboardingStatus> {
  const wire = await apiGet<WireOnboardingStatus>("/onboarding/status")
  return hydrateStatus(wire)
}

export async function submitBudget(input: {
  budgetWeeklyEur: number
  maxStakeEur: number
  ageConfirmed18: boolean
  cguAccepted: boolean
}): Promise<void> {
  await apiPost("/onboarding/budget", {
    budget_weekly_eur: input.budgetWeeklyEur,
    max_stake_eur: input.maxStakeEur,
    age_confirmed_18: input.ageConfirmed18,
    cgu_accepted: input.cguAccepted,
  })
}

export type QuizQuestion = { id: string; question: string; choices: string[] }

export async function fetchQuizQuestions(): Promise<QuizQuestion[]> {
  const r = await apiGet<{ questions: QuizQuestion[] }>("/quiz/questions")
  return r.questions
}

export async function submitQuiz(
  answers: Record<string, number>,
): Promise<{ score: number; total: number; passed: boolean }> {
  return apiPost("/quiz/submit", { answers })
}
