import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { MOCK_SIGNALS } from "@/data/signals"
import { OrderForm } from "../OrderForm"

// The per-signal spending caps (slider clamp + cooloff blocker + budget bar)
// were removed 2026-04-27. The form now exposes the USDC stake input as the
// only path. These tests pin that contract so a future regression that
// reintroduces a slider clamp without re-evaluating the cap design fails.

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

describe("OrderForm — stake input (post per-signal-cap removal)", () => {
  it("renders the USDC stake input", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))
    expect(
      screen.getByRole("spinbutton", { name: /montant usdc/i }),
    ).toBeInTheDocument()
  })

  it("does NOT render a stake slider", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))
    expect(
      screen.queryByRole("slider", { name: /mise/i }),
    ).not.toBeInTheDocument()
  })

  it("does NOT render a cooloff blocker", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))
    expect(screen.queryByText(/en pause \(cooloff\)/i)).not.toBeInTheDocument()
  })
})
