import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useId,
  useMemo,
  useRef,
} from "react"
import { cn } from "@/lib/utils"

/* ───────────────────────────────────────────────────────────────────
 * FilterPillGroup — a roving-tabindex radiogroup primitive.
 *
 * Matches the visual language of the inline pill clusters used across
 * the app (Signals page categories/score/direction). Unlike a native
 * <select> or <input type="radio">, these are stylised buttons — so we
 * re-implement the ARIA radiogroup pattern:
 *
 *   - container: role="radiogroup"
 *   - options:   role="radio" + aria-checked
 *   - selected option: tabIndex=0, others: tabIndex=-1
 *   - ArrowLeft/Right (horizontal) or ArrowUp/Down (vertical) cycle
 *     selection AND move focus. Home/End jump to first/last.
 *
 * Keyboard navigation selects on arrow-press (WAI-ARIA APG pattern).
 * ──────────────────────────────────────────────────────────────── */

type Orientation = "horizontal" | "vertical"

type FilterPillGroupContextValue = {
  groupId: string
  value: string
  orientation: Orientation
  register: (id: string, el: HTMLButtonElement | null) => void
  onSelect: (id: string) => void
  onKeyNavigate: (id: string, e: React.KeyboardEvent<HTMLButtonElement>) => void
}

const FilterPillGroupContext = createContext<FilterPillGroupContextValue | null>(null)

function useFilterPillGroupContext(componentName: string) {
  const ctx = useContext(FilterPillGroupContext)
  if (!ctx) {
    throw new Error(`${componentName} must be rendered inside <FilterPillGroup>`)
  }
  return ctx
}

type FilterPillGroupProps = {
  value: string
  onValueChange: (next: string) => void
  orientation?: Orientation
  /** Accessible label. Either this or aria-labelledby should be provided. */
  "aria-label"?: string
  "aria-labelledby"?: string
  className?: string
  children: React.ReactNode
}

export function FilterPillGroup({
  value,
  onValueChange,
  orientation = "horizontal",
  className,
  children,
  ...rest
}: FilterPillGroupProps) {
  const groupId = useId()
  const orderedIdsRef = useRef<string[]>([])
  const refsRef = useRef<Map<string, HTMLButtonElement | null>>(new Map())

  const register = useCallback((id: string, el: HTMLButtonElement | null) => {
    refsRef.current.set(id, el)
    const ids = orderedIdsRef.current
    if (el) {
      if (!ids.includes(id)) ids.push(id)
    } else {
      const i = ids.indexOf(id)
      if (i >= 0) ids.splice(i, 1)
      refsRef.current.delete(id)
    }
  }, [])

  const onSelect = useCallback(
    (id: string) => {
      onValueChange(id)
    },
    [onValueChange],
  )

  const onKeyNavigate = useCallback(
    (id: string, e: React.KeyboardEvent<HTMLButtonElement>) => {
      const ids = orderedIdsRef.current
      if (ids.length === 0) return
      const currentIndex = ids.indexOf(id)
      if (currentIndex === -1) return

      const nextKeys = orientation === "horizontal" ? ["ArrowRight"] : ["ArrowDown"]
      const prevKeys = orientation === "horizontal" ? ["ArrowLeft"] : ["ArrowUp"]

      let targetIndex: number | null = null
      if (nextKeys.includes(e.key)) targetIndex = (currentIndex + 1) % ids.length
      else if (prevKeys.includes(e.key))
        targetIndex = (currentIndex - 1 + ids.length) % ids.length
      else if (e.key === "Home") targetIndex = 0
      else if (e.key === "End") targetIndex = ids.length - 1

      if (targetIndex === null) return

      e.preventDefault()
      const nextId = ids[targetIndex]
      onValueChange(nextId)
      const el = refsRef.current.get(nextId)
      el?.focus()
    },
    [onValueChange, orientation],
  )

  const ctx = useMemo<FilterPillGroupContextValue>(
    () => ({ groupId, value, orientation, register, onSelect, onKeyNavigate }),
    [groupId, value, orientation, register, onSelect, onKeyNavigate],
  )

  return (
    <FilterPillGroupContext.Provider value={ctx}>
      <div
        role="radiogroup"
        aria-orientation={orientation}
        aria-label={rest["aria-label"]}
        aria-labelledby={rest["aria-labelledby"]}
        className={className}
      >
        {children}
      </div>
    </FilterPillGroupContext.Provider>
  )
}

/* ───────────────────────────────────────────────────────────────────
 * FilterPill — button option rendered inside a FilterPillGroup.
 * Falls back to a plain button when used outside a group (legacy callers).
 * ──────────────────────────────────────────────────────────────── */

type FilterPillProps = {
  value?: string
  active?: boolean
  onClick?: () => void
  size?: "sm" | "md"
  tone?: "yes" | "no"
  className?: string
  children: React.ReactNode
}

export const FilterPill = forwardRef<HTMLButtonElement, FilterPillProps>(
  function FilterPill({ value, active, onClick, size = "md", tone, className, children }, forwardedRef) {
    const group = useContext(FilterPillGroupContext)
    const localRef = useRef<HTMLButtonElement | null>(null)

    const setRef = useCallback(
      (el: HTMLButtonElement | null) => {
        localRef.current = el
        if (typeof forwardedRef === "function") forwardedRef(el)
        else if (forwardedRef) forwardedRef.current = el
        if (group && value != null) group.register(value, el)
      },
      [forwardedRef, group, value],
    )

    const isActive = group && value != null ? group.value === value : !!active

    const toneActive =
      tone === "yes"
        ? "border-signal-yes/50 bg-signal-yes/10 text-signal-yes"
        : tone === "no"
          ? "border-signal-no/50 bg-signal-no/10 text-signal-no"
          : "border-line-strong bg-obsidian-700 text-ink shadow-inset-line"

    const handleClick = () => {
      if (group && value != null) group.onSelect(value)
      onClick?.()
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (group && value != null) group.onKeyNavigate(value, e)
    }

    const inGroup = group && value != null
    const tabIndex = inGroup ? (isActive ? 0 : -1) : undefined

    return (
      <button
        ref={setRef}
        type="button"
        role={inGroup ? "radio" : undefined}
        aria-checked={inGroup ? isActive : undefined}
        tabIndex={tabIndex}
        onClick={handleClick}
        onKeyDown={inGroup ? handleKeyDown : undefined}
        className={cn(
          "inline-flex items-center gap-1 rounded-full border transition-premium whitespace-nowrap cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40",
          size === "sm" ? "px-2.5 py-1 text-label-sm" : "px-3 py-1.5 text-body-sm",
          isActive
            ? toneActive
            : "border-line bg-obsidian-850/60 text-ink-muted hover:text-ink hover:border-line-strong",
          className,
        )}
      >
        {children}
      </button>
    )
  },
)
