// frontend/vite.config.ts
// Vite is the build tool and development server.
// This config file tells Vite to use the React plugin (which enables
// JSX transformation and React Fast Refresh — instant hot reloading
// when you save a file during development).

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The dev server will run on http://localhost:5173
  },
});
