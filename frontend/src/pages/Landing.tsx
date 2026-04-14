import { useNavigate } from "react-router-dom"
import { motion, useScroll, useTransform } from "framer-motion"
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
  Star,
  Crown,
  Building2,
  ChevronRight,
  Bell,
} from "lucide-react"

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.55, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
  }),
}

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
}

export default function Landing() {
  const nav = useNavigate()
  const { scrollYProgress } = useScroll()
  const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.15], [1, 0.96])

  return (
    <div className="min-h-screen bg-surface-0 overflow-hidden">
      {/* ─── Navbar ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-surface-0/80 backdrop-blur-2xl" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="max-w-[1200px] mx-auto px-6 h-16 flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <Triangle size={20} strokeWidth={1.8} className="text-accent fill-accent/20" />
            <span className="text-lg font-bold tracking-tight text-txt-primary">Foresight</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#how" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">How it works</a>
            <a href="#features" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">Features</a>
            <a href="#pricing" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">Pricing</a>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => nav("/auth")} className="text-sm font-medium text-txt-muted hover:text-txt-primary transition-colors bg-transparent border-none cursor-pointer">
              Sign in
            </button>
            <button
              onClick={() => nav("/auth")}
              className="px-4 py-2 rounded-lg bg-accent text-surface-0 text-sm font-semibold hover:brightness-110 transition-all cursor-pointer border-none"
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
        {/* Glow */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-[800px] h-[800px] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.08)_0%,transparent_65%)]" />
          <div className="absolute bottom-[10%] left-[20%] w-[400px] h-[400px] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.04)_0%,transparent_70%)]" />
        </div>

        <div className="relative text-center max-w-[760px]">
          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={0}>
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent/8 border border-accent/15 text-accent text-xs font-semibold mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-live" />
              Research-grade analysis for prediction markets
            </span>
          </motion.div>

          <motion.h1
            initial="hidden" animate="visible" variants={fadeUp} custom={1}
            className="text-[2.75rem] md:text-[3.75rem] lg:text-[4.25rem] font-extrabold leading-[1.08] tracking-tight text-txt-primary mb-6"
          >
            Trade with
            <br />
            <span className="bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 bg-clip-text text-transparent">
              clarity and conviction
            </span>
          </motion.h1>

          <motion.p
            initial="hidden" animate="visible" variants={fadeUp} custom={2}
            className="text-lg md:text-xl text-txt-muted leading-relaxed mb-10 max-w-[580px] mx-auto"
          >
            Foresight links breaking news to the right Polymarket contracts using semantic retrieval, impact models, and market microstructure — then scores every opportunity with plain-English reasoning. Speed matters, but depth wins.
          </motion.p>

          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={3} className="flex gap-4 justify-center flex-wrap">
            <button
              onClick={() => nav("/auth")}
              className="group px-7 py-3.5 rounded-xl bg-accent text-surface-0 text-base font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-2 shadow-[0_0_24px_rgba(245,158,11,0.2)]"
            >
              Start free
              <ArrowRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
            <button
              onClick={() => {
                document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })
              }}
              className="px-7 py-3.5 rounded-xl bg-surface-card text-txt-secondary text-base font-semibold hover:text-accent transition-all cursor-pointer shadow-card"
              style={{ border: "1px solid rgba(255,255,255,0.08)" }}
            >
              See how it works
            </button>
          </motion.div>

          {/* Social proof */}
          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={4} className="mt-14 flex items-center justify-center gap-6 flex-wrap">
            <div className="flex items-center gap-1">
              {[1,2,3,4,5].map(i => <Star key={i} size={14} className="text-accent fill-accent" />)}
            </div>
            <span className="text-sm text-txt-muted">Trusted by <span className="text-txt-primary font-semibold">500+</span> active traders</span>
          </motion.div>
        </div>
      </motion.section>

      {/* ─── Signal Preview ─── */}
      <section className="py-20 px-6">
        <div className="max-w-[900px] mx-auto">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            custom={0}
            className="bg-surface-card rounded-2xl p-6 md:p-8 shadow-[0_4px_40px_rgba(0,0,0,0.4)] border border-edge-subtle"
          >
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse-live" />
              <span className="text-[11px] font-bold text-success uppercase tracking-widest">Live signal</span>
            </div>
            <div className="flex flex-col md:flex-row gap-6">
              <div className="flex-1">
                <p className="text-xs text-txt-muted mb-1 font-mono">Reuters · 3 min ago</p>
                <h3 className="text-lg font-bold text-txt-primary mb-3">Fed officials signal faster rate cuts after latest inflation data</h3>
                <p className="text-sm text-txt-secondary leading-relaxed">
                  Impact model: dovish shift underpriced vs. consensus. Contract mechanism aligns with policy path — not just headline correlation.
                </p>
              </div>
              <div className="flex flex-col gap-3 md:w-[220px] shrink-0">
                <div className="bg-surface-raised rounded-xl p-4 text-center">
                  <p className="text-[11px] text-txt-muted uppercase tracking-wider mb-1">Score</p>
                  <p className="text-3xl font-extrabold font-mono text-accent">91</p>
                  <p className="text-[10px] text-success font-semibold">High conviction</p>
                </div>
                <div className="bg-surface-raised rounded-xl p-4 text-center">
                  <p className="text-[11px] text-txt-muted uppercase tracking-wider mb-1">Market says</p>
                  <p className="text-2xl font-bold font-mono text-txt-primary">22% <span className="text-success text-sm">YES</span></p>
                </div>
                <div className="bg-success/10 rounded-xl p-3 text-center">
                  <p className="text-sm font-bold text-success">BUY YES</p>
                  <p className="text-[10px] text-txt-muted">Window: 2–4 weeks</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── How it works ─── */}
      <section id="how" className="py-24 px-6">
        <div className="max-w-[1100px] mx-auto">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0} className="text-center mb-16">
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">How it works</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary">From news to <span className="text-accent">actionable conviction</span></h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map((step, i) => (
              <motion.div
                key={step.title}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fadeUp}
                custom={i}
                className="relative"
              >
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center text-accent shrink-0">
                    <step.icon size={24} strokeWidth={1.5} />
                  </div>
                  <div className="w-8 h-8 rounded-full bg-surface-card flex items-center justify-center text-accent text-sm font-bold shadow-card">
                    {i + 1}
                  </div>
                </div>
                <h3 className="text-lg font-bold text-txt-primary mb-2">{step.title}</h3>
                <p className="text-sm text-txt-muted leading-relaxed">{step.desc}</p>
                {i < 2 && (
                  <ChevronRight size={20} className="hidden md:block absolute top-6 -right-4 text-edge" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="py-24 px-6 bg-surface-card/50">
        <div className="max-w-[1100px] mx-auto">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0} className="text-center mb-16">
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">Features</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary">Everything you need to <span className="text-accent">decide with confidence</span></h2>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={stagger}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
          >
            {FEATURES.map((f) => (
              <motion.div
                key={f.title}
                variants={fadeUp}
                custom={0}
                className="bg-surface-card rounded-xl p-6 border border-edge-subtle hover:border-edge-accent transition-all duration-300 group"
              >
                <div className="w-11 h-11 rounded-xl bg-accent/8 flex items-center justify-center text-accent mb-4 group-hover:bg-accent/15 transition-colors">
                  <f.icon size={22} strokeWidth={1.5} />
                </div>
                <h3 className="text-[15px] font-bold text-txt-primary mb-2">{f.title}</h3>
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
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">Pricing</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary mb-4">Start free, <span className="text-accent">upgrade when you are ready</span></h2>
            <p className="text-txt-muted max-w-lg mx-auto">Every plan includes live signals. Pro unlocks full history, richer explanations, and alerts.</p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-[960px] mx-auto">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fadeUp}
                custom={i}
                className={`relative bg-surface-card rounded-2xl p-7 border transition-all ${
                  plan.popular ? "border-accent/40 shadow-[0_0_30px_rgba(245,158,11,0.08)]" : "border-edge-subtle"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-accent text-surface-0 text-[11px] font-bold tracking-wider">
                    POPULAR
                  </div>
                )}
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${plan.color}15`, color: plan.color }}>
                    <plan.icon size={22} />
                  </div>
                  <h3 className="text-lg font-bold text-txt-primary">{plan.name}</h3>
                </div>
                <div className="mb-6">
                  <span className="text-4xl font-extrabold text-txt-primary font-mono">{plan.price === 0 ? "0" : plan.price}€</span>
                  {plan.price > 0 && <span className="text-sm text-txt-muted">/mois</span>}
                  {plan.price === 0 && <span className="text-sm text-txt-muted ml-1">pour toujours</span>}
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
                      ? "bg-accent text-surface-0 hover:brightness-110 shadow-[0_0_20px_rgba(245,158,11,0.15)]"
                      : "bg-surface-raised text-txt-secondary hover:text-accent hover:bg-surface-hover"
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
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0}
          className="max-w-[700px] mx-auto text-center"
        >
          <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center text-accent mx-auto mb-6">
            <Triangle size={32} strokeWidth={1.5} className="fill-accent/20" />
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary mb-4">
            Ready to see the full picture?
          </h2>
          <p className="text-lg text-txt-muted mb-10 max-w-md mx-auto leading-relaxed">
            Join traders who combine fast detection with structured analysis — so every signal is something you can actually understand and act on.
          </p>
          <button
            onClick={() => nav("/auth")}
            className="group px-8 py-4 rounded-xl bg-accent text-surface-0 text-lg font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-3 mx-auto shadow-[0_0_30px_rgba(245,158,11,0.2)]"
          >
            Create free account
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </motion.div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="py-8 px-6" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="max-w-[1200px] mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Triangle size={16} strokeWidth={1.8} className="text-accent fill-accent/20" />
            <span className="font-bold text-txt-primary">Foresight</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#pricing" className="text-xs text-txt-muted hover:text-txt-secondary transition-colors no-underline">Pricing</a>
            <a href="#features" className="text-xs text-txt-muted hover:text-txt-secondary transition-colors no-underline">Features</a>
            <span className="text-xs text-txt-muted">hello@getforesight.io</span>
          </div>
          <span className="text-xs text-txt-muted">&copy; {new Date().getFullYear()} Foresight. All rights reserved.</span>
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
    color: "#6B7280",
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
    color: "#F59E0B",
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
