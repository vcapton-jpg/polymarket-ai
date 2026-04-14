import type { ReactNode } from "react"

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: ReactNode
  mono?: boolean
}

export function MetricCard({ label, value, sub, icon, mono }: Props) {
  return (
    <div className="bg-surface-card rounded-lg shadow-card p-4 md:p-5 transition-shadow duration-200 hover:shadow-card-hover">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-txt-muted uppercase tracking-widest">
          {label}
        </span>
        {icon && (
          <div className="w-8 h-8 flex items-center justify-center rounded-md bg-accent-muted text-accent">
            {icon}
          </div>
        )}
      </div>
      <div className={`text-2xl font-bold text-txt-primary leading-tight mb-1 tracking-tight ${mono ? "font-mono font-tabular" : ""}`}>
        {value}
      </div>
      {sub && (
        <span className="text-xs text-txt-muted leading-relaxed">{sub}</span>
      )}
    </div>
  )
}
