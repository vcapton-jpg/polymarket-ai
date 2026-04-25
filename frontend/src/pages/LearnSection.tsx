import { useEffect } from "react"
import { Link, useParams } from "react-router-dom"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { ArrowLeft, ArrowRight, ChevronLeft, Clock } from "lucide-react"
import { AppShell } from "@/components/layout/AppShell"
import { Button } from "@/components/ui/Button"
import { LearnContent } from "@/components/learn/LearnContent"
import { LEARN_CONTENT } from "@/components/learn/sections"
import {
  LEARN_SECTIONS,
  findLearnSection,
  findLearnSectionIndex,
  getChapter,
  markLearnSectionRead,
} from "@/data/learn"
import { useProfile } from "@/lib/useProfile"
import { cn } from "@/lib/utils"

export default function LearnSection() {
  const { slug } = useParams<{ slug: string }>()
  const profile = useProfile()

  const section = slug ? findLearnSection(slug) : undefined
  const content = slug ? LEARN_CONTENT[slug] : undefined

  // Mark as read on mount. We do this eagerly (not on scroll-to-bottom) so
  // even quick skims show up in the progress dashboard — the point of the
  // counter is "did you visit it", not "did you complete a reading test".
  useEffect(() => {
    if (slug && section && content) {
      markLearnSectionRead(slug)
    }
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "auto" })
    }
  }, [slug, section, content])

  if (!slug || !section || !content) {
    return (
      <AppShell breadcrumb={[{ label: "Apprendre", to: "/apprendre" }, { label: "Introuvable" }]}>
        <div className="text-center py-20">
          <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">404</p>
          <h1 className="font-display text-[1.5rem] font-semibold text-ink">
            Cette section est en construction
          </h1>
          <p className="mt-2 text-ink-muted">
            Reviens bientôt — ou explore les autres sections.
          </p>
          <Link to="/apprendre" className="mt-5 inline-block">
            <Button>Retour à l’index</Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  const index = findLearnSectionIndex(slug)
  const prev = index > 0 ? LEARN_SECTIONS[index - 1] : null
  const next = index < LEARN_SECTIONS.length - 1 ? LEARN_SECTIONS[index + 1] : null

  const chapter = getChapter(section.chapter)
  const Icon = section.icon

  return (
    <AppShell
      breadcrumb={[
        { label: "Apprendre", to: "/apprendre" },
        { label: section.title },
      ]}
    >
      <article className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-10">
        {/* Back link (mobile + desktop) */}
        <Link
          to="/apprendre"
          className="mb-5 inline-flex items-center gap-1.5 text-body-sm text-ink-muted transition-premium hover:text-ink"
        >
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
          Retour à l'index
        </Link>

        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
          className="mb-6 border-b border-line/60 pb-5"
        >
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-full font-mono text-label-xs font-semibold ring-1",
                section.accentClass,
              )}
            >
              {String(section.number).padStart(2, "0")}
            </span>
            <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
              Section {section.number} sur {LEARN_SECTIONS.length}
            </span>
            <span className="text-ink-dim" aria-hidden>·</span>
            <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
              {chapter.label}
            </span>
          </div>
          <h1 className="font-display text-[1.625rem] font-semibold leading-tight tracking-tight text-ink md:text-[2rem]">
            {section.title}
          </h1>
          <div className="mt-2 flex items-center gap-4 text-body-sm text-ink-muted">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden />
              {section.readingTimeMinutes} min de lecture
            </span>
            <span className="inline-flex items-center gap-1">
              <Icon className="h-3.5 w-3.5" aria-hidden />
              {section.tagline}
            </span>
          </div>
        </motion.header>

        {/* Content */}
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.default, delay: 0.05, ease: EASE_PREMIUM }}
          className="space-y-5"
        >
          <LearnContent level={profile.type} content={content} />
        </motion.div>

        {/* Prev / Next nav */}
        <nav
          aria-label="Navigation entre sections"
          className="mt-10 grid gap-3 border-t border-line/60 pt-6 sm:grid-cols-2"
        >
          {prev ? (
            <Link
              to={`/apprendre/${prev.slug}`}
              className="group flex items-center gap-3 rounded-xl border border-line-strong bg-obsidian-850/60 px-4 py-3 transition-premium hover:border-brand-500/40 hover:bg-obsidian-800/60"
            >
              <ArrowLeft className="h-4 w-4 text-ink-muted transition-premium group-hover:text-brand-300" />
              <div className="min-w-0 flex-1">
                <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                  Précédent · {String(prev.number).padStart(2, "0")}
                </p>
                <p className="truncate text-body-md font-medium text-ink">
                  {prev.title}
                </p>
              </div>
            </Link>
          ) : (
            <div className="hidden sm:block" aria-hidden />
          )}
          {next ? (
            <Link
              to={`/apprendre/${next.slug}`}
              className="group flex items-center gap-3 rounded-xl border border-line-strong bg-obsidian-850/60 px-4 py-3 text-right transition-premium hover:border-brand-500/40 hover:bg-obsidian-800/60 sm:justify-end"
            >
              <div className="min-w-0 flex-1 text-right">
                <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                  Suivant · {String(next.number).padStart(2, "0")}
                </p>
                <p className="truncate text-body-md font-medium text-ink">
                  {next.title}
                </p>
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted transition-premium group-hover:text-brand-300" />
            </Link>
          ) : (
            <Link
              to="/signals"
              className="group flex items-center gap-3 rounded-xl border border-brand-500/40 bg-brand-500/10 px-4 py-3 text-right transition-premium hover:border-brand-500/60 hover:bg-brand-500/15 sm:justify-end"
            >
              <div className="min-w-0 flex-1 text-right">
                <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
                  Tu sais l'essentiel
                </p>
                <p className="truncate text-body-md font-semibold text-ink">
                  Voir les signaux en direct
                </p>
              </div>
              <ArrowRight className="h-4 w-4 text-brand-300" />
            </Link>
          )}
        </nav>
      </article>
    </AppShell>
  )
}
