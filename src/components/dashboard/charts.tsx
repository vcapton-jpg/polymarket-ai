import { motion } from 'framer-motion'
import { EASE } from '../../lib/motion'

/** Histogramme du volume entrant sur la journée — les barres montent à l'arrivée. */
export function VolumeChart({ data }: { data: { h: string; v: number }[] }) {
  const max = Math.max(...data.map((d) => d.v))
  return (
    <div className="flex h-52 items-stretch gap-2">
      {data.map((d, i) => (
        <div key={d.h} className="group flex flex-1 flex-col items-center gap-2">
          <div className="relative flex w-full flex-1 items-end justify-center">
            <span className="absolute -top-1 text-[10px] font-medium tabular-nums text-mist opacity-0 transition-opacity duration-200 group-hover:opacity-100">
              {d.v}
            </span>
            <motion.div
              initial={{ height: 0 }}
              whileInView={{ height: `${(d.v / max) * 100}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: i * 0.04, ease: EASE }}
              className="w-full rounded-md bg-gradient-to-t from-accent/25 to-accent/80 transition-colors group-hover:to-accent-300"
              style={{ minHeight: 4 }}
            />
          </div>
          <span className="text-[10px] text-faint">{d.h}</span>
        </div>
      ))}
    </div>
  )
}

/** Donut de répartition par canal (omnicanal), avec légende. */
export function ChannelDonut({ data }: { data: { label: string; value: number; color: string }[] }) {
  const total = data.reduce((s, c) => s + c.value, 0)
  let acc = 0
  const stops = data
    .map((c) => {
      const start = (acc / total) * 360
      acc += c.value
      const end = (acc / total) * 360
      return `${c.color} ${start}deg ${end}deg`
    })
    .join(', ')

  return (
    <div className="flex items-center gap-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.85, rotate: -25 }}
        whileInView={{ opacity: 1, scale: 1, rotate: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, ease: EASE }}
        className="relative h-36 w-36 shrink-0"
      >
        <div
          className="h-full w-full rounded-full"
          style={{
            background: `conic-gradient(${stops})`,
            WebkitMaskImage: 'radial-gradient(circle, transparent 54%, #000 55%)',
            maskImage: 'radial-gradient(circle, transparent 54%, #000 55%)',
          }}
        />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-lg font-semibold text-cloud">{total}%</span>
          <span className="text-[10px] text-faint">omnicanal</span>
        </div>
      </motion.div>

      <ul className="space-y-2">
        {data.map((c) => (
          <li key={c.label} className="flex items-center gap-2.5 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: c.color }} />
            <span className="text-mist">{c.label}</span>
            <span className="ml-auto font-mono text-xs font-medium text-cloud">{c.value}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Barres horizontales de répartition par catégorie. */
export function CategoryBars({ data }: { data: { label: string; value: number; color: string }[] }) {
  const max = Math.max(...data.map((d) => d.value))
  return (
    <div className="space-y-3.5">
      {data.map((d, i) => (
        <div key={d.label} className="flex items-center gap-3">
          <span className="w-36 shrink-0 truncate text-sm text-mist">{d.label}</span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/[0.04]">
            <motion.div
              initial={{ width: 0 }}
              whileInView={{ width: `${(d.value / max) * 100}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.9, delay: i * 0.07, ease: EASE }}
              className="h-full rounded-full"
              style={{ backgroundColor: d.color }}
            />
          </div>
          <span className="w-9 shrink-0 text-right font-mono text-xs font-medium text-cloud">{d.value}%</span>
        </div>
      ))}
    </div>
  )
}
