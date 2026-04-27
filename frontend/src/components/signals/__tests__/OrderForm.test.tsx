import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MOCK_SIGNALS } from "@/data/signals"
import { OrderForm } from "../OrderForm"
import { ApiError } from "@/lib/api/client"

// The per-signal spending caps (slider clamp + cooloff blocker + budget bar)
// were removed 2026-04-27. The form now exposes the USDC stake input as the
// only path. These tests pin that contract so a future regression that
// reintroduces a slider clamp without re-evaluating the cap design fails.

// Stub i18n so `t()` returns the FR translation the rest of the test
// expects (the form is i18n-migrated as of 2026-04-27 audit P0-7;
// without this stub `t()` falls back to the raw key and breaks the
// assertions that match French strings).
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, vars?: Record<string, unknown>) => {
      const dict: Record<string, string> = {
        "signal.cta.takePosition": "Prendre position",
        "orderForm.stakeLabel": "Mise (USDC)",
        "orderForm.amountAria": "Montant USDC",
        "orderForm.presetsAria": "Mises rapides",
        "orderForm.gainIf": "Gain si ✓",
        "orderForm.lossIf": "Perte si ✗",
        "orderForm.feesNote": "Montants hors frais Polymarket.",
        "orderForm.totalLossWarning":
          "⚠ Perte totale possible : si l'événement résout contre toi, tu perds 100 % de ta mise.",
        "orderForm.buyCta": `Acheter ${vars?.shares ?? ""} parts ${vars?.direction ?? ""}`,
        "orderForm.submittedCta": "Ordre transmis à Polymarket",
        "orderForm.successToastTitle": "Position ouverte — direction portfolio…",
        "orderForm.successToastDetail": "Position ouverte sur Polymarket",
        "orderForm.rejection.inCooloff.title": "Tu es en pause (cooloff)",
        "orderForm.rejection.inCooloff.description":
          "3 pertes consécutives — le serveur bloque les nouveaux trades pendant 24h.",
        "orderForm.rejection.ageNotConfirmed.title": "Confirmation 18+ requise",
        "orderForm.rejection.ageNotConfirmed.description":
          "Vérifie ton profil avant de prendre position.",
        "orderForm.rejection.generic.title": "Trade refusé par le serveur",
        "orderForm.rejection.generic.descriptionFallback": "Réessaie plus tard.",
      }
      return dict[key] ?? key
    },
  }),
}))

vi.mock("@/lib/api/auth", () => ({
  hasToken: () => true,
  clearToken: vi.fn(),
  getToken: () => "stub-token",
}))

vi.mock("@/lib/api/trading", () => ({
  placeTrade: vi.fn(),
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

// ── 403 rollback regression net ───────────────────────────────────────
//
// PR #11 removed the cooloff blocker JSX and the `inCooloff` submit-disabled
// guard. The backend at `app/api/routes/trading.py` still raises HTTP 403
// on `in_cooloff` / `age_not_confirmed` — without rollback, the optimistic
// localStorage write + green success toast + 1.5s navigate to /portfolio
// all fired regardless of the 403, leaving rejected users on a phantom
// position. These tests pin the rollback contract.

describe("OrderForm — 403 rollback contract", () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("removes the optimistic position from localStorage when backend returns 403 in_cooloff", async () => {
    const { placeTrade } = await import("@/lib/api/trading")
    vi.mocked(placeTrade).mockRejectedValueOnce(
      new ApiError(403, "in_cooloff", { detail: { reason: "in_cooloff" } }),
    )

    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))

    const submit = screen.getByRole("button", { name: /acheter/i })
    fireEvent.click(submit)

    await waitFor(() => {
      const raw = window.localStorage.getItem("foresight.positions")
      const arr: unknown[] = raw ? JSON.parse(raw) : []
      expect(arr).toHaveLength(0)
    })
  })

  it("removes the optimistic position from localStorage when backend returns 403 age_not_confirmed", async () => {
    const { placeTrade } = await import("@/lib/api/trading")
    vi.mocked(placeTrade).mockRejectedValueOnce(
      new ApiError(403, "age_not_confirmed", {
        detail: { reason: "age_not_confirmed" },
      }),
    )

    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))

    const submit = screen.getByRole("button", { name: /acheter/i })
    fireEvent.click(submit)

    await waitFor(() => {
      const raw = window.localStorage.getItem("foresight.positions")
      const arr: unknown[] = raw ? JSON.parse(raw) : []
      expect(arr).toHaveLength(0)
    })
  })

  it("KEEPS the optimistic position on a non-403 failure (network / 5xx)", async () => {
    const { placeTrade } = await import("@/lib/api/trading")
    vi.mocked(placeTrade).mockRejectedValueOnce(new Error("network down"))

    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} />))

    const submit = screen.getByRole("button", { name: /acheter/i })
    fireEvent.click(submit)

    await waitFor(() => {
      const raw = window.localStorage.getItem("foresight.positions")
      const arr: unknown[] = raw ? JSON.parse(raw) : []
      expect(arr).toHaveLength(1)
    })
  })
})
