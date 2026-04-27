import { motion } from "framer-motion"
import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { PublicNav } from "@/components/layout/PublicNav"
import { Footer } from "@/components/layout/Footer"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { cn } from "@/lib/utils"

const FAQ_ITEMS = [
  {
    q: "C’est quoi Foresight ?",
    a: "Foresight est un outil qui surveille l’actualité en temps réel et génère des signaux de trading sur Polymarket. En moins de 90 secondes après une news, tu reçois une recommandation claire : quoi acheter, avec quel score de conviction, et pourquoi.",
  },
  {
    q: "C’est quoi Polymarket ?",
    a: "Polymarket est un marché de prédiction décentralisé où tu paries sur l’issue d’événements réels : élections, conflits, crypto, sport, science. Si tu as raison, ton pari vaut 1 $. Foresight t’aide à identifier les marchés mal valorisés avant que le prix s’ajuste.",
  },
  {
    q: "Comment Foresight détecte-t-il les signaux ?",
    a: "Notre pipeline surveille 50+ sources Tier-1 (Reuters, AP, Bloomberg…) 24h/24. Dès qu’une news éclate, un moteur de recherche hybride la croise avec tous les marchés Polymarket ouverts. Un LLM calcule ensuite le score de conviction, la direction (BUY YES / BUY NO) et l’urgence.",
  },
  {
    q: "Qu’est-ce que le score de conviction ?",
    a: "C’est une note de 0 à 100 qui reflète la force du signal. Un score de 80+ indique un fort décalage entre la news et le prix du marché. En dessous de 50, le signal est trop incertain pour agir. Nous recommandons de ne trader qu’au-dessus de 60.",
  },
  {
    q: "Quelle est la différence entre Free et Pro ?",
    a: "Le plan Free donne accès à 5 signaux par jour avec un délai de 15 minutes. Le plan Pro donne accès à tous les signaux en temps réel (< 90 s), avec les explications complètes, les alertes Telegram, et l’historique complet des signaux passés.",
  },
  {
    q: "Les signaux sont-ils garantis gagnants ?",
    a: "Non. Foresight identifie des opportunités statistiquement intéressantes, pas des certitudes. Notre backtest montre un taux de réussite directionnel d’environ 68%, mais chaque trade comporte un risque. Ne mise jamais plus que tu n’es prêt à perdre.",
  },
  {
    q: "Comment fonctionne l’alerte Telegram ?",
    a: "Avec le plan Pro, tu reçois chaque signal directement dans ton Telegram dès qu’il est généré. Le message contient : la question du marché, le score, la direction, la fenêtre d’action estimée, et les sources. Tu n’as plus besoin d’ouvrir le dashboard.",
  },
  {
    q: "Faut-il un compte Polymarket pour utiliser Foresight ?",
    a: "Pour consulter les signaux, non. Pour agir dessus, oui — tu dois avoir un compte Polymarket et des fonds pour placer tes paris. Foresight ne passe pas d’ordres à ta place : c’est toi qui décides.",
  },
  {
    q: "Est-ce légal dans mon pays ?",
    a: "Polymarket est accessible dans la plupart des pays, mais certaines juridictions (notamment les États-Unis) imposent des restrictions. Vérifie les conditions d’utilisation de Polymarket selon ta localisation. Foresight lui-même est un outil d’analyse accessible mondialement.",
  },
  {
    q: "Comment annuler mon abonnement Pro ?",
    a: "Tu peux annuler à tout moment depuis les paramètres de ton compte, en un clic. Ton accès Pro reste actif jusqu’à la fin de la période déjà payée. Aucune question posée, aucuns frais d’annulation.",
  },
]

export default function Faq() {
  return (
    <>
      <PublicNav />
      <main id="main" className="relative pt-32 pb-24 md:pt-40 md:pb-32">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(50% 40% at 50% 0%, rgba(11,224,166,0.08), transparent 60%)",
          }}
          aria-hidden
        />

        <div className="container-page relative max-w-[760px]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
            className="mb-14 text-center"
          >
            <p className="mb-3 font-mono text-eyebrow uppercase text-brand-400">FAQ</p>
            <h1 className="text-display-2 text-ink text-balance">
              Questions fréquentes
            </h1>
            <p className="mt-4 text-body-lg text-ink-muted">
              Tout ce que tu dois savoir avant de commencer.
            </p>
          </motion.div>

          <div className="space-y-2">
            {FAQ_ITEMS.map((item, i) => (
              <FaqItem key={i} index={i} q={item.q} a={item.a} />
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}

function FaqItem({ q, a, index }: { q: string; a: string; index: number }) {
  const [open, setOpen] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.expressive, delay: index * 0.04, ease: EASE_PREMIUM }}
      className="rounded-xl border border-line-strong bg-obsidian-850/60 overflow-hidden"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left cursor-pointer hover:bg-obsidian-800/40 transition-premium"
      >
        <span className="font-display text-[1rem] md:text-[1.0625rem] font-semibold text-ink leading-snug">
          {q}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-ink-muted transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      <motion.div
        initial={false}
        animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
        transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
        className="overflow-hidden"
      >
        <p className="px-6 pb-5 text-body-md leading-relaxed text-ink-readable">
          {a}
        </p>
      </motion.div>
    </motion.div>
  )
}
