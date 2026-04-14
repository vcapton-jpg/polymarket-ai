import { getBucket, inferBucketFromQuestion } from "../../lib/constants"

interface Props {
  bucket?: string | null
  question?: string | null
  size?: "sm" | "md"
}

export function CategoryBadge({ bucket, question, size = "sm" }: Props) {
  const resolvedBucket = bucket || (question ? inferBucketFromQuestion(question) : "other")
  const b = getBucket(resolvedBucket)

  const pad = size === "sm" ? "px-2 py-0.5" : "px-3 py-1"
  const text = size === "sm" ? "text-[10px]" : "text-xs"

  return (
    <span
      className={`inline-flex items-center gap-1 ${pad} rounded-full ${text} font-semibold uppercase tracking-wider whitespace-nowrap`}
      style={{ color: b.color, background: `${b.color}18` }}
    >
      <span>{b.emoji}</span>
      <span>{b.label}</span>
    </span>
  )
}
