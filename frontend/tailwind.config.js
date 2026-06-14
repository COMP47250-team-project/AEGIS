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
      // DESIGN.md color tokens (PostHog design system applied to AEGIS)
      colors: {
        // Surfaces
        canvas: "#eeefe9",
        "surface-soft": "#e5e7e0",
        "surface-card": "#ffffff",
        "surface-doc": "#fcfcfa",
        "surface-dark": "#23251d",
        // Borders
        hairline: "#bfc1b7",
        "hairline-soft": "#dcdfd2",
        // Brand
        primary: "#f7a501",
        "primary-pressed": "#dd9001",
        "primary-active": "#b17816",
        // Text
        ink: "#23251d",
        body: "#4d4f46",
        charcoal: "#33342d",
        mute: "#6c6e63",
        ash: "#9b9c92",
        stone: "#b6b7af",
        "on-dark": "#ffffff",
        // Links
        "link-blue": "#1d4ed8",
        "link-teal": "#1078a3",
        // Semantic accents
        "accent-blue": "#2c84e0",
        "accent-blue-soft": "#dceaf6",
        "accent-red": "#cd4239",
        "accent-red-soft": "#f7d6d3",
        "accent-green": "#2c8c66",
        "accent-green-soft": "#d9eddf",
        "accent-purple": "#7c44a6",
        "accent-purple-soft": "#e7d8ee",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "-apple-system", "system-ui", "sans-serif"],
        mono: ["ui-monospace", '"Source Code Pro"', "monospace"],
      },
    },
  },
  plugins: [],
};
