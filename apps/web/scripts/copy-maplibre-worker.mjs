// Copia el worker de MapLibre 6 a public/ para servirlo como archivo estático (Turbopack no resuelve su URL).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "maplibre-gl", "dist", "maplibre-gl-worker.mjs");
const out = join(root, "public", "maplibre", "maplibre-gl-worker.mjs");
mkdirSync(dirname(out), { recursive: true });
copyFileSync(src, out);
console.log("worker de MapLibre copiado a public/maplibre/");
