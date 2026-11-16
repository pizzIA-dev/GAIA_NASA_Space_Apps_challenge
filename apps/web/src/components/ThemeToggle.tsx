"use client";
import { useT } from "@/lib/i18n";
import { useResolvedTheme, useThemeStore, type ThemeMode } from "@/lib/theme";

const OPTIONS: { mode: ThemeMode; es: string; en: string }[] = [
  { mode: "system", es: "Sistema", en: "System" },
  { mode: "light", es: "Claro", en: "Light" },
  { mode: "dark", es: "Oscuro", en: "Dark" },
];

export function ThemeToggle() {
  const t = useT();
  const mode = useThemeStore((s) => s.mode);
  const setMode = useThemeStore((s) => s.setMode);
  useResolvedTheme(); // sincroniza el modo guardado al montar
  return (
    <div className="seg theme" role="group" aria-label={t("Tema de color", "Colour theme")}>
      {OPTIONS.map((o) => (
        <button key={o.mode} type="button" aria-pressed={mode === o.mode} onClick={() => setMode(o.mode)}>{t(o.es, o.en)}</button>
      ))}
    </div>
  );
}
