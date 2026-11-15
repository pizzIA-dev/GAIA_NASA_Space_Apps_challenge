"use client";
// Tema claro/oscuro: "system" sigue al sistema operativo. Se aplica como data-theme en <html> (tokens.css).
import { useEffect, useState } from "react";
import { create } from "zustand";

export type ThemeMode = "system" | "light" | "dark";
import { THEME_KEY } from "./theme-boot";

function readStored(): ThemeMode {
  try {
    const t = localStorage.getItem(THEME_KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch { return "system"; }
}

interface ThemeStore { mode: ThemeMode; setMode: (m: ThemeMode) => void }

export const useThemeStore = create<ThemeStore>((set) => ({
  mode: "system",
  setMode: (mode) => {
    try { if (mode === "system") localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, mode); } catch { /* sin almacenamiento */ }
    if (mode === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    set({ mode });
  },
}));

/** Tema efectivo ("light" | "dark"), para que gráficos y mapa se redibujen al cambiar. */
export function useResolvedTheme(): "light" | "dark" {
  const mode = useThemeStore((s) => s.mode);
  const [sys, setSys] = useState<"light" | "dark">("light");
  useEffect(() => {
    useThemeStore.setState({ mode: readStored() });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSys(mq.matches ? "dark" : "light");
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return mode === "system" ? sys : mode;
}
