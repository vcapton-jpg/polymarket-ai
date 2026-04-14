import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts"
import { Card } from "../ui/Card"
import { BUCKETS } from "../../lib/constants"

interface DataPoint {
  name: string
  value: number
}

interface Props {
  data: DataPoint[]
  title?: string
}

export function BucketDonut({ data, title = "Signals by Bucket" }: Props) {
  const colorMap: Record<string, string> = {}
  BUCKETS.forEach((b) => (colorMap[b.value] = b.color))

  return (
    <Card className="p-5">
      <h4 className="text-sm font-semibold text-txt-primary mb-4">{title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value">
            {data.map((entry) => (
              <Cell key={entry.name} fill={colorMap[entry.name] || "#94A3B8"} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: "#1a1f2e", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: colorMap[d.name] || "#94A3B8" }} />
            <span className="text-xs text-txt-muted capitalize">{d.name}</span>
            <span className="text-xs font-mono font-semibold text-txt-secondary">{d.value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
