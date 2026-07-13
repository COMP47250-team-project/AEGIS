// frontend/tailwind.config.js
// Tailwind CSS configuration.
// Tailwind scans the files listed in `content` and generates only the
// CSS classes that are actually used in those files — keeping the
// final CSS bundle small.

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    // Scan all JS/TS/JSX/TSX files inside src/ for Tailwind class names
  ],
  theme: {
    extend: {
      // DESIGN.md color tokens (PostHog design system applied to AEGIS).
      // Each token resolves to a CSS variable so light/dark can be swapped at
      // runtime (AEGIS-74) — see src/index.css. `<alpha-value>` keeps Tailwind
      // opacity utilities (e.g. bg-primary/15) working.
      colors: {
        // Surfaces
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        "surface-soft": "rgb(var(--surface-soft) / <alpha-value>)",
        "surface-card": "rgb(var(--surface-card) / <alpha-value>)",
        "surface-doc": "rgb(var(--surface-doc) / <alpha-value>)",
        "surface-dark": "rgb(var(--surface-dark) / <alpha-value>)",
        // Borders
        hairline: "rgb(var(--hairline) / <alpha-value>)",
        "hairline-soft": "rgb(var(--hairline-soft) / <alpha-value>)",
        // Brand
        primary: "rgb(var(--primary) / <alpha-value>)",
        "primary-pressed": "rgb(var(--primary-pressed) / <alpha-value>)",
        "primary-active": "rgb(var(--primary-active) / <alpha-value>)",
        // Text
        ink: "rgb(var(--ink) / <alpha-value>)",
        body: "rgb(var(--body) / <alpha-value>)",
        charcoal: "rgb(var(--charcoal) / <alpha-value>)",
        mute: "rgb(var(--mute) / <alpha-value>)",
        ash: "rgb(var(--ash) / <alpha-value>)",
        stone: "rgb(var(--stone) / <alpha-value>)",
        "on-dark": "rgb(var(--on-dark) / <alpha-value>)",
        // Links
        "link-blue": "rgb(var(--link-blue) / <alpha-value>)",
        "link-teal": "rgb(var(--link-teal) / <alpha-value>)",
        // Semantic accents
        "accent-blue": "rgb(var(--accent-blue) / <alpha-value>)",
        "accent-blue-soft": "rgb(var(--accent-blue-soft) / <alpha-value>)",
        "accent-red": "rgb(var(--accent-red) / <alpha-value>)",
        "accent-red-soft": "rgb(var(--accent-red-soft) / <alpha-value>)",
        "accent-green": "rgb(var(--accent-green) / <alpha-value>)",
        "accent-green-soft": "rgb(var(--accent-green-soft) / <alpha-value>)",
        "accent-purple": "rgb(var(--accent-purple) / <alpha-value>)",
        "accent-purple-soft": "rgb(var(--accent-purple-soft) / <alpha-value>)",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "-apple-system", "system-ui", "sans-serif"],
        mono: ["ui-monospace", '"Source Code Pro"', "monospace"],
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};
