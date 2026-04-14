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
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-14 h-14 rounded-full bg-surface-raised flex items-center justify-center mb-4">
        {icon ?? <Inbox size={24} className="text-txt-muted" />}
      </div>
      <h3 className="text-sm font-semibold text-txt-secondary mb-1">{title}</h3>
      <p className="text-xs text-txt-muted max-w-xs leading-relaxed">{message}</p>
    </div>
  )
}
