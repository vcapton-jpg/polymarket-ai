/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#080C16",
          card: "#111827",
          raised: "#1A2236",
          hover: "#1E293B",
        },
        edge: {
          DEFAULT: "rgba(255,255,255,0.10)",
          subtle: "rgba(255,255,255,0.06)",
          accent: "rgba(245,158,11,0.40)",
        },
        accent: {
          DEFAULT: "#F59E0B",
          muted: "rgba(245,158,11,0.14)",
          glow: "rgba(245,158,11,0.25)",
        },
        success: { DEFAULT: "#10B981", muted: "rgba(16,185,129,0.15)" },
        danger: { DEFAULT: "#EF4444", muted: "rgba(239,68,68,0.15)" },
        warning: "#F59E0B",
        info: "#3B82F6",
        txt: {
          primary: "#F1F5F9",
          secondary: "#94A3B8",
          muted: "#64748B",
        },
        cat: {
          geo: "#F87171",
          politics: "#818CF8",
          economics: "#34D399",
          crypto: "#FBBF24",
          sports: "#60A5FA",
          science: "#A78BFA",
          other: "#94A3B8",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.06)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.5), 0 0 0 1px rgba(245,158,11,0.15)",
        glow: "0 0 20px rgba(245,158,11,0.12)",
      },
      animation: {
        "pulse-live": "pulse-live 2s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
        "score-fill": "score-fill 0.6s ease-out forwards",
        "slide-down": "slide-down 0.35s ease-out",
        "flash-border": "flash-border 2s ease-out",
        "badge-pulse": "badge-pulse 3s ease-in-out infinite",
      },
      keyframes: {
        "pulse-live": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "score-fill": {
          from: { width: "0%" },
          to: { width: "var(--score-width)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "flash-border": {
          "0%": { boxShadow: "0 0 0 2px rgba(16,185,129,0.6), 0 1px 3px rgba(0,0,0,0.4)" },
          "100%": { boxShadow: "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.06)" },
        },
        "badge-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
      },
    },
  },
  plugins: [],
}
