import { useTranslation } from "react-i18next"
import { useUserPreferences } from "@/lib/userPreferences"
import type { Currency } from "@/lib/formatCurrency"
import type { SupportedLanguage } from "@/lib/i18n"
import { cn } from "@/lib/utils"

type PreferenceTogglesProps = {
  className?: string
  compact?: boolean
}

/**
 * Dual toggle shown in the topbar: language (FR/EN) + currency (USD/EUR).
 *
 * Both are session-wide preferences persisted in localStorage. The component
 * stays purely visual — state lives in UserPreferencesContext + i18next.
 */
export function PreferenceToggles({ className, compact = false }: PreferenceTogglesProps) {
  const { t } = useTranslation()
  const { language, currency, setLanguage, setCurrency } = useUserPreferences()

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <SegmentedToggle
        ariaLabel={t("language.label") || "Language"}
        compact={compact}
        options={[
          { value: "fr", label: t("language.fr") },
          { value: "en", label: t("language.en") },
        ]}
        active={language}
        onChange={(v) => setLanguage(v as SupportedLanguage)}
      />
      <SegmentedToggle
        ariaLabel={t("currency.label") || "Currency"}
        compact={compact}
        options={[
          { value: "USD", label: t("currency.usd") },
          { value: "EUR", label: t("currency.eur") },
        ]}
        active={currency}
        onChange={(v) => setCurrency(v as Currency)}
      />
    </div>
  )
}

type Option = { value: string; label: string }

function SegmentedToggle({
  options,
  active,
  onChange,
  ariaLabel,
  compact,
}: {
  options: Option[]
  active: string
  onChange: (v: string) => void
  ariaLabel: string
  compact?: boolean
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex rounded-md border border-line/80 bg-obsidian-800/60 p-0.5",
        compact ? "text-label-xs" : "text-label-sm",
      )}
    >
      {options.map((opt) => {
        const isActive = opt.value === active
        return (
          <button
            key={opt.value}
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(opt.value)}
            className={cn(
              "num inline-flex items-center font-mono font-semibold tracking-[0.1em] rounded-sm transition-premium cursor-pointer",
              compact ? "h-6 px-2" : "h-7 px-2.5",
              isActive
                ? "bg-obsidian-700 text-ink shadow-inset-line"
                : "text-ink-dim hover:text-ink",
            )}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
