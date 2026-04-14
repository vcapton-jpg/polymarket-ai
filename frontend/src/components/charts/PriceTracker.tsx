import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts"
import { Card } from "../ui/Card"
import type { SignalOutcome } from "../../lib/types"

interface Props {
  outcome: SignalOutcome | null
  priceAtSignal: number | null
}

const tooltipStyle = {
  background: "#1a1f2e",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 8,
  fontSize: 12,
  color: "#F1F5F9",
}

export function PriceTracker({ outcome, priceAtSignal }: Props) {
  if (!outcome) return null

  const data = [
    { label: "T0", price: priceAtSignal },
    { label: "+5m", price: outcome.price_t5min },
    { label: "+15m", price: outcome.price_t15min },
    { label: "+1h", price: outcome.price_t1h },
    { label: "+24h", price: outcome.price_t24h },
  ].filter((d) => d.price != null)

  if (data.length < 2) return null

  return (
    <Card className="p-5">
      <h4 className="text-xs font-semibold text-txt-muted uppercase tracking-wider mb-1">
        YES implied probability over time
      </h4>
      <p className="text-[11px] text-txt-muted mb-4">
        Values are market-implied chance of YES (0-100%), not account dollars.
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="label" tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={["dataMin - 0.05", "dataMax + 0.05"]}
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
            tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${(Number(v) * 100).toFixed(1)}% YES`, "Implied"]} />
          {priceAtSignal != null && (
            <ReferenceLine y={priceAtSignal} stroke="#F59E0B" strokeDasharray="4 4" strokeOpacity={0.45} />
          )}
          <Area type="monotone" dataKey="price" stroke="#F59E0B" strokeWidth={2} fill="url(#priceGrad)" dot={{ fill: "#F59E0B", r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  )
}
