import { useId } from "react"
import { motion } from "framer-motion"
import { scoreColor } from "../../lib/utils"

interface Props {
  score: number
  size?: number
  strokeWidth?: number
}

export function ScoreRing({ score, size = 72, strokeWidth = 5 }: Props) {
  const reactId = useId()
  const filterId = `score-ring-glow-${reactId.replace(/:/g, "")}`
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference
  const color = scoreColor(score)

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.25" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.04)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeLinecap="round"
          filter={`url(#${filterId})`}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </svg>
      <div
        className="absolute inset-0 flex items-center justify-center font-mono font-bold font-tabular"
        style={{ fontSize: size * 0.28, color }}
      >
        {Math.round(score)}
      </div>
    </div>
  )
}
