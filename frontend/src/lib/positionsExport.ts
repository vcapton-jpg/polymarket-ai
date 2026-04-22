import type { Position } from "@/types/signal"

/**
 * Produce a CSV string of the given positions.
 * Columns picked to be useful in Excel / Sheets analysis — signal question,
 * direction, source, prices, stake, estimated gain, status, entry date,
 * resolution outcome.
 */
export function positionsToCSV(positions: Position[]): string {
  const headers = [
    "id",
    "signal_id",
    "question",
    "direction",
    "source",
    "entry_price",
    "current_price",
    "stake_usd",
    "estimated_gain_usd",
    "status",
    "entry_date_iso",
    "resolved",
    "correct_prediction",
  ]

  const lines = positions.map((p) =>
    [
      p.id,
      p.signalId,
      escape(p.signal.question),
      p.direction,
      p.source,
      p.entryPrice.toFixed(4),
      p.currentPrice.toFixed(4),
      p.stake.toFixed(2),
      p.estimatedGain.toFixed(2),
      p.status,
      p.entryDate,
      p.resolved ? "true" : "false",
      p.correctPrediction === null
        ? ""
        : p.correctPrediction
          ? "true"
          : "false",
    ].join(","),
  )

  return [headers.join(","), ...lines].join("\n")
}

/** RFC 4180 CSV escaping. */
function escape(v: string): string {
  if (/[",\n]/.test(v)) {
    return `"${v.replace(/"/g, '""')}"`
  }
  return v
}

/**
 * Trigger a CSV download in the browser.
 * Returns true on success, false in SSR / non-browser environments.
 */
export function downloadPositionsCSV(
  positions: Position[],
  filename = `foresight-portfolio-${new Date().toISOString().slice(0, 10)}.csv`,
): boolean {
  if (typeof document === "undefined") return false
  const csv = positionsToCSV(positions)
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  return true
}
