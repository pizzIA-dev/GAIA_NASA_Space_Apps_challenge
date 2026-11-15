// Tokens de diseño: si el paquete del monorepo está disponible (local, CI) se regeneran; si no (compilación remota de
// Vercel, que solo recibe apps/web) se usa la copia versionada en src/styles/tokens.css.
import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const builder = join(root, "..", "..", "packages", "design-tokens", "build.mjs");
const copy = join(root, "src", "styles", "tokens.css");
if (existsSync(builder)) {
  execFileSync(process.execPath, [builder], { stdio: "inherit" });
} else if (existsSync(copy)) {
  console.log("tokens: paquete del monorepo ausente; se usa la copia versionada src/styles/tokens.css");
} else {
  console.error("tokens: falta src/styles/tokens.css y no está el paquete packages/design-tokens");
  process.exit(1);
}
