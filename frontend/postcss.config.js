// frontend/postcss.config.js
// PostCSS processes your CSS. Tailwind CSS runs as a PostCSS plugin.
// This file tells PostCSS to run Tailwind and Autoprefixer.
// Autoprefixer adds vendor prefixes (like -webkit-) automatically.

export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
