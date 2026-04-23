import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { TimelineEvent } from "@/types/signal"
import { SignalTimeline } from "../SignalTimeline"

const makeEvents = (count: number): TimelineEvent[] =>
  Array.from({ length: count }, (_, i) => ({
    at: new Date(Date.now() - (count - i) * 60 * 1000).toISOString(),
    source: `Source ${i + 1}`,
    type: i % 2 === 0 ? "news" : "market_move",
    headline: `Headline ${i + 1}`,
    detail: i % 3 === 0 ? `Detail ${i + 1}` : null,
  }))

describe("SignalTimeline", () => {
  it("renders nothing when timeline is empty", () => {
    const { container } = render(<SignalTimeline events={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("shows first 8 events and a toggle button when more than 8", async () => {
    const events = makeEvents(11)
    render(<SignalTimeline events={events} />)
    // First 8 visible
    expect(screen.getByText("Headline 1")).toBeInTheDocument()
    expect(screen.getByText("Headline 8")).toBeInTheDocument()
    expect(screen.queryByText("Headline 9")).not.toBeInTheDocument()
    // Toggle button present
    expect(screen.getByRole("button", { name: /voir plus/i })).toBeInTheDocument()
    // Click to expand
    await userEvent.click(screen.getByRole("button", { name: /voir plus/i }))
    expect(screen.getByText("Headline 9")).toBeInTheDocument()
  })

  it("renders all events without toggle when 8 or fewer", () => {
    const events = makeEvents(5)
    render(<SignalTimeline events={events} />)
    expect(screen.getByText("Headline 5")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /voir plus/i })).not.toBeInTheDocument()
  })
})
