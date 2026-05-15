import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { WhyThisMatters, parseReasoning } from "../WhyThisMatters"

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

  it("splits the v2 machine pin from the prose and renders an FR data strip", () => {
    render(
      <WhyThisMatters
        reasoning={
          "Le sommet est confirmé par trois sources tier-1. " +
          "Market at 0.6400, my estimate 0.80, so BUY_YES with strength 0.6."
        }
        sourceTierMix={null}
      />,
    )
    // Prose kept, raw pin removed from the visible paragraph
    expect(screen.getByText(/Le sommet est confirmé par trois sources/)).toBeInTheDocument()
    expect(screen.queryByText(/Market at 0\.6400/)).not.toBeInTheDocument()
    // FR data strip rendered — "64 %" / "80 %" appear twice (strip +
    // sentence), "+16 pts" is unique to the strip.
    expect(screen.getAllByText("64 %").length).toBeGreaterThan(0)
    expect(screen.getAllByText("80 %").length).toBeGreaterThan(0)
    expect(screen.getByText("+16 pts")).toBeInTheDocument()
    expect(screen.getByText(/oriente vers/)).toBeInTheDocument()
  })
})

describe("parseReasoning", () => {
  it("extracts the pin and computes the edge", () => {
    const { prose, pin } = parseReasoning(
      "Analyse détaillée ici. Market at 0.6400, my estimate 0.80, so BUY_YES with strength 0.6.",
    )
    expect(prose).toBe("Analyse détaillée ici.")
    expect(pin).not.toBeNull()
    expect(pin!.marketPct).toBe(64)
    expect(pin!.estimatePct).toBe(80)
    expect(pin!.edgePts).toBe(16)
    expect(pin!.direction).toBe("BUY YES")
  })

  it("handles BUY_NO with a negative edge", () => {
    const { pin } = parseReasoning(
      "Le marché surévalue. Market at 0.70, my estimate 0.55, so BUY_NO with strength 0.4.",
    )
    expect(pin!.direction).toBe("BUY NO")
    expect(pin!.edgePts).toBe(-15)
  })

  it("returns the raw text untouched when there is no pin (v1 reasoning)", () => {
    const raw = "Reuters and BBC confirm the summit date directly."
    const { prose, pin } = parseReasoning(raw)
    expect(prose).toBe(raw)
    expect(pin).toBeNull()
  })

  it("tolerates a missing 'with strength' clause", () => {
    const { pin } = parseReasoning("Contexte. Market at 0.30, my estimate 0.45, so BUY_YES.")
    expect(pin).not.toBeNull()
    expect(pin!.marketPct).toBe(30)
    expect(pin!.estimatePct).toBe(45)
    expect(pin!.edgePts).toBe(15)
  })
})
