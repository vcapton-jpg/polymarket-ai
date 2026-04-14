import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import {
  Zap,
  BarChart3,
  TrendingUp,
  Radio,
  ArrowRight,
  Crosshair,
  Eye,
  MousePointerClick,
  ExternalLink,
  SlidersHorizontal,
  Shield,
} from "lucide-react"
import { Button } from "../components/ui/Button"

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.5, ease: "easeOut" as const },
  }),
}

export default function Landing() {
  const nav = useNavigate()

  return (
    <div className="min-h-screen overflow-hidden">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-surface-0/85 backdrop-blur-xl" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <div className="max-w-[1200px] mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Crosshair size={22} className="text-accent" />
            <span className="text-xl font-bold bg-gradient-to-r from-amber-400 to-amber-500 bg-clip-text text-transparent">
              Signal
            </span>
          </div>
          <Button variant="primary" size="sm" onClick={() => nav("/dashboard")}>
            Open App <ArrowRight size={14} />
          </Button>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative min-h-screen flex items-center justify-center px-6 pt-24 pb-20 overflow-hidden">
        <div className="absolute w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.1)_0%,transparent_70%)] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none" />
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0}
          className="relative text-center max-w-[720px]"
        >
          <span className="inline-block px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold mb-6">
            AI-Powered Prediction Market Platform
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold leading-tight mb-5 text-txt-primary">
            Your <span className="text-accent">AI team</span> trades
            <br />prediction markets for you
          </h1>
          <p className="text-lg text-txt-muted leading-relaxed mb-9 max-w-xl mx-auto">
            6 specialized AI agents monitor news, analyze impact, size positions, execute trades on Polymarket, manage risk, and report — all running 24/7.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Button size="lg" onClick={() => nav("/dashboard")}>
              Open Dashboard <ArrowRight size={16} />
            </Button>
            <Button variant="secondary" size="lg" onClick={() => nav("/learn")}>
              How It Works
            </Button>
          </div>
        </motion.div>
      </section>

      {/* How it works */}
      <section className="py-20 px-6 max-w-[1200px] mx-auto">
        <motion.h2
          className="text-center text-3xl font-bold mb-12 text-txt-primary"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0}
        >
          How it works
        </motion.h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.title}
              className="text-center p-8"
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              variants={fadeUp}
              custom={i}
            >
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-accent/12 text-accent text-sm font-bold mb-4">
                {i + 1}
              </div>
              <step.icon size={28} className="text-accent mx-auto mb-3" strokeWidth={1.5} />
              <h3 className="text-lg font-semibold text-txt-primary mb-2">{step.title}</h3>
              <p className="text-sm text-txt-muted leading-relaxed">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6 bg-surface-card">
        <div className="max-w-[1200px] mx-auto">
          <motion.h2
            className="text-center text-3xl font-bold mb-12 text-txt-primary"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            custom={0}
          >
            Platform Features
          </motion.h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                className="bg-surface-raised rounded-lg p-6 shadow-card transition-all hover:shadow-card-hover"
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fadeUp}
                custom={i}
              >
                <div className="w-11 h-11 flex items-center justify-center rounded-md bg-accent/10 text-accent mb-4">
                  <f.icon size={22} strokeWidth={1.5} />
                </div>
                <h3 className="text-base font-semibold text-txt-primary mb-2">{f.title}</h3>
                <p className="text-sm text-txt-muted leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 max-w-[1200px] mx-auto text-center">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0}
        >
          <h2 className="text-3xl font-bold mb-4 text-txt-primary">Ready to get an edge?</h2>
          <p className="text-txt-muted mb-8 max-w-md mx-auto">
            Join traders who receive real-time opportunities powered by AI, before the market reacts.
          </p>
          <Button size="lg" onClick={() => nav("/dashboard")}>
            Open Dashboard <ArrowRight size={16} />
          </Button>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="py-6 px-6" style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        <div className="max-w-[1200px] mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Crosshair size={16} className="text-accent" />
            <span className="font-bold text-txt-primary">Signal</span>
          </div>
          <span className="text-xs text-txt-muted">&copy; {new Date().getFullYear()} Signal Platform</span>
        </div>
      </footer>
    </div>
  )
}

const STEPS = [
  { icon: Eye, title: "Agents Detect", desc: "Scout Agent monitors thousands of news sources 24/7 — press agencies, social media, financial feeds — so no market-moving event is missed." },
  { icon: Crosshair, title: "Agents Analyze", desc: "Analyst and Strategist agents score impact, size positions with Kelly criterion, and generate actionable trade recommendations." },
  { icon: MousePointerClick, title: "Agents Execute", desc: "Trader Agent executes directly on Polymarket via Builder API. Risk Manager monitors your positions and alerts on adverse moves." },
]

const FEATURES = [
  { icon: Zap, title: "6 AI Agents", desc: "Scout, Analyst, Strategist, Trader, Risk Manager, and Reporter — a complete team working for you." },
  { icon: BarChart3, title: "Auto Execution", desc: "Trade directly on Polymarket through the Builder API — gas-free, attribution-tagged." },
  { icon: TrendingUp, title: "Portfolio Tracking", desc: "Real-time P&L, position monitoring, and risk alerts across all your prediction market trades." },
  { icon: Shield, title: "Risk Management", desc: "Stop-loss alerts, concentration limits, and correlation detection to protect your portfolio." },
  { icon: ExternalLink, title: "Daily Briefs", desc: "Reporter Agent generates intelligence briefs with performance summaries and market outlook." },
  { icon: SlidersHorizontal, title: "Multi-Channel", desc: "Dashboard, Telegram bot, and B2B API — access your signals and trade from anywhere." },
]
