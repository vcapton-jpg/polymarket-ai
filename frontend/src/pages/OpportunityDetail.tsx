import { useParams, Link } from "react-router-dom"
import { motion } from "framer-motion"
import { ArrowLeft, ExternalLink, TrendingUp, Lightbulb, AlertTriangle, Brain } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Badge } from "../components/ui/Badge"
import { ScoreBar } from "../components/ui/ScoreBar"
import { CategoryBadge } from "../components/ui/CategoryBadge"
import { DirectionBadge } from "../components/ui/DirectionBadge"
import { Button } from "../components/ui/Button"
import { PriceTracker } from "../components/charts/PriceTracker"
import { Skeleton } from "../components/ui/Skeleton"
import { useSignal } from "../hooks/useSignals"
import { CONFIDENCE_CONFIG, URGENCY_CONFIG, TRADABILITY_CONFIG, inferBucketFromQuestion } from "../lib/constants"
import {
  formatDate,
  formatYesImpliedPct,
  formatSpreadPp,
  formatUsdCompact,
  computeEdge,
  strengthColor,
  tradeQualityColor,
} from "../lib/utils"

const detailContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.04 },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
  },
}

export default function OpportunityDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: signal, isLoading } = useSignal(Number(id))

  if (isLoading) {
    return (
      <div>
        <Skeleton height={32} width="40%" />
        <div className="mt-6"><Skeleton height={300} /></div>
      </div>
    )
  }

  if (!signal) {
    return (
      <div className="py-16 text-center">
        <p className="text-txt-muted">Signal not found.</p>
        <Link to="/opportunities" className="mt-4 inline-block text-accent hover:text-accent-bright">
          &larr; Back to signals
        </Link>
      </div>
    )
  }

  const conf = signal.confidence_label
    ? CONFIDENCE_CONFIG[signal.confidence_label as keyof typeof CONFIDENCE_CONFIG]
    : null
  const urg = signal.urgency_label
    ? URGENCY_CONFIG[signal.urgency_label as keyof typeof URGENCY_CONFIG]
    : null
  const trad = signal.tradability_label
    ? TRADABILITY_CONFIG[signal.tradability_label as keyof typeof TRADABILITY_CONFIG]
    : null

  const edge = computeEdge(signal.direction, signal.signal_strength, signal.market_price_at_signal)

  return (
    <div className="max-w-[900px]">
      <Link to="/opportunities" className="inline-flex items-center gap-1.5 text-sm text-txt-muted hover:text-txt-secondary mb-5 no-underline transition-colors">
        <ArrowLeft size={16} /> Back to Signals
      </Link>

      {/* Title area */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <CategoryBadge bucket={inferBucketFromQuestion(signal.market_question)} question={signal.market_question} size="md" />
          <span className="text-xs text-txt-muted">{formatDate(signal.created_at)}</span>
        </div>
        <h1 className="text-xl md:text-2xl font-bold font-display tracking-display text-txt-primary leading-snug">
          {signal.market?.question || `Signal #${signal.id}`}
        </h1>
      </div>

      <motion.div
        variants={detailContainer}
        initial="hidden"
        animate="visible"
        className="space-y-5"
      >
        {/* News story */}
        {signal.event && (
          <motion.div variants={fadeUp}>
            <Card className="border-l-2 border-l-accent shadow-card">
              <h4 className="text-xs font-semibold font-display tracking-display text-txt-muted uppercase mb-3">
                The Story
              </h4>
              <p className="text-txt-primary font-semibold text-base mb-2 leading-snug">
                {signal.event.event_title}
              </p>
              {signal.event.event_summary && (
                <p className="text-sm text-txt-muted leading-relaxed">
                  {signal.event.event_summary}
                </p>
              )}
            </Card>
          </motion.div>
        )}

        {/* Score + Direction + CTA */}
        <motion.div variants={fadeUp}>
          <Card className="shadow-card">
            <div className="flex flex-col md:flex-row items-start gap-6">
              <div className="w-full md:w-56 shrink-0">
                <p className="text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-2">
                  Conviction Score
                </p>
                <ScoreBar
                  score={signal.signal_score}
                  signalStrength={signal.signal_strength}
                  tradeQuality={signal.trade_quality}
                  size="md"
                />
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-2">
                  Position
                </p>
                <div className="flex gap-2 flex-wrap mb-4">
                  <DirectionBadge direction={signal.direction} />
                  {conf && <Badge label={conf.label} color={conf.color} size="md" />}
                  {urg && <Badge label={`Timing: ${urg.label}`} color={urg.color} size="md" />}
                  {trad && <Badge label={`Liquidity: ${trad.label}`} color={trad.color} size="md" />}
                  {edge.label !== "N/A" && (
                    <span
                      className="inline-flex items-center gap-1 text-xs font-bold uppercase px-2 py-1 rounded-lg border border-edge-subtle shadow-glass"
                      style={{
                        color: edge.color,
                        background: `${edge.color}15`,
                        borderColor: `${edge.color}30`,
                      }}
                    >
                      <TrendingUp size={12} /> Edge: {edge.label}
                    </span>
                  )}
                </div>
                {signal.market && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      size="md"
                      icon={<TrendingUp size={15} />}
                      onClick={async () => {
                        const amount = prompt("How many shares?", "10")
                        if (!amount) return
                        try {
                          const res = await fetch("/api/trading/trade", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                              market_id: signal.market_id,
                              direction: signal.direction,
                              amount: Number(amount),
                              signal_id: signal.id,
                            }),
                          })
                          const data = await res.json()
                          if (data.success) {
                            alert(`Order placed! ID: ${data.polymarket_order_id || data.order_id}`)
                          } else {
                            alert(`Order failed: ${data.error || "Unknown error"}`)
                          }
                        } catch {
                          alert("Trade execution not available. Configure Builder API keys.")
                        }
                      }}
                    >
                      Execute Trade
                    </Button>
                    <a
                      href={`https://polymarket.com/market/${signal.market_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="no-underline"
                    >
                      <Button size="md" variant="ghost" icon={<ExternalLink size={15} />}>
                        Polymarket
                      </Button>
                    </a>
                  </div>
                )}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Score decomposition */}
        {signal.signal_strength != null && signal.trade_quality != null && (
          <motion.div variants={fadeUp}>
            <Card className="shadow-card">
              <h4 className="text-xs font-semibold font-display tracking-display text-txt-muted uppercase mb-4">
                Score Breakdown
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <DecompositionBar
                  label="Signal Strength"
                  description="How strongly the news impacts this market"
                  value={signal.signal_strength}
                  color={strengthColor(signal.signal_strength)}
                  weight="75%"
                />
                <DecompositionBar
                  label="Trade Quality"
                  description="How tradable the market is (liquidity, spread, timing)"
                  value={signal.trade_quality}
                  color={tradeQualityColor(signal.trade_quality)}
                  weight="25%"
                />
              </div>
            </Card>
          </motion.div>
        )}

        {/* LLM Analysis */}
        {signal.analysis && (
          <motion.div variants={fadeUp}>
            <Card className="shadow-card">
              <h4 className="text-xs font-semibold font-display tracking-display text-txt-muted uppercase mb-4 flex items-center gap-2">
                <Brain size={14} className="text-accent" /> AI Analysis
              </h4>
              {signal.analysis.reasoning && (
                <p className="text-sm text-txt-secondary leading-relaxed mb-4 italic">
                  "{signal.analysis.reasoning}"
                </p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {signal.analysis.catalysts && signal.analysis.catalysts.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-success uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Lightbulb size={12} /> Catalysts
                    </p>
                    <ul className="space-y-1.5">
                      {signal.analysis.catalysts.map((c, i) => (
                        <li key={i} className="text-sm text-txt-secondary flex items-start gap-2">
                          <span className="text-success mt-0.5 shrink-0">+</span>
                          <span>{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {signal.analysis.risks && signal.analysis.risks.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-danger uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <AlertTriangle size={12} /> Risks
                    </p>
                    <ul className="space-y-1.5">
                      {signal.analysis.risks.map((r, i) => (
                        <li key={i} className="text-sm text-txt-secondary flex items-start gap-2">
                          <span className="text-danger mt-0.5 shrink-0">-</span>
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              {/* LLM raw scores */}
              {(signal.analysis.impact_strength != null || signal.analysis.llm_confidence != null) && (
                <div className="flex gap-4 mt-4 pt-3 border-t border-edge-subtle">
                  {signal.analysis.impact_strength != null && (
                    <span className="text-[11px] text-txt-muted">
                      Impact: <span className="font-mono font-semibold text-txt-secondary">{(signal.analysis.impact_strength * 100).toFixed(0)}</span>
                    </span>
                  )}
                  {signal.analysis.llm_confidence != null && (
                    <span className="text-[11px] text-txt-muted">
                      LLM Confidence: <span className="font-mono font-semibold text-txt-secondary">{(signal.analysis.llm_confidence * 100).toFixed(0)}%</span>
                    </span>
                  )}
                  {signal.analysis.specificity_score != null && (
                    <span className="text-[11px] text-txt-muted">
                      Specificity: <span className="font-mono font-semibold text-txt-secondary">{(signal.analysis.specificity_score * 100).toFixed(0)}</span>
                    </span>
                  )}
                </div>
              )}
            </Card>
          </motion.div>
        )}

        {/* Score explanation + market context */}
        {(signal.score_explanation || signal.yes_probability_explanation) && (
          <motion.div variants={fadeUp}>
            <Card className="border-l-2 border-l-accent/40 shadow-card">
              {signal.score_explanation && (
                <div className="mb-3">
                  <h4 className="text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-1.5">
                    Why This Score
                  </h4>
                  <p className="text-sm text-txt-secondary leading-relaxed">{signal.score_explanation}</p>
                </div>
              )}
              {signal.yes_probability_explanation && (
                <div>
                  <h4 className="text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-1.5">
                    Market Context
                  </h4>
                  <p className="text-sm text-txt-secondary leading-relaxed">{signal.yes_probability_explanation}</p>
                </div>
              )}
              {signal.window_estimate && (
                <div className="mt-3 pt-2 border-t border-edge-subtle">
                  <span className="text-[11px] text-txt-muted">Resolution window: </span>
                  <span className="text-sm font-semibold text-txt-primary">{signal.window_estimate}</span>
                </div>
              )}
            </Card>
          </motion.div>
        )}

        {/* Key metrics */}
        <motion.div
          variants={fadeUp}
          className="grid grid-cols-2 md:grid-cols-3 gap-3"
        >
          <MetricBox label="Market (YES implied)" value={formatYesImpliedPct(signal.market_price_at_signal)} />
          <MetricBox label="Confidence" value={conf?.label || signal.confidence_label || "--"} color={conf?.color} />
          <MetricBox label="Urgency" value={urg?.label || signal.urgency_label || "--"} color={urg?.color} />
          {signal.market && (
            <>
              <MetricBox label="Spread" value={formatSpreadPp(signal.market.spread)} />
              <MetricBox label="Volume 24h" value={formatUsdCompact(signal.market.volume_24h)} />
              <MetricBox label="Liquidity" value={formatUsdCompact(signal.market.liquidity)} />
            </>
          )}
        </motion.div>

        {/* Price tracker */}
        {signal.outcome && (
          <motion.div variants={fadeUp}>
            <PriceTracker outcome={signal.outcome} priceAtSignal={signal.market_price_at_signal} />
          </motion.div>
        )}

        {/* Outcome */}
        {signal.outcome && (
          <motion.div variants={fadeUp}>
            <Card className="shadow-card">
              <h4 className="text-xs font-semibold font-display tracking-display text-txt-muted uppercase mb-4">
                Result
              </h4>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                <OutcomeBox label="+5 min" value={signal.outcome.price_t5min} />
                <OutcomeBox label="+15 min" value={signal.outcome.price_t15min} />
                <OutcomeBox label="+1h" value={signal.outcome.price_t1h} />
                <OutcomeBox label="+24h" value={signal.outcome.price_t24h} />
                <OutcomeBox label="Final" value={signal.outcome.price_resolved} />
                <div>
                  <span className="block text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-1">
                    Won?
                  </span>
                  <span className={`text-base font-semibold ${
                    signal.outcome.direction_correct === true
                      ? "text-success"
                      : signal.outcome.direction_correct === false
                      ? "text-danger"
                      : "text-txt-muted"
                  }`}>
                    {signal.outcome.direction_correct === true ? "Yes" : signal.outcome.direction_correct === false ? "No" : "Pending"}
                  </span>
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </motion.div>
    </div>
  )
}

function DecompositionBar({
  label,
  description,
  value,
  color,
  weight,
}: {
  label: string
  description: string
  value: number
  color: string
  weight: string
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-sm font-semibold font-display tracking-display text-txt-primary">{label}</span>
        <span className="font-mono text-lg font-bold" style={{ color }}>
          {Math.round(value)}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden mb-1 bg-surface-raised border border-edge-subtle">
        <motion.div
          className="h-2 rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(value, 100)}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <div className="flex justify-between">
        <span className="text-[10px] text-txt-muted">{description}</span>
        <span className="text-[10px] text-txt-muted">Weight: {weight}</span>
      </div>
    </div>
  )
}

function MetricBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Card className="p-4 shadow-card">
      <span className="block text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-1">{label}</span>
      <span className="text-lg font-semibold font-display tracking-display" style={{ color: color || "#E8ECF4" }}>{value}</span>
    </Card>
  )
}

function OutcomeBox({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <span className="block text-[11px] font-semibold font-display tracking-display text-txt-muted uppercase mb-1">{label}</span>
      <span className="text-base font-mono font-semibold text-txt-primary font-tabular">
        {value != null ? formatYesImpliedPct(value) : "Pending"}
      </span>
    </div>
  )
}
