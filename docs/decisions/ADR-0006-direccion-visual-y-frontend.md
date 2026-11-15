# ADR-0006 — Dirección visual «Cuaderno de campo» y stack del frontend

- **Fecha:** 2026-11-14 · **Estado:** aceptada (elección del usuario entre dos propuestas, plan §5.5)
- **Decisión visual:** propuesta A «Cuaderno de campo» (`docs/ux/prototypes/A_cuaderno_de_campo.html`).
  - Claro: gris hielo #E9EDEC, papel #F7F8F7, tinta #1D2B30, acento petróleo #0D4F5F, verde mineral #4C7A5B.
  - Oscuro derivado (no la propuesta B): grafito #1A2124 con acento petróleo aclarado #6FB7C7 para contraste.
  - Tipografía: Source Serif 4 (veredicto y títulos editoriales) + Source Sans 3 (interfaz), números tabulares.
  - Esqueleto §5.2: carril de configuración a la izquierda; veredicto como frase; serie + tendencia; mapa; calidad.
  - Rampa divergente marrón seco ↔ azul verdoso húmedo centrada en 0; rayado = sin evidencia; borde discontinuo =
    territorio menor que un píxel nativo.
  - **Ámbar/goldenrod y darkorange reservados para la capa de eventos SINPAD/ENFEN** (tokens `reserved-*`).
- **Fuente única de tokens:** `packages/design-tokens/tokens.json` → `tokens.css` (`node packages/design-tokens/build.mjs`).
- **Stack frontend (plan §10.1):** Next.js 16 (App Router) + React 19 + TypeScript 5.9 estricto (TS 7 recién publicado:
  se evita hasta que Next lo soporte oficialmente), TanStack Query (datos), Zustand (estado de estudio, sincronizado con
  la URL), Apache ECharts (gráficos), MapLibre GL sin mapa base externo (estilo vacío + GeoJSON de fronteras propias, sin
  dependencia de proveedores de teselas). CSS propio con tokens; sin Tailwind ni kits de componentes genéricos.
- **Invariante:** la web no calcula estadística: todo número viene de la API (`POST /analyses`), igual que el SDK.
