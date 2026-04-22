import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import LanguageDetector from "i18next-browser-languagedetector"

import fr from "@/locales/fr/common.json"
import en from "@/locales/en/common.json"

/**
 * i18n config for Foresight V2.
 *
 * - Default: FR (early testers francophones)
 * - Target: EN (once ready for US rollout)
 * - User choice persisted via localStorage key `foresight.language`
 * - Fallback chain always lands on FR so no keys show raw.
 * - EN file is intentionally mostly empty right now — any missing key falls
 *   back to FR automatically. Backend/Cursor will fill en/common.json later.
 */

export const LANGUAGE_STORAGE_KEY = "foresight.language"

export const SUPPORTED_LANGUAGES = ["fr", "en"] as const
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

export function isSupportedLanguage(v: unknown): v is SupportedLanguage {
  return typeof v === "string" && (SUPPORTED_LANGUAGES as readonly string[]).includes(v)
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { common: fr },
      en: { common: en },
    },
    ns: ["common"],
    defaultNS: "common",
    fallbackLng: "fr",
    supportedLngs: SUPPORTED_LANGUAGES,
    returnEmptyString: false, // empty strings → fallback to FR
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
      caches: ["localStorage"],
    },
  })

export default i18n
