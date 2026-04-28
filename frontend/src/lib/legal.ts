/**
 * Central legal-info registry — read by Mentions légales, CGV, Privacy.
 *
 * The five identification fields below are mandatory under LCEN art. 6.III
 * (mentions légales) and L221-5 (CGV) before any public sale. They MUST
 * be set via env vars at build time:
 *
 *   VITE_LEGAL_COMPANY_NAME       — e.g. "Foresight SAS"
 *   VITE_LEGAL_COMPANY_CAPITAL    — e.g. "10 000 €"
 *   VITE_LEGAL_COMPANY_SIREN      — 9 digits, e.g. "912 345 678"
 *   VITE_LEGAL_COMPANY_ADDRESS    — full postal address
 *   VITE_LEGAL_PUB_DIRECTOR       — name of the publishing director
 *   VITE_LEGAL_HOSTING_NAME       — e.g. "Hetzner Online GmbH"
 *   VITE_LEGAL_HOSTING_ADDRESS    — full postal address
 *   VITE_LEGAL_HOSTING_PHONE      — international format
 *   VITE_LEGAL_DPO_EMAIL          — RGPD Art. 37 designated DPO contact
 *   VITE_LEGAL_CONTACT_EMAIL      — general contact (defaults to contact@…)
 *
 * Any value that resolves to the literal sentinel `LEGAL_PLACEHOLDER`
 * is rendered as a visible warning and surfaces in the operator's
 * grep / build-time check, instead of being silently empty. This is
 * the chain that prevents a sneak public-launch with stub data.
 */

const PLACEHOLDER = "LEGAL_PLACEHOLDER"

function read(envKey: string, fallback: string = PLACEHOLDER): string {
  const value = (import.meta.env as Record<string, string | undefined>)[envKey]
  return (value && value.trim()) || fallback
}

export const LEGAL = {
  company: {
    name: read("VITE_LEGAL_COMPANY_NAME", "Foresight SAS"),
    capital: read("VITE_LEGAL_COMPANY_CAPITAL"),
    siren: read("VITE_LEGAL_COMPANY_SIREN"),
    address: read("VITE_LEGAL_COMPANY_ADDRESS"),
    pubDirector: read("VITE_LEGAL_PUB_DIRECTOR"),
  },
  hosting: {
    name: read("VITE_LEGAL_HOSTING_NAME"),
    address: read("VITE_LEGAL_HOSTING_ADDRESS"),
    phone: read("VITE_LEGAL_HOSTING_PHONE"),
  },
  contact: {
    general: read("VITE_LEGAL_CONTACT_EMAIL", "contact@foresight.app"),
    dpo: read("VITE_LEGAL_DPO_EMAIL", "dpo@foresight.app"),
  },
} as const

/**
 * Helper used by the legal pages to render a slot value with an inline
 * warning when the env var is not set. This makes placeholders
 * impossible to miss in a screenshot review and keeps the page usable
 * while the corporate paperwork is being finalised.
 */
export function legalSlot(value: string): string {
  return value === PLACEHOLDER ? "[À compléter avant production]" : value
}

export function isLegalConfigured(): boolean {
  // The five LCEN-mandatory editor fields PLUS the three hosting fields.
  // DPO + general contact have safe fallbacks so they don't gate this.
  return [
    LEGAL.company.name,
    LEGAL.company.capital,
    LEGAL.company.siren,
    LEGAL.company.address,
    LEGAL.company.pubDirector,
    LEGAL.hosting.name,
    LEGAL.hosting.address,
    LEGAL.hosting.phone,
  ].every((v) => v !== PLACEHOLDER)
}

export const LEGAL_PLACEHOLDER_SENTINEL = PLACEHOLDER
