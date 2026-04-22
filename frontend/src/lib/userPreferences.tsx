import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  type Currency,
  MOCK_EXCHANGE_RATE_USD_TO_EUR,
  isCurrency,
  formatCurrency as formatCurrencyRaw,
} from "./formatCurrency"
import {
  LANGUAGE_STORAGE_KEY,
  type SupportedLanguage,
  isSupportedLanguage,
} from "./i18n"

/**
 * Global user preferences: language + currency.
 *
 * Both choices are persisted in localStorage under:
 * - foresight.language (handled by i18next's LanguageDetector)
 * - foresight.currency (handled here)
 *
 * The exchange rate is mocked in V2 (1 USD = 0.92 EUR). A real rate API is
 * a backend concern — Cursor will wire openexchangerates.org later.
 */

const CURRENCY_STORAGE_KEY = "foresight.currency"

export type UserPreferencesValue = {
  language: SupportedLanguage
  currency: Currency
  exchangeRate: number
  setLanguage: (lang: SupportedLanguage) => void
  setCurrency: (currency: Currency) => void
  formatMoney: (amountUSD: number, opts?: { signed?: boolean; decimals?: number }) => string
}

const UserPreferencesContext = createContext<UserPreferencesValue | null>(null)

function readStoredCurrency(): Currency {
  if (typeof window === "undefined") return "USD"
  try {
    const raw = window.localStorage.getItem(CURRENCY_STORAGE_KEY)
    if (isCurrency(raw)) return raw
  } catch {
    // ignore
  }
  return "USD"
}

export function UserPreferencesProvider({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation()
  const [currency, setCurrencyState] = useState<Currency>(() => readStoredCurrency())

  const language = useMemo<SupportedLanguage>(() => {
    const current = i18n.resolvedLanguage ?? i18n.language
    return isSupportedLanguage(current) ? current : "fr"
  }, [i18n.resolvedLanguage, i18n.language])

  const setLanguage = useCallback(
    (lang: SupportedLanguage) => {
      void i18n.changeLanguage(lang)
      try {
        window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lang)
      } catch {
        // ignore
      }
    },
    [i18n],
  )

  const setCurrency = useCallback((next: Currency) => {
    setCurrencyState(next)
    try {
      window.localStorage.setItem(CURRENCY_STORAGE_KEY, next)
    } catch {
      // ignore
    }
  }, [])

  // Keep <html lang="…"> synced for accessibility.
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = language
    }
  }, [language])

  const formatMoney = useCallback(
    (amountUSD: number, opts?: { signed?: boolean; decimals?: number }) =>
      formatCurrencyRaw(amountUSD, currency, {
        ...opts,
        rate: MOCK_EXCHANGE_RATE_USD_TO_EUR,
        locale: language === "fr" ? "fr-FR" : "en-US",
      }),
    [currency, language],
  )

  const value = useMemo<UserPreferencesValue>(
    () => ({
      language,
      currency,
      exchangeRate: MOCK_EXCHANGE_RATE_USD_TO_EUR,
      setLanguage,
      setCurrency,
      formatMoney,
    }),
    [language, currency, setLanguage, setCurrency, formatMoney],
  )

  return (
    <UserPreferencesContext.Provider value={value}>{children}</UserPreferencesContext.Provider>
  )
}

export function useUserPreferences(): UserPreferencesValue {
  const ctx = useContext(UserPreferencesContext)
  if (!ctx) {
    throw new Error("useUserPreferences must be used inside <UserPreferencesProvider>")
  }
  return ctx
}
