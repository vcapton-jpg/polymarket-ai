/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#05080F",
          card: "#0B1120",
          raised: "#131C2E",
          hover: "#182338",
          glass: "rgba(255,255,255,0.03)",
        },
        edge: {
          DEFAULT: "rgba(255,255,255,0.08)",
          subtle: "rgba(255,255,255,0.04)",
          accent: "rgba(212,160,23,0.35)",
          glass: "rgba(255,255,255,0.04)",
          glow: "rgba(212,160,23,0.20)",
        },
        accent: {
          DEFAULT: "#D4A017",
          bright: "#F59E0B",
          muted: "rgba(212,160,23,0.12)",
          glow: "rgba(212,160,23,0.20)",
        },
        success: { DEFAULT: "#10B981", muted: "rgba(16,185,129,0.12)" },
        danger: { DEFAULT: "#EF4444", muted: "rgba(239,68,68,0.12)" },
        warning: "#F59E0B",
        info: "#3B82F6",
        txt: {
          primary: "#E8ECF4",
          secondary: "#8892A4",
          muted: "#505868",
        },
        cat: {
          geo: "#F87171",
          politics: "#818CF8",
          economics: "#34D399",
          crypto: "#FBBF24",
          sports: "#60A5FA",
          science: "#A78BFA",
          other: "#8892A4",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        display: ["Plus Jakarta Sans", "Inter", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      letterSpacing: {
        display: "-0.02em",
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        "2xl": "24px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)",
        "card-hover": "0 8px 24px rgba(0,0,0,0.6), 0 0 0 1px rgba(212,160,23,0.12)",
        glow: "0 0 24px rgba(212,160,23,0.10)",
        "glow-lg": "0 0 48px rgba(212,160,23,0.15)",
        glass: "0 4px 16px rgba(0,0,0,0.3)",
        "inner-glow": "inset 0 1px 0 rgba(255,255,255,0.04)",
      },
      animation: {
        "pulse-live": "pulse-live 2s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
        "shimmer-gold": "shimmer-gold 2s infinite",
        "score-fill": "score-fill 0.6s ease-out forwards",
        "slide-down": "slide-down 0.35s ease-out",
        "flash-border": "flash-border 2s ease-out",
        "badge-pulse": "badge-pulse 3s ease-in-out infinite",
        "gradient-rotate": "gradient-rotate 3s linear infinite",
        "fade-in-blur": "fade-in-blur 0.5s ease-out forwards",
        "scale-in": "scale-in 0.3s ease-out forwards",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
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
        "shimmer-gold": {
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
          "0%": { boxShadow: "0 0 0 2px rgba(16,185,129,0.6), 0 1px 3px rgba(0,0,0,0.5)" },
          "100%": { boxShadow: "0 1px 3px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)" },
        },
        "badge-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        "gradient-rotate": {
          "0%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
          "100%": { backgroundPosition: "0% 50%" },
        },
        "fade-in-blur": {
          from: { opacity: "0", filter: "blur(8px)", transform: "translateY(8px)" },
          to: { opacity: "1", filter: "blur(0)", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.95)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(212,160,23,0.10)" },
          "50%": { boxShadow: "0 0 32px rgba(212,160,23,0.20)" },
        },
      },
      backgroundImage: {
        "gradient-gold": "linear-gradient(135deg, #D4A017, #F59E0B, #D4A017)",
        "gradient-mesh": "radial-gradient(ellipse at 20% 50%, rgba(212,160,23,0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(59,130,246,0.04) 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, rgba(139,92,246,0.03) 0%, transparent 50%)",
      },
    },
  },
  plugins: [],
}
