import { motion } from "framer-motion"
import { useState } from "react"
import { scoreColor, strengthColor, tradeQualityColor } from "../../lib/utils"
import { getScoreTier } from "../../lib/constants"

interface Props {
  score: number
  signalStrength?: number | null
  tradeQuality?: number | null
  size?: "sm" | "md"
  showTooltip?: boolean
}

export function ScoreBar({
  score,
  signalStrength,
  tradeQuality,
  size = "md",
  showTooltip = true,
}: Props) {
  const [hover, setHover] = useState(false)
  const color = scoreColor(score)
  const tier = getScoreTier(score)
  const pct = Math.min(score, 100)
  const isSm = size === "sm"

  const hasSubScores = signalStrength != null && tradeQuality != null

  return (
    <div
      className="relative"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={`font-mono font-extrabold ${isSm ? "text-xl" : "text-3xl"} leading-none font-tabular`}
          style={{ color }}
        >
          {Math.round(score)}
        </span>
        <div className="flex-1 min-w-0">
          <div
            className={`${isSm ? "h-2" : "h-2.5"} rounded-full overflow-hidden`}
            style={{ background: "rgba(255,255,255,0.04)" }}
          >
            <motion.div
              className={`${isSm ? "h-2" : "h-2.5"} rounded-full`}
              style={{
                background: color,
                boxShadow: `0 0 12px ${color}55, 0 0 4px ${color}33`,
              }}
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
          {!isSm && hasSubScores && (
            <div className="flex gap-2 mt-1.5">
              <SubBar label="Signal" value={signalStrength!} color={strengthColor(signalStrength!)} />
              <SubBar label="Market" value={tradeQuality!} color={tradeQualityColor(tradeQuality!)} />
            </div>
          )}
          <div className="flex justify-between mt-0.5">
            <span className="text-[9px] font-medium uppercase tracking-wider" style={{ color }}>
              {tier.label}
            </span>
            <span className="text-[9px] text-txt-muted">{pct}/100</span>
          </div>
        </div>
      </div>

      {showTooltip && hover && (
        <div
          className="absolute z-50 bottom-full left-0 mb-2 w-64 px-3 py-2.5 glass-card rounded-xl text-[11px] text-txt-secondary leading-relaxed pointer-events-none"
        >
          <p className="font-semibold text-txt-primary mb-1">Score: {Math.round(score)}</p>
          {hasSubScores && (
            <>
              <div className="flex justify-between mb-0.5">
                <span>Signal Strength</span>
                <span className="font-mono font-semibold" style={{ color: strengthColor(signalStrength!) }}>
                  {Math.round(signalStrength!)}
                </span>
              </div>
              <div className="flex justify-between mb-1">
                <span>Trade Quality</span>
                <span className="font-mono font-semibold" style={{ color: tradeQualityColor(tradeQuality!) }}>
                  {Math.round(tradeQuality!)}
                </span>
              </div>
              <p className="text-txt-muted text-[10px]">Score = 75% signal + 25% trade quality</p>
            </>
          )}
          {!hasSubScores && (
            <p className="text-txt-muted">55+ actionable, 75+ strong, 90+ exceptional</p>
          )}
        </div>
      )}
    </div>
  )
}

function SubBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[9px] text-txt-muted">{label}</span>
        <span className="text-[9px] font-mono font-semibold" style={{ color }}>{Math.round(value)}</span>
      </div>
      <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.04)" }}>
        <motion.div
          className="h-1 rounded-full"
          style={{
            background: color,
            boxShadow: `0 0 8px ${color}44`,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(value, 100)}%` }}
          transition={{ duration: 0.5, ease: "easeOut", delay: 0.1 }}
        />
      </div>
    </div>
  )
}
