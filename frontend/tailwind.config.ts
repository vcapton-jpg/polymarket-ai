import type { Config } from "tailwindcss"
import animate from "tailwindcss-animate"

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1280px",
      },
    },
    extend: {
      colors: {
        // Base palette — obsidian terminal
        obsidian: {
          950: "#05050A",
          900: "#08080C",
          850: "#0B0B11",
          800: "#0F0F14",
          750: "#14141A",
          700: "#1A1A22",
          650: "#23232D",
          600: "#2F2F3A",
        },
        // Brand — mint cyan
        brand: {
          50: "#E8FFF9",
          100: "#C9FFF0",
          200: "#94FFE0",
          300: "#5DFFCE",
          400: "#2FF5BC",
          500: "#0BE0A6", // primary
          600: "#06B088",
          700: "#088269",
          800: "#0B5E4D",
          900: "#0A3F35",
        },
        // Signal directions / states
        signal: {
          yes: "#4ADE80",
          no: "#F87171",
          amber: "#FBBF24",
          alert: "#FB7185",
        },
        // Tier badges
        tier: {
          1: "#0BE0A6",
          2: "#60A5FA",
          3: "#A78BFA",
        },
        // Semantic
        ink: {
          DEFAULT: "#F5F6F8",
          muted: "#A1A3AC",
          dim: "#6B6E79",
          readable: "#8A8D99", // WCAG AA informational body text
          faint: "#4A4D57",
        },
        telegram: "#229ED9",
        polymarket: "#2D7CFE",
        "chart-yes": "#4ADE80", // align with signal-yes
        "chart-no": "#F87171", // align with signal-no
        "chart-amber": "#FBBF24", // align with signal-amber
        "chart-brand": "#0BE0A6", // align with brand-500
        "chart-sky": "#60A5FA",
        "chart-orange": "#F97316",
        "chart-purple": "#A855F7",
        line: {
          DEFAULT: "#1F1F28",
          strong: "#2A2A36",
          subtle: "#15151C",
        },
        // shadcn aliases
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        display: ['"Satoshi"', '"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "display-1": ["clamp(2.25rem, 6vw, 5rem)", { lineHeight: "1.05", letterSpacing: "-0.035em", fontWeight: "600" }],
        "display-2": ["clamp(2rem, 4vw, 3.5rem)", { lineHeight: "1.05", letterSpacing: "-0.03em", fontWeight: "600" }],
        "display-3": ["clamp(1.5rem, 2.5vw, 2.25rem)", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "600" }],
        eyebrow: ["0.6875rem", { lineHeight: "1", letterSpacing: "0.18em", fontWeight: "500" }],
        "label-xs": ["0.6875rem", { lineHeight: "1rem" }],
        "label-sm": ["0.75rem", { lineHeight: "1.125rem" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.375rem" }],
        "body-md": ["0.875rem", { lineHeight: "1.5rem" }],
        "body-lg": ["1.0625rem", { lineHeight: "1.75rem" }],
        "title-sm": ["1.125rem", { lineHeight: "1.5rem" }],
        "title-md": ["1.25rem", { lineHeight: "1.625rem" }],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        "brand-glow": "0 0 0 1px rgba(11, 224, 166, 0.25), 0 8px 32px -8px rgba(11, 224, 166, 0.35)",
        "inset-line": "inset 0 0 0 1px rgba(255, 255, 255, 0.04)",
        "elevated": "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 48px -12px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "grid-fade": "linear-gradient(180deg, rgba(11,224,166,0.08), transparent 60%)",
        "mesh-brand": "radial-gradient(60% 50% at 50% 0%, rgba(11,224,166,0.18), transparent 70%)",
        "mesh-cool": "radial-gradient(50% 50% at 20% 30%, rgba(96,165,250,0.12), transparent 70%), radial-gradient(40% 40% at 80% 20%, rgba(167,139,250,0.12), transparent 70%)",
        "noise": "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"200\" height=\"200\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.9\" numOctaves=\"2\" stitchTiles=\"stitch\"/><feColorMatrix values=\"0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.4 0\"/></filter><rect width=\"100%\" height=\"100%\" filter=\"url(%23n)\" opacity=\"0.9\"/></svg>')",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.6", transform: "scale(0.9)" },
        },
        "ticker-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        "scan": {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        "flash": {
          "0%": { backgroundColor: "rgba(11,224,166,0.15)" },
          "100%": { backgroundColor: "transparent" },
        },
        "shimmer": {
          "100%": { transform: "translateX(100%)" },
        },
        "marquee": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 360ms ease-out both",
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
        "ticker-pulse": "ticker-pulse 1.2s ease-in-out infinite",
        "scan": "scan 3.5s linear infinite",
        "flash": "flash 2s ease-out",
        "shimmer": "shimmer 1.6s ease-in-out infinite",
        "marquee": "marquee 50s linear infinite",
      },
    },
  },
  plugins: [animate],
}

export default config
