import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { WhyThisMatters } from "../WhyThisMatters"

describe("WhyThisMatters", () => {
  it("renders reasoning and tier-mix badges", () => {
    render(
      <WhyThisMatters
        reasoning="Reuters Top News and BBC confirm the summit date, addressing the market resolution criteria directly."
        sourceTierMix={{ tier_1: 3, tier_2: 1 }}
      />,
    )
    expect(screen.getByText(/Reuters Top News and BBC confirm/)).toBeInTheDocument()
    expect(screen.getByText(/3 sources Tier 1/i)).toBeInTheDocument()
    expect(screen.getByText(/1 source Tier 2/i)).toBeInTheDocument()
  })

  it("hides when reasoning is null", () => {
    const { container } = render(<WhyThisMatters reasoning={null} sourceTierMix={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
