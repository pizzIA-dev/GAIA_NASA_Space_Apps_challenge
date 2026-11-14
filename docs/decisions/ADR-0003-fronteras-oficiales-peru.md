# ADR-0003 — Fronteras oficiales del Perú (IGN vía HDX COD-AB) como conjunto por defecto para PER

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** geoBoundaries (ADR-0002) no tiene ADM3 del Perú y mezcla fuentes (ADM1 Wikimedia 2008, ADM2 IGN 2020).
  El plan (§3.1) exige un adaptador peruano autónomo y no sustituir silenciosamente fronteras oficiales.
- **Decisión:**
  - Fuente: OCHA HDX "Peru - Subnational Administrative Boundaries" (COD-AB), productor **IGN**, licencia **CC BY-IGO**,
    v01 válida desde 2020-07-14 (recurso actualizado en HDX el 2026-01-26). `boundary_set_id = pe-ign-cod-ab-2020`.
  - Ingesta reproducible `scripts/ingest_pe_boundaries.py`: descarga, verifica SHA256
    (`2f0ec51b…baafb3`), conteos (25/196/1873), validez (0 inválidas); manifiesto versionado en
    `data/manifests/pe-ign-cod-ab-2020.json`. Geometrías en `.cache/boundaries/pe-ign2020/` (no versionadas, 105 MB).
  - `geo_id = pe-ign2020:<UBIGEO>` (2/4/6 dígitos). Búsqueda por nombre o UBIGEO.
  - Geometrías **sin simplificar** enviadas a Earth Engine (máx. ~1,1 MB, Puno). `geometry_hash` incluye el SHA256 de la
    geometría. Simplificación (~0,002°) solo para visualización.
  - Para `country=PER` la búsqueda usa IGN por defecto; geoBoundaries se pide explícitamente con `boundary_set_id`.
    Si IGN no está ingerido, se usa geoBoundaries y la respuesta lo declara.
  - `boundary_set_id` en el spec debe coincidir con el del `geo_id` (si no → 422 `boundary_set_mismatch`).
- **Validación (IMERG 2003–2024 vs serie v12 del estudio previo):** 7 de 8 distritos focales con IoU 0,970–1,000 contra
  los polígonos del estudio; |diff| medio ≤ 0,024 mm, máx 0,198 mm, correlación 1,00000. Trujillo y Víctor Larco idénticos.
- **Limitación detectada:** **Alto Trujillo (UBIGEO 130112) no existe en IGN v01**; su territorio está dentro de
  El Porvenir (94,5 %) y Huanchaco (5,5 %). No se crea artificialmente: `pe-ign2020:130112` → 404. Para el caso Trujillo
  (F5) se necesita una cartografía distrital más reciente (INEI) como nuevo `boundary_set_id`, o ROI propio documentado.
