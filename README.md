# Tempo

Landing one-page de **Tempo** — le co-pilote IA qui répond aux messages entrants
(email, chat, formulaires, DM), dans votre ton, et n'escalade à un humain que ce
qui compte. Pour les agences créatives et les marques DTC.

🌐 Production : https://givetempo.com

## Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** (via `@tailwindcss/vite`, design system dans `src/index.css`)
- **framer-motion** (animations), **lucide-react** (icônes), **simple-icons** (logos d'intégrations)

## Démarrer

```bash
npm install
npm run dev      # serveur de dev (http://localhost:5173)
npm run build    # build de production -> dist/
npm run preview  # prévisualiser le build
```

## Repères

- `src/config.ts` — **source unique** : nom de marque, accent, email, lien Calendly, navigation.
- `src/demo/handleMessage.ts` — ⚙️ **point de branchement API** : la fonction à remplacer
  pour passer la démo en réel (appel à l'API Anthropic). La signature ne change pas.
- `src/components/` — une section = un composant (Hero, Démo, ROI, FAQ, etc.).
- `src/components/ui/BrandMark.tsx` — le logo (barres de rythme).

## Déploiement

Hébergé sur **Vercel** (framework détecté : Vite · build `npm run build` · output `dist`).
DNS géré chez **Cloudflare** ; emails sur **Google Workspace** (`@givetempo.com`).
