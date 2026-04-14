import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { ArrowRight, Clock, TrendingUp, Zap } from "lucide-react"
import { ScoreBar } from "../ui/ScoreBar"
import { CategoryBadge } from "../ui/CategoryBadge"
import { DirectionBadge } from "../ui/DirectionBadge"
import { timeAgo, formatYesImpliedPct, cn, computeEdge } from "../../lib/utils"
import { inferBucketFromQuestion } from "../../lib/constants"
import type { Signal } from "../../lib/types"

interface Props {
  signal: Signal
  showLive?: boolean
  isNew?: boolean
}

export function SignalCard({ signal, showLive, isNew }: Props) {
  const nav = useNavigate()
  const displayText = signal.event_title || `Signal #${signal.id}`
  const marketLabel = signal.market_question ?? null
  const bucket = inferBucketFromQuestion(signal.market_question)
  const yesPct = formatYesImpliedPct(signal.market_price_at_signal)
  const edge = computeEdge(signal.direction, signal.signal_strength, signal.market_price_at_signal)

  return (
    <motion.article
      className={cn(
        "bg-surface-card rounded-lg shadow-card cursor-pointer transition-shadow duration-200 hover:shadow-card-hover overflow-hidden",
        isNew && "animate-flash-border",
      )}
      onClick={() => nav(`/opportunity/${signal.id}`)}
      layout
      initial={isNew ? { opacity: 0, y: -12 } : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Top strip: category + time + direction */}
      <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <CategoryBadge bucket={bucket} question={signal.market_question} />
          <span className="text-[11px] text-txt-muted whitespace-nowrap flex items-center gap-1">
            <Clock size={10} />
            {timeAgo(signal.created_at)} ago
          </span>
          {showLive && (
            <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse-live" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {edge.label !== "N/A" && (
            <span
              className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
              style={{
                color: edge.color,
                background: `${edge.color}15`,
                border: `1px solid ${edge.color}30`,
              }}
            >
              <TrendingUp size={10} />
              Edge: {edge.label}
            </span>
          )}
          <DirectionBadge direction={signal.direction} animate />
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3">
        <h3 className="text-[15px] font-semibold text-txt-primary leading-snug line-clamp-2 mb-1">
          {displayText}
        </h3>
        {marketLabel && (
          <p className="text-xs text-txt-muted mb-0.5 truncate">{marketLabel}</p>
        )}
        {signal.score_explanation && (
          <p className="text-[11px] text-txt-muted/70 leading-relaxed line-clamp-2 mt-1">
            {signal.score_explanation}
          </p>
        )}
      </div>

      {/* Score + Market section */}
      <div className="px-4 pb-3.5 flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <ScoreBar
            score={signal.signal_score}
            signalStrength={signal.signal_strength}
            tradeQuality={signal.trade_quality}
            size="sm"
          />
        </div>

        <div className="shrink-0 text-right pl-3"
          style={{ borderLeft: "1px solid rgba(255,255,255,0.06)" }}
        >
          <span className="text-[10px] text-txt-muted block mb-0.5">Market says</span>
          <span className="text-base font-mono font-bold text-txt-primary font-tabular leading-none">
            {yesPct}
          </span>
          <span className="text-[10px] text-txt-muted ml-1">YES</span>
        </div>
      </div>

      {/* Footer: confidence + urgency + trade */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-surface-0/50"
        style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
      >
        <div className="flex items-center gap-4 text-[11px]">
          {signal.confidence_label && (
            <span className="flex items-center gap-1.5">
              <span className="text-txt-muted">Confidence:</span>
              <span className="font-semibold text-txt-secondary">
                {signal.confidence_label.toUpperCase()}
              </span>
            </span>
          )}
          {signal.urgency_label && (
            <span className="flex items-center gap-1.5">
              <span className="text-txt-muted">Urgency:</span>
              <span className="font-semibold text-warning">
                {signal.urgency_label.toUpperCase()}
              </span>
            </span>
          )}
          {signal.window_estimate && (
            <span className="flex items-center gap-1.5">
              <span className="text-txt-muted">Window:</span>
              <span className="font-semibold text-txt-secondary">
                {signal.window_estimate}
              </span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              nav(`/opportunity/${signal.id}?trade=1`)
            }}
            className="flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-1 rounded bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
          >
            <Zap size={10} />
            Trade
          </button>
          <ArrowRight size={14} className="text-txt-muted" />
        </div>
      </div>
    </motion.article>
  )
}
