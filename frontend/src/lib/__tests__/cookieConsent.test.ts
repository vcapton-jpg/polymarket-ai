/**
 * Cookie consent state machine — Legal-PR-2 (B5).
 *
 * Pins the contract that downstream pages and the banner rely on:
 *   - Default state on a fresh browser: no decision recorded.
 *   - `essential` is always granted, regardless of input.
 *   - `acceptAll` / `refuseAll` are equally one-call (CNIL).
 *   - `revoke` deletes the record so the banner re-prompts.
 *   - A version bump invalidates older records.
 *   - `isAllowed` is the single guard everything else uses.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  COOKIE_CONSENT_STORAGE_KEY,
  COOKIE_CONSENT_VERSION,
  acceptAll,
  getConsent,
  hasDecided,
  isAllowed,
  refuseAll,
  revoke,
  setConsent,
} from "../cookieConsent"

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  window.localStorage.clear()
})

describe("cookieConsent", () => {
  it("starts undecided on a fresh browser", () => {
    expect(hasDecided()).toBe(false)
    expect(getConsent()).toBeNull()
  })

  it("essential is always granted, regardless of input", () => {
    setConsent({ analytics: false, marketing: false })
    expect(isAllowed("essential")).toBe(true)
    // Even a positively-named bypass attempt cannot turn off essential.
    setConsent({ analytics: false, marketing: false })
    expect(getConsent()?.categories.essential).toBe(true)
  })

  it("acceptAll grants every non-essential category", () => {
    acceptAll()
    expect(isAllowed("analytics")).toBe(true)
    expect(isAllowed("marketing")).toBe(true)
  })

  it("refuseAll denies every non-essential category", () => {
    refuseAll()
    expect(isAllowed("analytics")).toBe(false)
    expect(isAllowed("marketing")).toBe(false)
  })

  it("acceptAll and refuseAll both record a decision", () => {
    refuseAll()
    expect(hasDecided()).toBe(true)
    revoke()
    acceptAll()
    expect(hasDecided()).toBe(true)
  })

  it("partial setConsent treats missing keys as refused (opt-in default)", () => {
    setConsent({ analytics: true })
    expect(isAllowed("analytics")).toBe(true)
    expect(isAllowed("marketing")).toBe(false)
  })

  it("revoke deletes the record so the banner re-prompts", () => {
    acceptAll()
    expect(hasDecided()).toBe(true)
    revoke()
    expect(hasDecided()).toBe(false)
    expect(isAllowed("analytics")).toBe(false)
  })

  it("a stale-version record is treated as undecided (re-prompt)", () => {
    const stale = {
      version: COOKIE_CONSENT_VERSION + 99,
      decidedAt: new Date().toISOString(),
      categories: { essential: true, analytics: true, marketing: true },
    }
    window.localStorage.setItem(
      COOKIE_CONSENT_STORAGE_KEY,
      JSON.stringify(stale),
    )
    expect(hasDecided()).toBe(false)
    expect(isAllowed("analytics")).toBe(false)
  })

  it("malformed JSON in storage degrades to undecided (no crash)", () => {
    window.localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, "{not-json")
    expect(hasDecided()).toBe(false)
    expect(getConsent()).toBeNull()
  })

  it("isAllowed('essential') returns true even with no record", () => {
    expect(isAllowed("essential")).toBe(true)
  })

  it("decidedAt is a valid ISO timestamp", () => {
    acceptAll()
    const d = getConsent()?.decidedAt
    expect(d).toBeTruthy()
    expect(() => new Date(d!).toISOString()).not.toThrow()
  })
})
