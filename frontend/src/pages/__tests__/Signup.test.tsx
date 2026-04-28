import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import Signup from "../Signup"

// Mock the auth client (tests shouldn't hit the network)
vi.mock("@/lib/api/auth", () => ({
  registerApi: vi.fn().mockResolvedValue({
    token: "t",
    user: { id: 1, email: "a@b.com", plan: "free", trial_ends_at: null, card_attached: false },
  }),
  setToken: vi.fn(),
  clearToken: vi.fn(),
  hasToken: vi.fn().mockReturnValue(false),
  fetchMe: vi.fn().mockResolvedValue(null),
}))

// Mock toasts (hook may emit a "draft found" toast)
vi.mock("@/lib/useToasts", () => ({
  useToasts: () => ({ addToast: vi.fn() }),
}))

function renderSignup() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Signup />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("Signup — age gate + CGU", () => {
  it("disables submit when age_18 is unchecked even with other acknowledgements", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/^mot de passe$/i), "password123")
    // Check risk + CGU, but NOT age18
    await userEvent.click(screen.getByLabelText(/outil d.analyse/i))
    await userEvent.click(screen.getByLabelText(/j.accepte les cgu/i))
    const submit = screen.getByRole("button", { name: /créer mon compte/i })
    expect(submit).toBeDisabled()
  })

  it("disables submit when CGU is unchecked", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/^mot de passe$/i), "password123")
    await userEvent.click(screen.getByLabelText(/outil d.analyse/i))
    await userEvent.click(screen.getByLabelText(/j.ai 18 ans/i))
    const submit = screen.getByRole("button", { name: /créer mon compte/i })
    expect(submit).toBeDisabled()
  })

  it("disables submit when country of residence is unset (Legal-PR-1 B3)", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/^mot de passe$/i), "password123")
    await userEvent.click(screen.getByLabelText(/outil d.analyse/i))
    await userEvent.click(screen.getByLabelText(/j.ai 18 ans/i))
    await userEvent.click(screen.getByLabelText(/j.accepte les cgu/i))
    // Country still empty → submit disabled.
    const submit = screen.getByRole("button", { name: /créer mon compte/i })
    expect(submit).toBeDisabled()
  })

  it("enables submit when email, password, risk, age_18, CGU, and country are all set", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/^mot de passe$/i), "password123")
    await userEvent.click(screen.getByLabelText(/outil d.analyse/i))
    await userEvent.click(screen.getByLabelText(/j.ai 18 ans/i))
    await userEvent.click(screen.getByLabelText(/j.accepte les cgu/i))
    await userEvent.selectOptions(screen.getByLabelText(/pays de résidence/i), "FR")
    const submit = screen.getByRole("button", { name: /créer mon compte/i })
    expect(submit).not.toBeDisabled()
  })
})
