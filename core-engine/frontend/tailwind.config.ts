// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Config } from "tailwindcss";

const withOpacity = (varName: string) => `rgb(var(${varName}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: withOpacity("--paper-rgb"),
          raised: withOpacity("--paper-raised-rgb"),
          subtle: withOpacity("--paper-subtle-rgb"),
          white: withOpacity("--paper-white-rgb"),
        },
        ink: {
          DEFAULT: withOpacity("--ink-rgb"),
          soft: withOpacity("--ink-soft-rgb"),
        },
        muted: withOpacity("--muted-rgb"),
        dim: withOpacity("--dim-rgb"),
        ghost: withOpacity("--ghost-rgb"),
        accent: {
          DEFAULT: withOpacity("--accent-rgb"),
          hover: withOpacity("--accent-hover-rgb"),
          solid: withOpacity("--accent-solid-rgb"),
          soft: "var(--accent-soft)",
          glow: "var(--accent-glow)",
        },
        line: {
          DEFAULT: withOpacity("--line-rgb"),
          hi: withOpacity("--line-hi-rgb"),
          focus: "var(--line-focus)",
        },
        plate: {
          DEFAULT: "var(--plate)",
          soft: "var(--plate-soft)",
          border: "var(--plate-border)",
        },
        // Semantic
        semantic: {
          cyan: withOpacity("--cyan-rgb"),
          emerald: withOpacity("--emerald-rgb"),
          amber: withOpacity("--amber-rgb"),
          rose: withOpacity("--rose-rgb"),
          violet: withOpacity("--violet-rgb"),
        },
        // Legacy & semantic color aliases (with alpha modifier support for /10, /20, /50...)
        primary: {
          DEFAULT: withOpacity("--accent-rgb"),
          hover: withOpacity("--accent-hover-rgb"),
          dark: withOpacity("--accent-hover-rgb"),
          light: "var(--accent-soft)",
          soft: "var(--accent-soft)",
          glow: "var(--accent-glow)",
          50: "var(--accent-soft)",
          100: "var(--accent-soft)",
          500: withOpacity("--accent-rgb"),
          600: withOpacity("--accent-hover-rgb"),
          700: withOpacity("--accent-hover-rgb"),
        },
        "brand-primary": withOpacity("--accent-rgb"),
        "bg-base": withOpacity("--paper-rgb"),
        "bg-surface": withOpacity("--paper-raised-rgb"),
        "bg-hover": withOpacity("--hover-rgb"),
        "text-primary": withOpacity("--ink-rgb"),
        "text-secondary": withOpacity("--muted-rgb"),
        "text-muted": withOpacity("--dim-rgb"),
        "text-disabled": withOpacity("--dim-rgb"),
        border: withOpacity("--line-rgb"),
        error: {
          DEFAULT: withOpacity("--rose-rgb"),
          light: "var(--rose-fill)",
        },
        danger: {
          DEFAULT: withOpacity("--rose-rgb"),
          light: "var(--rose-fill)",
        },
        warning: {
          DEFAULT: withOpacity("--amber-rgb"),
          light: "var(--amber-fill)",
        },
        success: {
          DEFAULT: withOpacity("--emerald-rgb"),
          light: "var(--emerald-fill)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "-apple-system", "sans-serif"],
        heading: ["var(--font-jakarta)", "Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        hero: ["clamp(2.25rem, 4.2vw, 3.25rem)", { lineHeight: "1.12", letterSpacing: "-0.028em" }],
        meta: ["0.75rem", { lineHeight: "1.35", letterSpacing: "0.02em" }],
      },
      maxWidth: {
        container: "var(--container-max)",
      },
      gap: {
        bento: "var(--bento-gap)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        elevated: "var(--shadow-elevated)",
        modal: "var(--shadow-modal)",
      },
      borderRadius: {
        card: "12px",
      },
      animation: {
        "fade-in": "fade-in 0.25s cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-up": "slide-up 0.3s cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-down": "slide-down 0.2s cubic-bezier(0.22, 1, 0.36, 1) both",
        "scale-in": "scale-in 0.16s cubic-bezier(0.22, 1, 0.36, 1) both",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
