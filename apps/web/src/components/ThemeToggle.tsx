"use client";
import { useResolvedTheme, useThemeStore, type ThemeMode } from "@/lib/theme";

const OPTIONS: { mode: ThemeMode; label: string }[] = [
  { mode: "system", label: "Sistema" },
  { mode: "light", label: "Claro" },
  { mode: "dark", label: "Oscuro" },
];

export function ThemeToggle() {
  const mode = useThemeStore((s) => s.mode);
  const setMode = useThemeStore((s) => s.setMode);
  useResolvedTheme(); // sincroniza el modo guardado al montar
  return (
    <div className="seg theme" role="group" aria-label="Tema de color">
      {OPTIONS.map((o) => (
        <button key={o.mode} type="button" aria-pressed={mode === o.mode} onClick={() => setMode(o.mode)}>{o.label}</button>
      ))}
    </div>
  );
}
