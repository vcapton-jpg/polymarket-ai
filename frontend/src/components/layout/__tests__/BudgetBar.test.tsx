import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { BudgetBar } from "../BudgetBar"

const mockLimits = vi.hoisted(() => ({
  current: null as null | {
    budgetWeeklyEur: number
    maxStakeEur: number
    level: number
    realTradesCount: number
    consecutiveLosses: number
    weekSpentEur: number
    cooloffUntil: string | null
    quizPassed: boolean
    ageConfirmed18: boolean
  },
}))

vi.mock("@/hooks/useUserLimits", () => ({
  useUserLimits: () => ({
    data: mockLimits.current ?? undefined,
    isLoading: false,
    isError: false,
  }),
}))

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe("BudgetBar", () => {
  it("returns null when limits data is undefined", () => {
    mockLimits.current = null
    const { container } = render(wrap(<BudgetBar />))
    expect(container).toBeEmptyDOMElement()
  })

  it("shows spent / budget when limits are available", () => {
    mockLimits.current = {
      budgetWeeklyEur: 20,
      maxStakeEur: 10,
      level: 1,
      realTradesCount: 0,
      consecutiveLosses: 0,
      weekSpentEur: 15,
      cooloffUntil: null,
      quizPassed: true,
      ageConfirmed18: true,
    }
    render(wrap(<BudgetBar />))
    expect(screen.getByText(/15€\s*\/\s*20€/)).toBeInTheDocument()
    expect(
      screen.getByRole("progressbar", { name: /budget hebdomadaire/i }),
    ).toHaveAttribute("aria-valuenow", "75")
  })

  it("shows cooloff badge when cooloff_until is in the future", () => {
    const future = new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString()
    mockLimits.current = {
      budgetWeeklyEur: 20,
      maxStakeEur: 10,
      level: 1,
      realTradesCount: 3,
      consecutiveLosses: 3,
      weekSpentEur: 5,
      cooloffUntil: future,
      quizPassed: true,
      ageConfirmed18: true,
    }
    render(wrap(<BudgetBar />))
    expect(screen.getByRole("status")).toHaveTextContent(/en pause/i)
  })
})
