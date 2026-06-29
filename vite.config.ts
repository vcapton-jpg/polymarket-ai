import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
// Tailwind v4 est branché ici via son plugin Vite officiel (pas de postcss.config).
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
