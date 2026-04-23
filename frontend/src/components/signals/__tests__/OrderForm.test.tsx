import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { MOCK_SIGNALS } from "@/data/signals"
import { OrderForm } from "../OrderForm"

vi.mock("@/hooks/useUserLimits", () => ({
  useUserLimits: () => ({
    data: {
      budgetWeeklyEur: 20,
      maxStakeEur: 10,
      level: 1,
      realTradesCount: 0,
      consecutiveLosses: 0,
      weekSpentEur: 15,
      cooloffUntil: null,
      quizPassed: true,
      ageConfirmed18: true,
    },
    isLoading: false,
    isError: false,
  }),
}))

// The component calls auth helpers + wallet hooks at mount; stub them so the
// test doesn't need the full app context.
vi.mock("@/lib/api/auth", () => ({
  hasToken: () => false,
  clearToken: vi.fn(),
  getToken: () => null,
}))

vi.mock("@/hooks/useAuth", () => ({
  useIsFreePlan: () => false,
}))

vi.mock("@/hooks/useWalletSetup", () => ({
  useWalletSetup: () => ({
    walletConnected: true,
    step: "idle",
    error: null,
    startSetup: vi.fn(),
  }),
}))

vi.mock("@/lib/userPreferences", () => ({
  useUserPreferences: () => ({
    currency: "EUR",
    setCurrency: vi.fn(),
    formatMoney: (n: number) => `${n.toFixed(2)}€`,
  }),
}))

vi.mock("@/lib/useToasts", () => ({
  useToasts: () => ({ addToast: vi.fn(), dismiss: vi.fn() }),
}))

vi.mock("@/lib/useProfile", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("@/lib/useProfile")
  return {
    ...actual,
    useProfile: () => ({
      type: "Actif",
      experience: "Un peu",
      reaction: "J'attends",
      budget: "50-200€",
      completed: true,
    }),
  }
})

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe("OrderForm — limits", () => {
  it("caps slider to maxStakeEur", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))
    const slider = screen.getByRole("slider", { name: /mise/i }) as HTMLInputElement
    // effectiveMax = min(maxStakeEur=10, remaining=5) = 5; maxStakeEur=10 is
    // the displayed upper bound. We assert against the DOM max attribute —
    // the slider itself is bound to the effective max.
    expect(Number(slider.max)).toBe(5)
  })

  it("shows remaining weekly budget", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))
    expect(screen.getByText(/reste\s*5\s*€/i)).toBeInTheDocument()
  })
})
