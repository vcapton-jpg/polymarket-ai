import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"
import { Card } from "../ui/Card"

interface DataPoint {
  day: string
  accuracy: number
}

interface Props {
  data: DataPoint[]
  title?: string
}

export function AccuracyChart({ data, title = "Accuracy (7d)" }: Props) {
  return (
    <Card className="p-5">
      <h4 className="text-sm font-semibold text-txt-primary mb-4">{title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="day" tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} width={32} />
          <Tooltip contentStyle={{ background: "#1a1f2e", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }} />
          <Line type="monotone" dataKey="accuracy" stroke="#F59E0B" strokeWidth={2} dot={{ fill: "#F59E0B", r: 3 }} activeDot={{ r: 5, stroke: "#F59E0B", strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}
