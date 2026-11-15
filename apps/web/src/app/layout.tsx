import type { Metadata } from "next";
import { Source_Sans_3, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "../styles/tokens.css";
import "./globals.css";
import { Providers } from "./providers";
import { ThemeToggle } from "@/components/ThemeToggle";
import { THEME_BOOT } from "@/lib/theme-boot";

const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-serif", display: "swap" });
const sans = Source_Sans_3({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Earth Trend Studio",
  description: "Un laboratorio visual para investigar cómo cambia la Tierra con datos NASA.",
};

const NAV = [
  { href: "/explorar", label: "Explorar" },
  { href: "/estudio", label: "Estudio" },
  { href: "/atlas", label: "Atlas" },
  { href: "/historias", label: "Historias" },
  { href: "/fuentes", label: "Fuentes" },
  { href: "/metodos", label: "Métodos" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${serif.variable} ${sans.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <a className="skip" href="#contenido">Saltar al contenido</a>
        <header className="top">
          <Link href="/explorar" className="brand">Earth Trend Studio<small>nombre provisional</small></Link>
          <nav className="primary" aria-label="Secciones">
            {NAV.map((n) => <Link key={n.href} href={n.href}>{n.label}</Link>)}
          </nav>
          <ThemeToggle />
        </header>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
