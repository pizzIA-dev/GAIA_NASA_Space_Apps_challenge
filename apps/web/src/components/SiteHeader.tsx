"use client";
// Cabecera común: navegación, tema e idioma. Es cliente para que los textos cambien al elegir ES/EN.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { readStoredLang, useLangStore, useT, type Lang } from "@/lib/i18n";
import { ThemeToggle } from "./ThemeToggle";

// Panel = experiencia principal; el resto es opcional (Explorar = detalle de una variable, enlazado desde el panel).
const NAV: { href: string; es: string; en: string }[] = [
  { href: "/", es: "Panel", en: "Dashboard" },
  { href: "/estudio", es: "Análisis avanzado", en: "Advanced analysis" },
  { href: "/atlas", es: "Atlas", en: "Atlas" },
  { href: "/fuentes", es: "Fuentes", en: "Sources" },
  { href: "/metodos", es: "Métodos", en: "Methods" },
];
const TITLES: Record<string, [string, string]> = {
  "/explorar": ["Detalle de una variable", "Variable detail"],
  "/estudio": ["Análisis avanzado", "Advanced analysis"],
  "/atlas": ["Atlas", "Atlas"], "/fuentes": ["Fuentes", "Sources"], "/metodos": ["Métodos", "Methods"],
};

export function SiteHeader() {
  const t = useT();
  const lang = useLangStore((s) => s.lang);
  const setLang = useLangStore((s) => s.setLang);
  const pathname = usePathname();
  useEffect(() => { const s = readStoredLang(); if (s !== useLangStore.getState().lang) setLang(s); }, [setLang]);
  // El título de la pestaña lo fija Next.js en español (metadata) y puede reescribirlo tras la navegación: se vigila
  // el <head> y se ajusta al idioma elegido.
  useEffect(() => {
    const p = TITLES[pathname];
    const want = p ? `${lang === "en" ? p[1] : p[0]} · GaIA` : "GaIA";
    const apply = () => { if (document.title !== want) document.title = want; };
    apply();
    const mo = new MutationObserver(apply);
    mo.observe(document.head, { childList: true, subtree: true, characterData: true });
    return () => mo.disconnect();
  }, [pathname, lang]);
  return (
    <>
      <a className="skip" href="#contenido">{t("Saltar al contenido", "Skip to content")}</a>
      <header className="top">
        <Link href="/" className="brand">GaIA</Link>
        <nav className="primary" aria-label={t("Secciones", "Sections")}>
          {NAV.map((n) => <Link key={n.href} href={n.href}>{t(n.es, n.en)}</Link>)}
        </nav>
        <div className="top-tools">
          <div className="seg lang" role="group" aria-label={t("Idioma", "Language")}>
            {(["es", "en"] as Lang[]).map((l) => (
              <button key={l} type="button" lang={l} aria-pressed={lang === l} onClick={() => setLang(l)}>
                {l.toUpperCase()}<span className="sr-only"> ({l === "es" ? "Español" : "English"})</span>
              </button>
            ))}
          </div>
          <ThemeToggle />
        </div>
      </header>
    </>
  );
}
