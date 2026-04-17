import { useNavigate } from "react-router-dom"
import { motion, useScroll, useTransform, useInView } from "framer-motion"
import { useRef, useEffect, useState } from "react"
import {
  Triangle,
  ArrowRight,
  Zap,
  Shield,
  BarChart3,
  TrendingUp,
  Radio,
  Eye,
  Brain,
  Check,
  Crown,
  Building2,
  Bell,
  ExternalLink,
  Activity,
  Globe,
} from "lucide-react"

/* ─── animation variants ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 24, filter: "blur(6px)" },
  visible: (i: number) => ({
    opacity: 1, y: 0, filter: "blur(0px)",
    transition: { delay: i * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
  }),
}
const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
}

/* ─── animated counter ─── */
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const [val, setVal] = useState(0)

  useEffect(() => {
    if (!inView) return
    let frame: number
    const start = performance.now()
    const duration = 1200
    const step = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setVal(Math.round(eased * target))
      if (progress < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [inView, target])

  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>
}

export default function Landing() {
  const nav = useNavigate()
  const { scrollYProgress } = useScroll()
  const heroOpacity = useTransform(scrollYProgress, [0, 0.12], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.12], [1, 0.97])

  return (
    <div className="min-h-screen bg-surface-0 overflow-hidden">
      {/* ─── Navbar ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-edge-subtle">
        <div className="max-w-[1200px] mx-auto px-6 h-16 flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center">
              <Triangle size={16} strokeWidth={1.8} className="text-accent fill-accent/20" />
            </div>
            <span className="text-lg font-display font-bold tracking-display text-txt-primary">Foresight</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            {["How it works", "Features", "Pricing"].map((s) => (
              <a key={s} href={`#${s.toLowerCase().replace(/ /g, "")}`} className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">
                {s}
              </a>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => nav("/auth")} className="text-sm font-medium text-txt-muted hover:text-txt-primary transition-colors bg-transparent border-none cursor-pointer">
              Sign in
            </button>
            <button
              onClick={() => nav("/auth")}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-sm font-bold hover:brightness-110 transition-all cursor-pointer border-none shadow-glow"
            >
              Start free
            </button>
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <motion.section
        style={{ opacity: heroOpacity, scale: heroScale }}
        className="relative min-h-[100vh] flex items-center justify-center px-6 pt-16"
      >
        <div className="absolute inset-0 bg-mesh pointer-events-none" />
        <div className="absolute top-[15%] left-1/2 -translate-x-1/2 w-[900px] h-[900px] rounded-full bg-[radial-gradient(circle,rgba(212,160,23,0.07)_0%,transparent_55%)] pointer-events-none" />

        <div className="relative text-center max-w-[800px]">
          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={0}>
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass-card border border-accent/15 text-accent text-xs font-semibold mb-8 gradient-border">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-live" />
              Research-grade prediction market intelligence
            </span>
          </motion.div>

          <motion.h1
            initial="hidden" animate="visible" variants={fadeUp} custom={1}
            className="text-[2.75rem] md:text-[3.75rem] lg:text-[4.5rem] font-display font-extrabold leading-[1.06] tracking-display text-txt-primary mb-6"
          >
            Trade with
            <br />
            <span className="text-gradient-gold">clarity and conviction</span>
          </motion.h1>

          <motion.p
            initial="hidden" animate="visible" variants={fadeUp} custom={2}
            className="text-lg md:text-xl text-txt-secondary leading-relaxed mb-10 max-w-[600px] mx-auto"
          >
            Foresight matches breaking news to Polymarket contracts using deep AI analysis — then scores every opportunity with plain-English reasoning you can actually act on.
          </motion.p>

          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={3} className="flex gap-4 justify-center flex-wrap">
            <button
              onClick={() => nav("/auth")}
              className="group px-8 py-3.5 rounded-xl bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-base font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-2 shadow-glow-lg animate-glow-pulse"
            >
              Start free
              <ArrowRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
            <button
              onClick={() => document.getElementById("howitworks")?.scrollIntoView({ behavior: "smooth" })}
              className="px-8 py-3.5 rounded-xl glass-card text-txt-secondary text-base font-semibold hover:text-accent hover:border-accent/20 transition-all cursor-pointer border border-edge"
            >
              See how it works
            </button>
          </motion.div>

          {/* Stats */}
          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={4} className="mt-16 flex items-center justify-center gap-10 flex-wrap">
            {[
              { value: 12400, suffix: "+", label: "Signals generated" },
              { value: 68, suffix: "%", label: "Win rate" },
              { value: 30, suffix: "s", label: "Avg detection" },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-2xl md:text-3xl font-display font-extrabold text-txt-primary font-tabular">
                  <Counter target={s.value} suffix={s.suffix} />
                </div>
                <span className="text-xs text-txt-muted">{s.label}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </motion.section>

      {/* ─── Signal Preview (Terminal style) ─── */}
      <section className="py-20 px-6">
        <div className="max-w-[900px] mx-auto">
          <motion.div
            initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp} custom={0}
            className="glass-card rounded-2xl overflow-hidden shadow-[0_8px_48px_rgba(0,0,0,0.5)]"
          >
            {/* Terminal header */}
            <div className="flex items-center gap-2 px-5 py-3 bg-surface-0/60 border-b border-edge-subtle">
              <span className="w-3 h-3 rounded-full bg-danger/60" />
              <span className="w-3 h-3 rounded-full bg-warning/60" />
              <span className="w-3 h-3 rounded-full bg-success/60" />
              <span className="text-[11px] text-txt-muted font-mono ml-2">foresight — live signal feed</span>
            </div>

            <div className="p-6 md:p-8">
              <div className="flex items-center gap-2 mb-5">
                <Activity size={14} className="text-success" />
                <span className="text-[11px] font-bold text-success uppercase tracking-widest font-mono">SIGNAL DETECTED</span>
                <span className="text-[10px] text-txt-muted font-mono ml-auto">12 min ago</span>
              </div>

              <div className="flex flex-col md:flex-row gap-6">
                <div className="flex-1">
                  <p className="text-[11px] text-txt-muted font-mono mb-1.5 flex items-center gap-1.5">
                    <Globe size={10} />
                    Reuters Wire
                  </p>
                  <h3 className="text-xl font-display font-bold text-txt-primary mb-3 leading-snug">
                    Trump announces new sanctions on Iran
                  </h3>
                  <p className="text-sm text-txt-secondary leading-relaxed mb-5">
                    Oil prices are likely to rise — Iran produces 3% of global oil.
                    Less Iranian oil on the market = higher prices worldwide.
                  </p>

                  <div className="glass-card rounded-xl p-4">
                    <p className="text-[10px] font-bold text-txt-muted uppercase tracking-wider mb-2 font-mono">CONTRACT MATCHED</p>
                    <a
                      href="https://polymarket.com/event/oil-prices"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-bold text-accent hover:text-accent-bright transition-colors flex items-center gap-1.5 no-underline"
                    >
                      Will oil go above $90/barrel?
                      <ExternalLink size={12} className="shrink-0" />
                    </a>
                    <p className="text-xs text-txt-muted mt-1.5">
                      Market currently says <strong className="text-txt-primary font-mono">34%</strong> — our model thinks this is underpriced.
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-3 md:w-[200px] shrink-0">
                  <div className="glass-card rounded-xl p-4 text-center">
                    <p className="text-[10px] text-txt-muted uppercase tracking-wider mb-1 font-mono">SCORE</p>
                    <p className="text-4xl font-extrabold font-mono text-gradient-gold leading-none">87</p>
                    <p className="text-[11px] text-txt-muted mt-1 font-mono">/100</p>
                  </div>
                  <div className="glass-card rounded-xl p-4 text-center border-success/20 border">
                    <p className="text-base font-bold text-success flex items-center justify-center gap-1.5 font-mono">
                      <TrendingUp size={16} />
                      BUY YES
                    </p>
                    <p className="text-xs text-txt-muted mt-1">High conviction</p>
                  </div>
                  <p className="text-[10px] text-txt-muted text-center leading-relaxed font-mono">
                    Detected &amp; scored<br />automatically in 28s
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── How it works (Timeline) ─── */}
      <section id="howitworks" className="py-24 px-6">
        <div className="max-w-[800px] mx-auto">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0} className="text-center mb-16">
            <span className="text-[11px] font-bold text-accent uppercase tracking-[0.2em] mb-3 block font-mono">How it works</span>
            <h2 className="text-3xl md:text-4xl font-display font-extrabold tracking-display text-txt-primary">
              From news to <span className="text-gradient-gold">actionable conviction</span>
            </h2>
          </motion.div>

          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-accent/30 via-accent/10 to-transparent" />

            {STEPS.map((step, i) => (
              <motion.div
                key={step.title}
                initial="hidden" whileInView="visible" viewport={{ once: true }}
                variants={fadeUp} custom={i}
                className="relative pl-16 pb-12 last:pb-0"
              >
                <div className="absolute left-3 top-1 w-7 h-7 rounded-full glass-card border border-accent/20 flex items-center justify-center shadow-[0_0_12px_rgba(212,160,23,0.15)]">
                  <span className="text-xs font-bold text-accent font-mono">{i + 1}</span>
                </div>
                <div className="glass-card rounded-xl p-5 border border-edge-subtle hover:border-accent/15 transition-colors">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent shrink-0">
                      <step.icon size={20} strokeWidth={1.5} />
                    </div>
                    <h3 className="text-base font-display font-bold text-txt-primary">{step.title}</h3>
                  </div>
                  <p className="text-sm text-txt-secondary leading-relaxed">{step.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features (Bento) ─── */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-[1100px] mx-auto">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0} className="text-center mb-16">
            <span className="text-[11px] font-bold text-accent uppercase tracking-[0.2em] mb-3 block font-mono">Features</span>
            <h2 className="text-3xl md:text-4xl font-display font-extrabold tracking-display text-txt-primary">
              Everything you need to <span className="text-gradient-gold">decide with confidence</span>
            </h2>
          </motion.div>

          <motion.div
            initial="hidden" whileInView="visible" viewport={{ once: true }}
            variants={stagger}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          >
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                variants={fadeUp} custom={0}
                className={`glass-card rounded-xl p-6 border border-edge-subtle hover:border-accent/15 transition-all duration-300 group ${
                  i < 2 ? "lg:col-span-1 lg:row-span-1" : ""
                }`}
              >
                <div className="w-11 h-11 rounded-xl bg-accent-muted flex items-center justify-center text-accent mb-4 group-hover:bg-accent/20 group-hover:shadow-[0_0_16px_rgba(212,160,23,0.12)] transition-all">
                  <f.icon size={22} strokeWidth={1.5} />
                </div>
                <h3 className="text-[15px] font-display font-bold text-txt-primary mb-2">{f.title}</h3>
                <p className="text-sm text-txt-muted leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── Pricing ─── */}
      <section id="pricing" className="py-24 px-6">
        <div className="max-w-[1100px] mx-auto">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0} className="text-center mb-16">
            <span className="text-[11px] font-bold text-accent uppercase tracking-[0.2em] mb-3 block font-mono">Pricing</span>
            <h2 className="text-3xl md:text-4xl font-display font-extrabold tracking-display text-txt-primary mb-4">
              Start free, <span className="text-gradient-gold">upgrade when ready</span>
            </h2>
            <p className="text-txt-secondary max-w-lg mx-auto">Every plan includes live signals. Pro unlocks full history, richer explanations, and alerts.</p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-[960px] mx-auto">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial="hidden" whileInView="visible" viewport={{ once: true }}
                variants={fadeUp} custom={i}
                className={`relative glass-card rounded-2xl p-7 border transition-all duration-300 ${
                  plan.popular
                    ? "border-accent/30 shadow-[0_0_40px_rgba(212,160,23,0.08)] gradient-border"
                    : "border-edge-subtle hover:border-edge"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-[11px] font-bold tracking-wider shadow-glow">
                    POPULAR
                  </div>
                )}
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${plan.color}12`, color: plan.color }}>
                    <plan.icon size={22} />
                  </div>
                  <h3 className="text-lg font-display font-bold text-txt-primary">{plan.name}</h3>
                </div>
                <div className="mb-6">
                  <span className="text-4xl font-extrabold text-txt-primary font-mono">{plan.price === 0 ? "0" : plan.price}€</span>
                  {plan.price > 0 && <span className="text-sm text-txt-muted">/mo</span>}
                  {plan.price === 0 && <span className="text-sm text-txt-muted ml-1">forever</span>}
                </div>
                <ul className="flex flex-col gap-3 mb-7">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-txt-secondary">
                      <Check size={15} className="text-success mt-0.5 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => nav("/auth")}
                  className={`w-full py-3 rounded-xl text-sm font-bold transition-all cursor-pointer border-none ${
                    plan.popular
                      ? "bg-gradient-to-r from-accent to-accent-bright text-surface-0 hover:brightness-110 shadow-glow"
                      : "glass-card text-txt-secondary hover:text-accent border border-edge-subtle"
                  }`}
                >
                  {plan.cta}
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Final CTA ─── */}
      <section className="py-24 px-6">
        <motion.div
          initial="hidden" whileInView="visible" viewport={{ once: true }}
          variants={fadeUp} custom={0}
          className="max-w-[700px] mx-auto text-center"
        >
          <div className="w-16 h-16 rounded-2xl bg-accent-muted flex items-center justify-center text-accent mx-auto mb-6 shadow-glow">
            <Triangle size={32} strokeWidth={1.5} className="fill-accent/20" />
          </div>
          <h2 className="text-3xl md:text-4xl font-display font-extrabold tracking-display text-txt-primary mb-4">
            Ready to see the full picture?
          </h2>
          <p className="text-lg text-txt-secondary mb-10 max-w-md mx-auto leading-relaxed">
            Join traders who combine fast detection with structured analysis — so every signal is something you can actually understand and act on.
          </p>
          <button
            onClick={() => nav("/auth")}
            className="group px-8 py-4 rounded-xl bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-lg font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-3 mx-auto shadow-glow-lg"
          >
            Create free account
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </motion.div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="py-12 px-6 border-t border-edge-subtle">
        <div className="max-w-[1200px] mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10">
            <div>
              <div className="flex items-center gap-2.5 mb-3">
                <div className="w-7 h-7 rounded-lg bg-accent-muted flex items-center justify-center">
                  <Triangle size={14} strokeWidth={1.8} className="text-accent fill-accent/20" />
                </div>
                <span className="font-display font-bold text-txt-primary">Foresight</span>
              </div>
              <p className="text-sm text-txt-muted leading-relaxed">
                AI-powered prediction market intelligence. Speed matters, but depth wins.
              </p>
            </div>
            <div>
              <h4 className="text-xs font-bold text-txt-secondary uppercase tracking-wider mb-3">Product</h4>
              <div className="flex flex-col gap-2">
                <a href="#howitworks" className="text-sm text-txt-muted hover:text-txt-secondary transition-colors no-underline">How it works</a>
                <a href="#features" className="text-sm text-txt-muted hover:text-txt-secondary transition-colors no-underline">Features</a>
                <a href="#pricing" className="text-sm text-txt-muted hover:text-txt-secondary transition-colors no-underline">Pricing</a>
              </div>
            </div>
            <div>
              <h4 className="text-xs font-bold text-txt-secondary uppercase tracking-wider mb-3">Resources</h4>
              <div className="flex flex-col gap-2">
                <a href="https://polymarket.com" target="_blank" rel="noopener noreferrer" className="text-sm text-txt-muted hover:text-txt-secondary transition-colors no-underline">Polymarket</a>
                <span className="text-sm text-txt-muted">API docs (coming soon)</span>
              </div>
            </div>
            <div>
              <h4 className="text-xs font-bold text-txt-secondary uppercase tracking-wider mb-3">Contact</h4>
              <span className="text-sm text-txt-muted">hello@getforesight.io</span>
            </div>
          </div>
          <div className="flex flex-col md:flex-row justify-between items-center gap-4 pt-8 border-t border-edge-subtle">
            <span className="text-xs text-txt-muted">&copy; {new Date().getFullYear()} Foresight. All rights reserved.</span>
            <span className="text-xs text-txt-muted">Built for traders who want to understand before they act.</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

const STEPS = [
  {
    icon: Eye,
    title: "Ingest & match",
    desc: "50+ sources feed our pipeline — wire services, finance media, social — then we retrieve the Polymarket contracts that truly match the story, not just keyword overlap.",
  },
  {
    icon: Brain,
    title: "Deep analysis",
    desc: "Hybrid retrieval (vectors + BM25), LLM impact scoring, liquidity and spread checks. Every signal carries structured reasoning — why this contract, why now.",
  },
  {
    icon: TrendingUp,
    title: "Conviction you can use",
    desc: "Direction, score tiers, probability context, and time window — so you trade on analysis, not vibes. Alerts when it matters.",
  },
]

const FEATURES = [
  { icon: Radio, title: "Live signal feed", desc: "Event + contract pairs where information may not be fully priced — surfaced as soon as the pipeline validates the link." },
  { icon: BarChart3, title: "Explainable scores", desc: "Semantic fit, model impact, market quality — decomposed so you see why a signal exists, not just a single number." },
  { icon: Shield, title: "Verified track record", desc: "Signals tracked against outcomes: win rates, simulated P&L — evidence you can audit." },
  { icon: Zap, title: "Low-latency delivery", desc: "Fast path from headline to dashboard when timing matters — without skipping the analysis layer." },
  { icon: TrendingUp, title: "Performance analytics", desc: "Score distribution, category win rates, timelines — understand where your edge actually comes from." },
  { icon: Bell, title: "Multi-channel alerts", desc: "Push, Telegram, in-app — high-conviction moments find you wherever you work." },
]

const PLANS = [
  {
    name: "Free",
    price: 0,
    icon: Zap,
    color: "#8892A4",
    popular: false,
    cta: "Get started",
    features: [
      "5 signals per day",
      "Score & direction",
      "24h history",
      "Basic dashboard",
    ],
  },
  {
    name: "Pro",
    price: 29,
    icon: Crown,
    color: "#D4A017",
    popular: true,
    cta: "Upgrade to Pro",
    features: [
      "Unlimited signals",
      "Rich explanations",
      "Full history",
      "Telegram & push alerts",
      "Advanced performance view",
      "Priority support",
    ],
  },
  {
    name: "Trader",
    price: 99,
    icon: Building2,
    color: "#8B5CF6",
    popular: false,
    cta: "Talk to us",
    features: [
      "Everything in Pro",
      "Direct Polymarket execution",
      "Risk alerts",
      "Daily intelligence briefs",
      "API access (10k req/day)",
      "Dedicated Discord support",
    ],
  },
]
