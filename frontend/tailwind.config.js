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
    extend: {},
    // extend: allows adding custom colors, fonts, spacing etc. on top
    // of Tailwind's defaults. Empty for now.
  },
  plugins: [],
};
