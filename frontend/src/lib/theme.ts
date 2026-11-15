import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "govlens.theme";

function initial(): Theme {
  try { const saved = localStorage.getItem(KEY); if (saved === "light" || saved === "dark") return saved; } catch { /* blocked */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(KEY, theme); } catch { /* blocked */ }
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}
