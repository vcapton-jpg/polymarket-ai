import { useEffect, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

/** Vitesse de frappe (caractères / seconde). */
export const TYPE_CPS = 68

/** Durée approximative pour taper `text` (sert à synchroniser l'orchestrateur). */
export const typingMs = (text: string) => (text.length / TYPE_CPS) * 1000 + 500

/**
 * Effet « machine à écrire » : révèle `text` progressivement quand `active` est vrai.
 * Respecte prefers-reduced-motion (affiche tout d'un coup).
 */
export function useTypewriter(text: string, active: boolean) {
  const [out, setOut] = useState('')
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!active) {
      setOut('')
      return
    }
    if (reduce) {
      setOut(text)
      return
    }
    setOut('')
    let i = 0
    const id = setInterval(() => {
      i += 1
      setOut(text.slice(0, i))
      if (i >= text.length) clearInterval(id)
    }, 1000 / TYPE_CPS)
    return () => clearInterval(id)
  }, [text, active, reduce])

  return out
}
