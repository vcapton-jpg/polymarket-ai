import { Inbox } from "lucide-react"

interface Props {
  title?: string
  message?: string
  icon?: React.ReactNode
}

export function EmptyState({
  title = "Nothing here yet",
  message = "Data will appear as the pipeline processes signals.",
  icon,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in-blur">
      <div className="w-16 h-16 rounded-full glass-card border border-edge-subtle shadow-inner-glow flex items-center justify-center mb-4">
        {icon ?? <Inbox size={28} className="text-txt-muted" strokeWidth={1.5} />}
      </div>
      <h3 className="text-sm font-semibold font-display text-txt-secondary mb-1">{title}</h3>
      <p className="text-xs text-txt-muted max-w-xs leading-relaxed">{message}</p>
    </div>
  )
}
