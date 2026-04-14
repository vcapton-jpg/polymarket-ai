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

export default function Learn() {
  return (
    <div>
      <PageHeader
        title="Learn"
        subtitle="Everything you need to understand prediction markets and trade smarter"
      />

      <div style={styles.sections}>
        <EducationSection
          icon={<BarChart3 size={22} />}
          title="What is a prediction market?"
          defaultOpen
        >
          <p style={styles.text}>
            A prediction market is a marketplace where you trade contracts based on
            the outcomes of real-world events. The price of a contract reflects how
            likely the crowd thinks that event is to happen.
          </p>
          <div style={styles.conceptGrid}>
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
          <div style={styles.exampleBox}>
            <h4 style={styles.exampleTitle}>Example</h4>
            <p style={styles.text}>
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
          <p style={styles.text}>
            Our platform detects news that could move a Polymarket contract's price
            and delivers it to you as an opportunity. Here's what each indicator means:
          </p>
          <div style={styles.metricList}>
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
          <div style={styles.strategyGrid}>
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
          <div style={styles.glossaryGrid}>
            {GLOSSARY.map(({ term, def }) => (
              <div key={term} style={styles.glossaryItem}>
                <h4 style={styles.glossaryTerm}>{term}</h4>
                <p style={styles.glossaryDef}>{def}</p>
              </div>
            ))}
          </div>
        </EducationSection>

        <EducationSection
          icon={<HelpCircle size={22} />}
          title="Frequently Asked Questions"
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {FAQ.map(({ q, a }) => (
              <FaqItem key={q} question={q} answer={a} />
            ))}
          </div>
        </EducationSection>
      </div>
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
    <Card>
      <div style={styles.sectionHeader} onClick={() => setOpen(!open)}>
        <div style={styles.sectionIcon}>{icon}</div>
        <h2 style={styles.sectionTitle}>{title}</h2>
        <div style={{ marginLeft: "auto", color: "var(--text-muted)" }}>
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
            style={{ overflow: "hidden" }}
          >
            <div style={styles.sectionBody}>{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

function ConceptCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div style={styles.conceptCard}>
      <h4 style={styles.conceptTitle}>{title}</h4>
      <p style={styles.conceptDesc}>{desc}</p>
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
    <div style={styles.metricItem}>
      <h4 style={styles.metricName}>{name}</h4>
      <p style={styles.text}>{desc}</p>
      <div style={styles.thresholdBox}>
        <Shield size={14} color="var(--color-primary)" />
        <span style={styles.thresholdText}>{threshold}</span>
      </div>
    </div>
  )
}

function StrategyCard({ title, steps }: { title: string; steps: string[] }) {
  return (
    <div style={styles.strategyCard}>
      <h4 style={styles.strategyTitle}>{title}</h4>
      <ol style={styles.stepList}>
        {steps.map((s, i) => (
          <li key={i} style={styles.stepItem}>
            <span style={styles.stepNum}>{i + 1}</span>
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
    <div style={styles.faqItem} onClick={() => setOpen(!open)}>
      <div style={styles.faqQ}>
        <span style={{ flex: 1 }}>{question}</span>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </div>
      <AnimatePresence>
        {open && (
          <motion.p
            style={styles.faqA}
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

const styles: Record<string, React.CSSProperties> = {
  sections: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  sectionHeader: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    cursor: "pointer",
    userSelect: "none",
  },
  sectionIcon: {
    width: 40,
    height: 40,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "var(--radius-sm)",
    background: "rgba(99,102,241,0.1)",
    color: "var(--color-primary)",
    flexShrink: 0,
  },
  sectionTitle: {
    fontSize: "1.15rem",
    fontWeight: 600,
    color: "var(--text-primary)",
  },
  sectionBody: {
    paddingTop: "20px",
    marginTop: "16px",
    borderTop: "1px solid var(--border-light)",
  },
  text: {
    fontSize: "0.9rem",
    color: "var(--text-secondary)",
    lineHeight: 1.7,
    marginBottom: "16px",
  },
  conceptGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "16px",
    marginBottom: "20px",
  },
  conceptCard: {
    padding: "20px",
    background: "var(--bg-tertiary)",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--border-light)",
  },
  conceptTitle: {
    fontSize: "0.95rem",
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: "8px",
  },
  conceptDesc: {
    fontSize: "0.85rem",
    color: "var(--text-muted)",
    lineHeight: 1.6,
  },
  exampleBox: {
    padding: "20px",
    background: "rgba(99,102,241,0.06)",
    borderRadius: "var(--radius-md)",
    borderLeft: "3px solid var(--color-primary)",
  },
  exampleTitle: {
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "var(--color-primary)",
    marginBottom: "8px",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  },
  metricList: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  metricItem: {
    padding: "16px",
    background: "var(--bg-tertiary)",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--border-light)",
  },
  metricName: {
    fontSize: "0.95rem",
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: "6px",
  },
  thresholdBox: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    marginTop: "8px",
    padding: "6px 12px",
    background: "rgba(99,102,241,0.06)",
    borderRadius: "var(--radius-sm)",
  },
  thresholdText: {
    fontSize: "0.8rem",
    color: "var(--color-primary)",
    fontWeight: 500,
  },
  strategyGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: "16px",
  },
  strategyCard: {
    padding: "24px",
    background: "var(--bg-tertiary)",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--border-light)",
  },
  strategyTitle: {
    fontSize: "1rem",
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: "16px",
  },
  stepList: {
    listStyle: "none",
    padding: 0,
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  stepItem: {
    display: "flex",
    gap: "10px",
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    lineHeight: 1.5,
  },
  stepNum: {
    width: 22,
    height: 22,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    background: "rgba(99,102,241,0.12)",
    color: "var(--color-primary)",
    fontSize: "0.7rem",
    fontWeight: 700,
    flexShrink: 0,
  },
  glossaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
    gap: "12px",
  },
  glossaryItem: {
    padding: "14px",
    background: "var(--bg-tertiary)",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border-light)",
  },
  glossaryTerm: {
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "var(--color-primary-hover)",
    marginBottom: "4px",
  },
  glossaryDef: {
    fontSize: "0.82rem",
    color: "var(--text-muted)",
    lineHeight: 1.5,
  },
  faqItem: {
    padding: "14px 16px",
    background: "var(--bg-tertiary)",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border-light)",
    cursor: "pointer",
  },
  faqQ: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "var(--text-primary)",
  },
  faqA: {
    fontSize: "0.85rem",
    color: "var(--text-muted)",
    lineHeight: 1.7,
    marginTop: "10px",
    overflow: "hidden",
  },
}
