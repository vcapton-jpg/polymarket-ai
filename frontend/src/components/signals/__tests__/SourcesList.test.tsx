import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { SignalSource } from "@/types/signal"
import { SourcesList } from "../SourcesList"

const sources: SignalSource[] = [
  {
    newsId: 1,
    title: "Trump confirms summit timing",
    url: "https://reuters.com/a",
    sourceName: "Reuters",
    sourceTier: 1,
    publishDate: new Date(Date.now() - 23 * 60 * 1000).toISOString(),
    excerpt: "summit confirmed for April 28",
    relevanceScore: 0.9,
    role: "primary",
  },
  {
    newsId: 2,
    title: "Officials comment",
    url: "https://bbc.co.uk/a",
    sourceName: "BBC",
    sourceTier: 2,
    publishDate: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    excerpt: null,
    relevanceScore: 0.5,
    role: "supporting",
  },
]

describe("SourcesList", () => {
  it("renders count and items sorted by relevance", () => {
    render(<SourcesList sources={sources} />)
    expect(screen.getByText(/Sources \(2\)/i)).toBeInTheDocument()
    const links = screen.getAllByRole("link")
    expect(links[0]).toHaveAttribute("href", "https://reuters.com/a")
    expect(links[1]).toHaveAttribute("href", "https://bbc.co.uk/a")
  })

  it("renders excerpt with quotation marks when present", () => {
    render(<SourcesList sources={sources} />)
    expect(screen.getByText(/« summit confirmed for April 28 »/)).toBeInTheDocument()
  })

  it("renders nothing when empty", () => {
    const { container } = render(<SourcesList sources={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
