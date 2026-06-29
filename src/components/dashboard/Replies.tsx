import { Sparkles, TrendingUp } from 'lucide-react'
import { TEMPLATES } from '../../demo/templates'
import { CATEGORY_META } from '../../demo/requests'
import { Reveal } from '../ui/Reveal'

/** Bibliothèque des réponses automatiques — modèles dans le ton de la marque. */
export function Replies() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 rounded-2xl border border-white/[0.06] bg-ink-900/40 p-4 text-sm text-mist">
        <Sparkles className="h-4 w-4 shrink-0 text-accent" />
        Modèles appris sur vos réponses passées et adaptés par catégorie — chaleureux, proches des
        familles. L’IA les personnalise (prénom, magazine, n° d’abonné) à chaque envoi.
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {TEMPLATES.map((t, i) => (
          <Reveal key={t.id} delay={i * 0.04}>
            <div className="flex h-full flex-col rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5 transition-colors hover:border-white/10">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold text-cloud">{t.title}</h3>
                <span
                  className="rounded-md px-2 py-0.5 text-[11px] font-medium"
                  style={{
                    color: CATEGORY_META[t.category].color,
                    backgroundColor: `color-mix(in srgb, ${CATEGORY_META[t.category].color} 12%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${CATEGORY_META[t.category].color} 25%, transparent)`,
                  }}
                >
                  {CATEGORY_META[t.category].label}
                </span>
              </div>
              <p className="mt-1 text-xs italic text-faint">Déclenché par : {t.trigger}</p>
              <p className="mt-3 flex-1 rounded-xl border border-white/[0.05] bg-ink-950/40 p-3.5 text-sm leading-relaxed text-mist">
                {t.body}
              </p>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-faint">
                <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                Utilisé <span className="font-mono text-mist">{t.uses}×</span> ce mois-ci
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  )
}
