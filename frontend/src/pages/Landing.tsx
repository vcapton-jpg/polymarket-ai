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
  Clock,
  Check,
  Star,
  Crown,
  Building2,
  ChevronRight,
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
            <span className="text-lg font-bold tracking-tight text-txt-primary">Presage</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#how" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">Comment ca marche</a>
            <a href="#features" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">Fonctionnalites</a>
            <a href="#pricing" className="text-sm text-txt-muted hover:text-txt-primary transition-colors no-underline">Tarifs</a>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => nav("/auth")} className="text-sm font-medium text-txt-muted hover:text-txt-primary transition-colors bg-transparent border-none cursor-pointer">
              Connexion
            </button>
            <button
              onClick={() => nav("/auth")}
              className="px-4 py-2 rounded-lg bg-accent text-surface-0 text-sm font-semibold hover:brightness-110 transition-all cursor-pointer border-none"
            >
              Commencer gratuitement
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
              Intelligence en temps reel sur les marches predictifs
            </span>
          </motion.div>

          <motion.h1
            initial="hidden" animate="visible" variants={fadeUp} custom={1}
            className="text-[2.75rem] md:text-[3.75rem] lg:text-[4.25rem] font-extrabold leading-[1.08] tracking-tight text-txt-primary mb-6"
          >
            Voyez les marches
            <br />
            <span className="bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 bg-clip-text text-transparent">
              avant qu'ils ne bougent
            </span>
          </motion.h1>

          <motion.p
            initial="hidden" animate="visible" variants={fadeUp} custom={2}
            className="text-lg md:text-xl text-txt-muted leading-relaxed mb-10 max-w-[580px] mx-auto"
          >
            Presage detecte les evenements qui font bouger Polymarket en moins de 60 secondes. Score de conviction, explication, probabilite — tout ce qu'il faut pour trader avec un avantage reel.
          </motion.p>

          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={3} className="flex gap-4 justify-center flex-wrap">
            <button
              onClick={() => nav("/auth")}
              className="group px-7 py-3.5 rounded-xl bg-accent text-surface-0 text-base font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-2 shadow-[0_0_24px_rgba(245,158,11,0.2)]"
            >
              Commencer gratuitement
              <ArrowRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
            <button
              onClick={() => {
                document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })
              }}
              className="px-7 py-3.5 rounded-xl bg-surface-card text-txt-secondary text-base font-semibold hover:text-accent transition-all cursor-pointer shadow-card"
              style={{ border: "1px solid rgba(255,255,255,0.08)" }}
            >
              Decouvrir comment
            </button>
          </motion.div>

          {/* Social proof */}
          <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={4} className="mt-14 flex items-center justify-center gap-6 flex-wrap">
            <div className="flex items-center gap-1">
              {[1,2,3,4,5].map(i => <Star key={i} size={14} className="text-accent fill-accent" />)}
            </div>
            <span className="text-sm text-txt-muted">Utilise par <span className="text-txt-primary font-semibold">500+</span> traders sur Polymarket</span>
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
              <span className="text-[11px] font-bold text-success uppercase tracking-widest">Signal en direct</span>
            </div>
            <div className="flex flex-col md:flex-row gap-6">
              <div className="flex-1">
                <p className="text-xs text-txt-muted mb-1 font-mono">Reuters &middot; il y a 3 min</p>
                <h3 className="text-lg font-bold text-txt-primary mb-3">La Fed signale une acceleration des baisses de taux apres les derniers chiffres d'inflation</h3>
                <p className="text-sm text-txt-secondary leading-relaxed">
                  "Les rapports de la Fed indiquent une position plus accommodante que prevu. Le marche ne reflete pas encore ce changement de politique."
                </p>
              </div>
              <div className="flex flex-col gap-3 md:w-[220px] shrink-0">
                <div className="bg-surface-raised rounded-xl p-4 text-center">
                  <p className="text-[11px] text-txt-muted uppercase tracking-wider mb-1">Score</p>
                  <p className="text-3xl font-extrabold font-mono text-accent">91</p>
                  <p className="text-[10px] text-success font-semibold">Conviction exceptionnelle</p>
                </div>
                <div className="bg-surface-raised rounded-xl p-4 text-center">
                  <p className="text-[11px] text-txt-muted uppercase tracking-wider mb-1">Le marche dit</p>
                  <p className="text-2xl font-bold font-mono text-txt-primary">22% <span className="text-success text-sm">YES</span></p>
                </div>
                <div className="bg-success/10 rounded-xl p-3 text-center">
                  <p className="text-sm font-bold text-success">BUY YES</p>
                  <p className="text-[10px] text-txt-muted">Fenetre: 2-4 semaines</p>
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
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">Comment ca marche</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary">De l'info brute a l'avantage en <span className="text-accent">60 secondes</span></h2>
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
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">Fonctionnalites</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary">Tout ce qu'il faut pour <span className="text-accent">gagner</span></h2>
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
            <span className="text-xs font-bold text-accent uppercase tracking-[0.2em] mb-3 block">Tarifs</span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-txt-primary mb-4">Commencez gratuitement, <span className="text-accent">evoluez quand vous etes pret</span></h2>
            <p className="text-txt-muted max-w-lg mx-auto">Tous les plans incluent les signaux en temps reel. Passez a Pro pour debloquer l'historique complet et les alertes.</p>
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
                    POPULAIRE
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
            Pret a voir avant les autres ?
          </h2>
          <p className="text-lg text-txt-muted mb-10 max-w-md mx-auto leading-relaxed">
            Rejoignez les traders qui recoivent des opportunites en temps reel, alimentees par l'IA, avant que le marche ne reagisse.
          </p>
          <button
            onClick={() => nav("/auth")}
            className="group px-8 py-4 rounded-xl bg-accent text-surface-0 text-lg font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center gap-3 mx-auto shadow-[0_0_30px_rgba(245,158,11,0.2)]"
          >
            Creer mon compte gratuit
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </motion.div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="py-8 px-6" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="max-w-[1200px] mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Triangle size={16} strokeWidth={1.8} className="text-accent fill-accent/20" />
            <span className="font-bold text-txt-primary">Presage</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#pricing" className="text-xs text-txt-muted hover:text-txt-secondary transition-colors no-underline">Tarifs</a>
            <a href="#features" className="text-xs text-txt-muted hover:text-txt-secondary transition-colors no-underline">Fonctionnalites</a>
            <span className="text-xs text-txt-muted">contact@presage.market</span>
          </div>
          <span className="text-xs text-txt-muted">&copy; {new Date().getFullYear()} Presage. Tous droits reserves.</span>
        </div>
      </footer>
    </div>
  )
}

const STEPS = [
  {
    icon: Eye,
    title: "Detection instantanee",
    desc: "Notre pipeline analyse 50+ sources d'information en temps reel — agences de presse, medias financiers, reseaux sociaux — pour capturer chaque evenement qui compte.",
  },
  {
    icon: Zap,
    title: "Scoring intelligent",
    desc: "Chaque evenement est croise avec les contrats Polymarket actifs. Similarite semantique, analyse LLM, microstructure du marche — tout est quantifie en un score de 0 a 100.",
  },
  {
    icon: TrendingUp,
    title: "Agir avec conviction",
    desc: "Recevez le signal avec l'explication complete : pourquoi l'evenement impacte le contrat, quelle fenetre d'action, et le niveau de confiance du modele.",
  },
]

const FEATURES = [
  { icon: Radio, title: "Signaux en temps reel", desc: "Chaque signal = un evenement + un contrat Polymarket ou le marche n'a pas encore integre l'information." },
  { icon: BarChart3, title: "Score explicable", desc: "Chaque score est decompose : pertinence semantique, impact LLM, liquidite, spread. Vous comprenez le pourquoi." },
  { icon: Shield, title: "Track record verifiable", desc: "Chaque signal est suivi contre les resultats reels. Taux de reussite, P&L simule — des preuves, pas des promesses." },
  { icon: Clock, title: "Latence < 60 secondes", desc: "De la publication d'une news au signal dans votre feed en moins d'une minute. L'avantage est dans la vitesse." },
  { icon: TrendingUp, title: "Dashboard performance", desc: "Distribution des scores, win rate par categorie, timeline cumulative — suivez votre edge en temps reel." },
  { icon: Zap, title: "Alertes multi-canal", desc: "Push notifications, Telegram, dashboard — ne ratez jamais un signal a haute conviction." },
]

const PLANS = [
  {
    name: "Gratuit",
    price: 0,
    icon: Zap,
    color: "#6B7280",
    popular: false,
    cta: "Commencer",
    features: [
      "5 signaux par jour",
      "Score et direction",
      "Dernieres 24h d'historique",
      "Dashboard basique",
    ],
  },
  {
    name: "Pro",
    price: 29,
    icon: Crown,
    color: "#F59E0B",
    popular: true,
    cta: "Passer a Pro",
    features: [
      "Signaux illimites",
      "Explications detaillees",
      "Historique complet",
      "Alertes Telegram & Push",
      "Dashboard performance avance",
      "Support prioritaire",
    ],
  },
  {
    name: "Trader",
    price: 99,
    icon: Building2,
    color: "#8B5CF6",
    popular: false,
    cta: "Contacter",
    features: [
      "Tout Pro inclus",
      "Execution directe Polymarket",
      "Alertes risk management",
      "Briefs intelligence quotidiens",
      "Acces API (10k req/jour)",
      "Support dedie Discord",
    ],
  },
]
