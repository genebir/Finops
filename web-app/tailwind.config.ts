import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          warm: "#FAF7F2",
          "warm-subtle": "#F2EDE4",
          dark: "#1A1714",
          "dark-subtle": "#26221E",
        },
        text: {
          primary: "#1A1714",
          secondary: "#6B6560",
          tertiary: "#A89F94",
          inverse: "#FAF7F2",
        },
        border: {
          DEFAULT: "#E8E2D9",
          strong: "#D4CCC0",
        },
        status: {
          critical: "#C8553D",
          warning: "#E8A04A",
          healthy: "#7FB77E",
          under: "#6B8CAE",
        },
        provider: {
          aws: "#D97757",
          gcp: "#6B8CAE",
          azure: "#8B7FB8",
        },
      },
      borderRadius: {
        input: "10px",
        button: "12px",
        card: "20px",
        large: "28px",
        full: "9999px",
      },
      fontFamily: {
        display: ['"Montserrat"', "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 2px rgba(0,0,0,0.04)",
        hover: "0 4px 12px rgba(0,0,0,0.06)",
        float: "0 8px 24px rgba(0,0,0,0.08)",
      },
      fontSize: {
        metric: ["48px", { lineHeight: "1.0" }],
      },
    },
  },
  plugins: [],
} satisfies Config;
