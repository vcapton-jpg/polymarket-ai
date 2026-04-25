import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        /**
         * Vendor chunking strategy.
         *
         * Default Rollup behavior is "everything node_modules → one giant
         * vendor chunk", which means every page download tugs the full
         * dependency graph regardless of whether it's needed. We split
         * by domain so:
         *
         *   - `vendor-react`     — React + ReactDOM + Router. Loaded by
         *     every page, gets its own long-lived cache entry.
         *   - `vendor-query`     — TanStack Query. Loaded eagerly via
         *     main.tsx; isolated so a router upgrade doesn't bust this.
         *   - `vendor-motion`    — Framer Motion. Used by every page but
         *     splits cleanly because nothing else imports it.
         *   - `vendor-i18n`      — i18next + react-i18next. Lots of
         *     locale data; isolated so a string-only change rebuilds a
         *     small chunk.
         *   - `vendor-recharts`  — Recharts. Only loaded inside the
         *     PerformanceCharts lazy chunk; manualChunks groups all of
         *     its many sub-modules under one filename so the network
         *     waterfall is one request, not 80.
         *   - `vendor-wagmi`     — wagmi + viem. Only loaded inside the
         *     SignalDetail chunk via WalletScope; same reasoning as
         *     recharts.
         *
         * Anything else in node_modules falls through to Rollup's
         * default chunking — small enough to share with the importing
         * page chunk.
         */
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined
          if (id.includes("/react-dom/") || id.includes("/react/") || id.includes("/scheduler/")) {
            return "vendor-react"
          }
          if (id.includes("/react-router") || id.includes("/@remix-run/")) {
            return "vendor-react"
          }
          if (id.includes("/@tanstack/react-query")) {
            return "vendor-query"
          }
          if (id.includes("/framer-motion/") || id.includes("/motion-utils/") || id.includes("/motion-dom/")) {
            return "vendor-motion"
          }
          if (id.includes("/i18next") || id.includes("/react-i18next")) {
            return "vendor-i18n"
          }
          if (id.includes("/recharts/") || id.includes("/d3-") || id.includes("/victory-vendor/")) {
            return "vendor-recharts"
          }
          if (id.includes("/wagmi/") || id.includes("/viem/") || id.includes("/@wagmi/")) {
            return "vendor-wagmi"
          }
          return undefined
        },
      },
    },
  },
})
