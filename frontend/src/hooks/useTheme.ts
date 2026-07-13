// frontend/src/hooks/useTheme.ts — light/dark theme state (AEGIS-74)
import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "aegis-theme";

/** Current effective theme: explicit choice in localStorage, else light. */
function resolveTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage unavailable — fall through to the light default.
  }
  return "light";
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(resolveTheme);

  // Keep the DOM attribute in sync (covers the very first client render).
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Ignore persistence failures (e.g. private mode).
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
