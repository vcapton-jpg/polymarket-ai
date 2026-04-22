# Guide de voix Foresight

_La référence copy pour toutes les surfaces du produit. Écrite pour durer._

---

## 3 principes

1. **Court.** Si une phrase peut perdre trois mots, elle les perd. Un bénéfice par ligne.
2. **Concret.** Chaque ligne doit contenir un chiffre, un nom propre, un délai, une action. Zéro filler.
3. **Opinionated.** On tranche, on ne liste pas. Le ton est direct, jamais promotionnel.

---

## We say / We don't say

| ✅ On dit | ❌ On ne dit pas |
|---|---|
| « Le pipeline tourne. » | « Notre algorithme est actif 24/7. » |
| « Tu n'as pas 61 247 onglets. » | « Gagnez du temps avec notre surveillance automatisée. » |
| « Parier sur ce marché. » | « Investir maintenant. » |
| « Tes chiffres. Sans filtre. » | « Tes chiffres, en toute transparence. » |
| « Tes positions, là où elles en sont. » | « Tes positions, en un coup d'œil. » |
| « On commence. » | « Bienvenue dans Foresight ! » |
| « 68 s de la news à ta position. » | « Ultra-rapide, en temps réel. » |

---

## Règles de typographie française

- **Apostrophe courbe `’` toujours.** Jamais la droite `'`. Exemples : `l’info`, `d’un`, `c’est`, `aujourd’hui`.
- **Espace insécable `\u00A0` avant `: ? ! ;`.** Jamais d’espace simple. Utilise `NBSP` de `lib/typography.ts`.
- **Espace insécable entre nombre et unité.** `68 s`, `29 €`, `2 h`, `61 247 marchés`. Utilise `formatFRUnit()`.
- **Guillemets français `« »` avec NBSP interne.** `« vendre »`, pas `"vendre"`. Utilise `guillemets()`.
- **Tiret em `—` pour les incises.** `Foresight détecte les signaux — avant que le marché les intègre.`
- **Tiret demi-cadratin `–` pour les fourchettes.** `50–200 €`, pas `50-200€`. Utilise `formatFRRange()`.
- **Espace fine `\u202F` en séparateur de milliers.** `formatFR(61247)` → `« 61 247 »`.

Tous ces helpers vivent dans `frontend/src/lib/typography.ts`. Importe depuis là, ne hardcode jamais.

---

## Anglicismes — liste de décision

### À garder (trading-native ou brand)
- **Dashboard** · **Live** · **Sizing** · **Edge** · **Watchlist** · **Stack** · **Ticket** · **Builder code** · **Telegram**
- **« Pricing »** uniquement comme eyebrow court, jamais comme H1 ou label de nav.

### À remplacer
| Anglicisme | Remplacement |
|---|---|
| Upgrade / Upgrader | Passer Pro / Passer au plan X |
| Digest | Résumé email / Récapitulatif |
| CB | Carte / Carte bancaire |
| Pricing (H1, nav) | Tarifs |
| Live feed (eyebrow) | En direct |
| Investir (CTA) | Parier sur ce marché |

---

## Conventions CTA

- **Verbe d’abord.** « Parier sur ce marché », « Voir le signal », « Créer mon compte ».
- **Jamais de CTA générique.** Pas de « Cliquer ici », pas de « En savoir plus », pas de « Détails ».
- **Le CTA dit ce qui se passe au clic.** Si je clique « Passer Pro », je m’attends à voir la page plan. Si je clique « Parler à l’équipe API », je m’attends à une mise en relation.
- **Le CTA principal est unique par surface.** Un seul bouton `variant="primary"` par zone visible.

---

## Règles partenariat Polymarket

Foresight est partenaire **Polymarket Builder Program**. Les ordres s’exécutent **sur notre site** via le client CLOB — l’utilisateur ne quitte pas Foresight pour parier sur ce marché.

### À dire
- **CTA d’action :** « Parier sur ce marché ». C’est une action sur Foresight.
- **CTA d’évasion :** « Voir le marché sur Polymarket ». C’est un lien externe assumé.
- **Badge partenariat :** « Partenaire Polymarket » (discret, haut gauche de SignalDetail + footer).
- **Attribution légale :** « Exécution via notre partenariat Polymarket Builder Program » (petit texte sous OrderForm).

### À ne pas dire
- Jamais « Investir sur Polymarket » (risque AMF + factuellement faux, l’utilisateur reste sur Foresight).
- Jamais « Redirection vers Polymarket » (sauf pour le CTA externe).
- Ne pas marteler la marque Polymarket en H1 / hero — le partenariat doit être visible, pas intrusif.
