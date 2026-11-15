// Colores derivados de los tokens CSS (fuente única: packages/design-tokens). Solo en cliente.
export const cssVar = (name: string) =>
  typeof window === "undefined" ? "" : getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function hex2rgb(h: string): [number, number, number] {
  const n = parseInt(h.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function mix(a: string, b: string, f: number): string {
  const A = hex2rgb(a), B = hex2rgb(b);
  return `rgb(${A.map((v, i) => Math.round(v + ((B[i] ?? 0) - v) * f)).join(",")})`;
}

/** Rampa divergente centrada en 0 (plan §8): f ∈ [−1, 1]; seco (marrón) ↔ húmedo (azul verdoso). */
export function divergent(f: number): string {
  const c = Math.max(-1, Math.min(1, f));
  return c < 0 ? mix(cssVar("--div-mid"), cssVar("--div-dry"), -c) : mix(cssVar("--div-mid"), cssVar("--div-wet"), c);
}

export function divergentStops(n = 5): string[] {
  return Array.from({ length: n }, (_, i) => divergent(-1 + (2 * i) / (n - 1)));
}
