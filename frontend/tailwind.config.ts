import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Syne", "Noto Serif SC", "serif"],
        body: ["'Noto Serif SC'", "serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        // Mapped 1:1 from the original CSS variables
        bg: {
          deep: "#0a0b0f",
          main: "#101117",
          surface: "#171822",
          elevated: "#1e2030",
          hover: "#252840",
        },
        accent: {
          DEFAULT: "#e4a853",
          dim: "#c48a3a",
          glow: "rgba(228,168,83,0.12)",
          glowS: "rgba(228,168,83,0.22)",
        },
        text: {
          1: "#eae6de",
          2: "#9e9a92",
          3: "#5c5953",
        },
        line: {
          DEFAULT: "#252738",
          l: "#2f3248",
        },
        ok: "#5ad4a6",
        bad: "#e85d6f",
        info: "#5b9df0",
        purple: "#a78bfa",
      },
      borderRadius: {
        DEFAULT: "10px",
        sm: "7px",
      },
      boxShadow: {
        accent: "0 2px 14px rgba(228,168,83,0.22)",
        accentLg: "0 4px 22px rgba(228,168,83,0.22)",
      },
    },
  },
  plugins: [],
} satisfies Config;
