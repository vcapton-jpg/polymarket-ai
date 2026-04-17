import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  BookOpen,
  BarChart3,
  Zap,
  Shield,
  HelpCircle,
  TrendingUp,
} from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"

const learnContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.06 },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: [0.22, 1, 0.36, 1] as const },
  },
}

export default function Learn() {
  return (
    <div>
      <PageHeader
        title="Learn"
        subtitle="Everything you need to understand prediction markets and trade smarter"
      />

      <motion.div
        className="flex flex-col gap-4"
        variants={learnContainer}
        initial="hidden"
        animate="visible"
      >
        <EducationSection
          icon={<BarChart3 size={22} />}
          title="What is a prediction market?"
          defaultOpen
        >
          <p className="text-sm text-txt-secondary leading-relaxed mb-4">
            A prediction market is a marketplace where you trade contracts based on
            the outcomes of real-world events. The price of a contract reflects how
            likely the crowd thinks that event is to happen.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-5">
            <ConceptCard
              title="Binary contracts"
              desc="Contracts pay $1 if the event happens, $0 if it doesn't. Buying at $0.60 means you think there's more than a 60% chance."
            />
            <ConceptCard
              title="Price = Probability"
              desc="A contract trading at $0.75 means the market estimates a 75% chance. If you disagree, there's a trade to be made."
            />
            <ConceptCard
              title="Polymarket"
              desc="One of the largest prediction markets. It offers contracts on politics, economics, crypto, sports, and more."
            />
          </div>
          <div className="rounded-xl border border-edge-subtle border-l-4 border-l-accent bg-accent-muted/50 p-5 shadow-glass">
            <h4 className="text-xs font-semibold font-display tracking-display text-accent-bright uppercase mb-2">
              Example
            </h4>
            <p className="text-sm text-txt-secondary leading-relaxed">
              &ldquo;Will Bitcoin exceed $100,000 by Dec 31?&rdquo; trades at $0.42.
              That means the market estimates a 42% probability. If you believe the
              real probability is closer to 60%, buying at $0.42 gives you an edge.
            </p>
          </div>
        </EducationSection>

        <EducationSection
          icon={<Zap size={22} />}
          title="How to read an opportunity"
        >
          <p className="text-sm text-txt-secondary leading-relaxed mb-4">
            Our platform detects news that could move a Polymarket contract's price
            and delivers it to you as an opportunity. Here's what each indicator means:
          </p>
          <div className="flex flex-col gap-5">
            <MetricExplainer
              name="Opportunity Score (0-100)"
              desc="Overall strength of the opportunity. Higher means a stronger connection between the news event and the market. Think of it as our confidence."
              threshold="80+ = Strong, 60-79 = Moderate, <60 = Speculative"
            />
            <MetricExplainer
              name="Direction (BUY YES / BUY NO)"
              desc="Our recommended trade direction based on how the news is expected to impact the outcome."
              threshold="BUY YES = event raises probability, BUY NO = lowers it"
            />
            <MetricExplainer
              name="Confidence (High / Medium / Low)"
              desc="How clear the connection is between the news and the market. A clear, direct cause-and-effect relationship means high confidence."
              threshold="High = clear link, Low = indirect or ambiguous"
            />
            <MetricExplainer
              name="Urgency (Critical / High / Medium / Low)"
              desc="How quickly the market is likely to react. Breaking news = critical urgency, meaning you should act fast."
              threshold="Critical = minutes, Low = days"
            />
            <MetricExplainer
              name="Market Conditions (Excellent / Good / Fair)"
              desc="Whether the market is easy to trade. Considers the bid-ask spread, available liquidity, and recent trading volume."
              threshold="Excellent = tight spread + deep liquidity"
            />
          </div>
        </EducationSection>

        <EducationSection
          icon={<TrendingUp size={22} />}
          title="Trading strategies"
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <StrategyCard
              title="Getting Started"
              steps={[
                "Filter opportunities with a score of 70+ and high confidence",
                "Check the market spread (below $0.05 is ideal)",
                "Make sure there's enough liquidity ($10K+ recommended)",
                "Click the Polymarket link and place your trade",
                "Monitor the price movement after your entry",
              ]}
            />
            <StrategyCard
              title="Risk Management"
              steps={[
                "Never risk more than 5% of your total capital on a single market",
                "Diversify across different categories (politics, crypto, etc.)",
                "Watch the early price movement (+5min, +15min) for confirmation",
                "Take partial profits if the price moves 10%+ in your favor",
                "Consider exiting before resolution to lock in gains",
              ]}
            />
            <StrategyCard
              title="Position Sizing"
              steps={[
                "Calculate your edge: your estimate vs. market price",
                "Start small with low-confidence opportunities",
                "Increase size only on high-confidence, high-urgency setups",
                "Leave cash available for sudden breaking news opportunities",
                "Track your results to refine your strategy over time",
              ]}
            />
          </div>
        </EducationSection>

        <EducationSection
          icon={<BookOpen size={22} />}
          title="Glossary"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {GLOSSARY.map(({ term, def }) => (
              <div
                key={term}
                className="rounded-lg border border-edge-subtle bg-surface-raised p-3.5 shadow-glass"
              >
                <h4 className="text-sm font-semibold font-display tracking-display text-accent-bright mb-1">
                  {term}
                </h4>
                <p className="text-[0.82rem] text-txt-muted leading-relaxed">{def}</p>
              </div>
            ))}
          </div>
        </EducationSection>

        <EducationSection
          icon={<HelpCircle size={22} />}
          title="Frequently Asked Questions"
        >
          <div className="flex flex-col gap-2">
            {FAQ.map(({ q, a }) => (
              <FaqItem key={q} question={q} answer={a} />
            ))}
          </div>
        </EducationSection>
      </motion.div>
    </div>
  )
}

function EducationSection({
  icon,
  title,
  children,
  defaultOpen,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen ?? false)

  return (
    <motion.div variants={fadeUp}>
      <Card className="shadow-card p-0 overflow-hidden">
        <div
          className="flex items-center gap-3 cursor-pointer select-none p-5 md:p-6 pb-0 md:pb-0"
          onClick={() => setOpen(!open)}
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-muted text-accent border border-edge-subtle shadow-glass">
            {icon}
          </div>
          <h2 className="font-display text-lg font-semibold tracking-display text-txt-primary flex-1">
            {title}
          </h2>
          <div className="text-txt-muted shrink-0">
            {open ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
          </div>
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <div className="px-5 md:px-6 pt-5 pb-5 md:pb-6 mt-4 border-t border-edge-subtle">
                {children}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}

function ConceptCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-xl border border-edge-subtle bg-surface-raised p-5 shadow-glass">
      <h4 className="text-[0.95rem] font-semibold font-display tracking-display text-txt-primary mb-2">
        {title}
      </h4>
      <p className="text-[0.85rem] text-txt-muted leading-relaxed">{desc}</p>
    </div>
  )
}

function MetricExplainer({
  name,
  desc,
  threshold,
}: {
  name: string
  desc: string
  threshold: string
}) {
  return (
    <div className="rounded-xl border border-edge-subtle bg-surface-raised p-4 shadow-glass">
      <h4 className="text-[0.95rem] font-semibold font-display tracking-display text-txt-primary mb-1.5">
        {name}
      </h4>
      <p className="text-sm text-txt-secondary leading-relaxed">{desc}</p>
      <div className="mt-2 flex items-center gap-1.5 rounded-lg bg-accent-muted px-3 py-1.5 border border-edge-subtle">
        <Shield size={14} className="text-accent shrink-0" />
        <span className="text-[0.8rem] font-medium text-accent">{threshold}</span>
      </div>
    </div>
  )
}

function StrategyCard({ title, steps }: { title: string; steps: string[] }) {
  return (
    <div className="rounded-xl border border-edge-subtle bg-surface-raised p-6 shadow-glass">
      <h4 className="text-base font-semibold font-display tracking-display text-txt-primary mb-4">
        {title}
      </h4>
      <ol className="list-none p-0 flex flex-col gap-2.5">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2.5 text-[0.85rem] text-txt-secondary leading-relaxed">
            <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-accent-muted text-[0.7rem] font-bold text-accent border border-edge-subtle">
              {i + 1}
            </span>
            <span>{s}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function FaqItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false)

  return (
    <div
      className="rounded-lg border border-edge-subtle bg-surface-raised px-4 py-3.5 cursor-pointer shadow-glass hover:border-edge-accent/30 hover:shadow-card-hover transition-all"
      onClick={() => setOpen(!open)}
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-txt-primary">
        <span className="flex-1">{question}</span>
        {open ? <ChevronDown size={16} className="text-txt-muted shrink-0" /> : <ChevronRight size={16} className="text-txt-muted shrink-0" />}
      </div>
      <AnimatePresence>
        {open && (
          <motion.p
            className="text-[0.85rem] text-txt-muted leading-relaxed mt-2.5 overflow-hidden"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            {answer}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}

const GLOSSARY = [
  { term: "Spread", def: "Difference between the buy and sell price. A tighter spread means a more liquid, easier-to-trade market." },
  { term: "Liquidity", def: "Total capital available in the order book. More liquidity means you can trade larger amounts without moving the price." },
  { term: "Bid / Ask", def: "Bid is the highest price a buyer will pay. Ask is the lowest price a seller will accept. The gap between them is the spread." },
  { term: "Volume", def: "Total value of contracts traded in a period (usually 24 hours). High volume indicates active interest." },
  { term: "Resolution", def: "When a market's outcome is determined and contracts pay out $1.00 (happened) or $0.00 (didn't happen)." },
  { term: "Implied Probability", def: "The probability implied by the current price. A contract at $0.65 implies a 65% probability of the event occurring." },
  { term: "Opportunity Score", def: "Our 0-100 composite score representing the overall strength of a trading opportunity." },
]

const FAQ = [
  {
    q: "How accurate are the opportunities?",
    a: "Our accuracy is tracked transparently on the Performance page. We show the win rate across all resolved opportunities, broken down by category. Past performance doesn't guarantee future results.",
  },
  {
    q: "How fast do I get notified?",
    a: "Opportunities appear within minutes of the news breaking. Our AI continuously monitors global news sources so you don't have to. Critical-urgency opportunities appear fastest.",
  },
  {
    q: "Can I trade directly from this platform?",
    a: "Not yet. Each opportunity includes a direct link to the relevant Polymarket contract. Click the 'Trade on Polymarket' button on any opportunity detail page to go straight to the market.",
  },
  {
    q: "Is my money at risk on this platform?",
    a: "No. Signal does not hold or manage any of your funds. We only provide trading intelligence. All trades are executed by you on Polymarket, where you control your own wallet.",
  },
  {
    q: "How is the win rate calculated?",
    a: "An opportunity is a 'win' if the price moved in the predicted direction by the time the market resolved. We track price snapshots at +5min, +15min, +1h, +24h, and at resolution.",
  },
  {
    q: "Is this financial advice?",
    a: "No. Signal provides informational trading opportunities based on AI analysis. Always do your own research and never invest more than you can afford to lose.",
  },
]
