import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import Quiz from "../Quiz"

vi.mock("@/lib/api/onboarding", () => ({
  fetchQuizQuestions: vi.fn().mockResolvedValue([
    { id: "q1", question: "Q1?", choices: ["A", "B", "C"] },
    { id: "q2", question: "Q2?", choices: ["X", "Y"] },
    { id: "q3", question: "Q3?", choices: ["1", "2", "3"] },
  ]),
  submitQuiz: vi.fn().mockResolvedValue({ score: 3, total: 3, passed: true }),
}))

function renderQuiz() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Quiz />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("Quiz", () => {
  it("renders all 3 questions after load", async () => {
    renderQuiz()
    await waitFor(() => expect(screen.getByText(/Q1\?/)).toBeInTheDocument())
    expect(screen.getByText(/Q2\?/)).toBeInTheDocument()
    expect(screen.getByText(/Q3\?/)).toBeInTheDocument()
  })

  it("disables submit until all questions answered", async () => {
    renderQuiz()
    await waitFor(() => screen.getByText(/Q1\?/))
    const submit = screen.getByRole("button", { name: /valider/i })
    expect(submit).toBeDisabled()
  })
})
