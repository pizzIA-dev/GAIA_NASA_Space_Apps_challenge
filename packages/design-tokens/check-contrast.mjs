// Contraste WCAG 2.1 de los pares texto/fondo de los tokens (claro y oscuro). Sale con código 1 si alguno falla.
// Uso: node packages/design-tokens/check-contrast.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const t = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "tokens.json"), "utf8"));

const lum = (hex) => {
  const n = parseInt(hex.replace("#", ""), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// [primer plano, fondo, mínimo, uso]
const PAIRS = [
  ["ink", "bg", 4.5, "texto principal sobre fondo"],
  ["ink", "paper", 4.5, "texto principal sobre panel"],
  ["muted", "paper", 4.5, "texto secundario sobre panel"],
  ["muted", "bg", 4.5, "texto secundario sobre fondo"],
  ["muted", "paper-2", 4.5, "texto secundario sobre controles"],
  ["accent", "paper", 4.5, "enlaces y acento sobre panel"],
  ["accent-ink", "accent", 4.5, "texto sobre botón activo"],
  ["div-dry", "paper", 4.5, "etiqueta «disminución» (texto 14 px seminegrita)"],
  ["div-wet", "paper", 4.5, "etiqueta «aumento» (texto 14 px seminegrita)"],
  ["danger", "paper", 4.5, "mensajes de error"],
  ["focus", "bg", 3.0, "anillo de foco (componente no textual)"],
  ["trend", "paper", 3.0, "línea de tendencia (gráfico)"],
  ["series", "paper", 3.0, "línea de la serie (gráfico)"],
  ["cat-1", "paper", 3.0, "territorio 1 en comparaciones (línea)"],
  ["cat-2", "paper", 3.0, "territorio 2 en comparaciones (línea)"],
  ["cat-3", "paper", 3.0, "territorio 3 en comparaciones (línea)"],
  ["cat-4", "paper", 3.0, "territorio 4 en comparaciones (línea)"],
];

let failed = 0;
for (const mode of ["light", "dark"]) {
  console.log(`\n${mode === "light" ? "Claro" : "Oscuro"}`);
  for (const [fg, bg, min, use] of PAIRS) {
    const r = ratio(t.color[mode][fg], t.color[mode][bg]);
    const ok = r >= min;
    if (!ok) failed++;
    console.log(`  ${ok ? "OK " : "FALLA"} ${r.toFixed(2).padStart(5)} ≥ ${min}  ${fg} / ${bg}  — ${use}`);
  }
}
console.log(failed ? `\n${failed} par(es) por debajo del mínimo WCAG.` : "\nTodos los pares cumplen WCAG 2.1 AA.");
process.exit(failed ? 1 : 0);
