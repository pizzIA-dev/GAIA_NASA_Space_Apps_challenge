# ADR-0002 — Geografías globales con geoBoundaries v6 en Earth Engine + índice local

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** el plan (§3.1) pide ADM0–ADM3 con `geography_id` estable y versionado, sin unir por nombre.
- **Decisión:**
  - Fuente global: `WM/geoLab/geoBoundaries/600/ADM0|ADM1|ADM2` (gbOpen v6.0.0, CC BY 4.0 con atribución).
    `boundary_set_id = geoboundaries-gbopen-6.0.0`.
  - `geo_id`: `gb6:<ISO3>` (ADM0) o `gb6:<ISO3>:<ADMn>:<shapeID>`.
  - Índice por país (solo atributos: nombre, nivel, padre, área km²) construido en EE una vez y cacheado en
    `.cache/geographies/`. La colección no trae jerarquía: padre = ADM superior que contiene un punto interior;
    si no hay (bordes ADM1/ADM2 de fuentes distintas), el de mayor área de intersección.
  - El análisis no descarga geometrías: filtra la colección por `shapeID` dentro de EE. `geometry_hash` = hash de
    `(geo_id, boundary_set_id)`. Geometría simplificada (500 m) solo para visualización.
  - Advertencia automática si el territorio es menor que un píxel nativo del dataset.
- **Limitaciones conocidas:**
  - **Sin ADM3** en EE → distritos del Perú pendientes (caso Trujillo). geoBoundaries tampoco publica PER ADM3.
  - Perú en geoBoundaries: ADM1 = Wikimedia Commons 2008 (dominio público); ADM2 = IGN/OCHA 2020 (CC BY 3.0 IGO).
    Fuentes de distinta época → por eso el respaldo por intersección.
- **Siguiente:** adaptador peruano oficial (`boundary_set_id` propio, p. ej. `pe-ign-cod-ab-2020` o INEI) con ADM1–ADM3 y
  UBIGEO, subido como asset de EE o enviado como geometría; nunca reemplazar silenciosamente geoBoundaries.
