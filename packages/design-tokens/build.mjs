// Genera tokens.css a partir de tokens.json (fuente única). Uso: node packages/design-tokens/build.mjs
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const t = JSON.parse(readFileSync(join(here, "tokens.json"), "utf8"));
const vars = (obj, prefix) => Object.entries(obj).filter(([k]) => !k.startsWith("$"))
  .map(([k, v]) => `  --${prefix}${k}: ${v};`).join("\n");

const css = `/* GENERADO por build.mjs desde tokens.json — no editar a mano. */
:root {
${vars(t.font, "font-")}
${vars(t.type, "text-")}
${vars(t.space, "space-")}
${vars(t.radius, "radius-")}
${vars(t.reserved, "reserved-")}
${vars(t.color.light, "")}
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
${vars(t.color.dark, "", "    ")}
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
${vars(t.color.dark, "")}
  color-scheme: dark;
}
`;
writeFileSync(join(here, "tokens.css"), css);
// Copia para la web (Next no importa CSS fuera de su raíz). Archivo generado: no editar.
const webOut = join(here, "..", "..", "apps", "web", "src", "styles", "tokens.css");
mkdirSync(dirname(webOut), { recursive: true });
writeFileSync(webOut, css);
console.log("tokens.css generado (paquete + apps/web)");
