import { useState, type ReactNode } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  sortFn?: (a: T, b: T) => number
  className?: string
}

interface Props<T> {
  data: T[]
  columns: Column<T>[]
  keyFn: (row: T) => string | number
  onRowClick?: (row: T) => void
  emptyMessage?: string
}

export function DataTable<T>({ data, columns, keyFn, onRowClick, emptyMessage }: Props<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)

  const sortedData = (() => {
    if (!sortCol) return data
    const col = columns.find((c) => c.key === sortCol)
    if (!col?.sortFn) return data
    const sorted = [...data].sort(col.sortFn)
    return sortAsc ? sorted : sorted.reverse()
  })()

  function toggleSort(key: string) {
    if (sortCol === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortCol(key)
      setSortAsc(true)
    }
  }

  if (data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-txt-muted">
        {emptyMessage ?? "No data available."}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg shadow-card">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-surface-card">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-[11px] font-semibold text-txt-muted uppercase tracking-wider whitespace-nowrap ${
                  col.sortFn ? "cursor-pointer select-none hover:text-txt-secondary" : ""
                } ${col.className ?? ""}`}
                style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
                onClick={col.sortFn ? () => toggleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1.5">
                  {col.header}
                  {sortCol === col.key &&
                    (sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row) => (
            <tr
              key={keyFn(row)}
              className={`bg-surface-card/60 hover:bg-surface-raised transition-colors ${
                onRowClick ? "cursor-pointer" : ""
              }`}
              style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-3 ${col.className ?? ""}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
