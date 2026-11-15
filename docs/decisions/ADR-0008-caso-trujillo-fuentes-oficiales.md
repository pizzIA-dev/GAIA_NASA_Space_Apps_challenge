# ADR-0008 — Caso Trujillo desde fuentes oficiales: SINPAD (datos abiertos) + ICEN (IGP/ENFEN)

- **Fecha:** 2026-11-14 · **Estado:** aceptada (umbral ENFEN pendiente de verificación directa)
- **Contexto:** plan §6.5 y §9: reconstruir el caso desde fuentes oficiales sin notebooks; coincidencia ENFEN ≠ causa;
  los 16 registros 2017–2025 son control, no cifra fija.
- **Fuentes (verificadas en esta sesión):**
  - **SINPAD/INDECI** en la Plataforma Nacional de Datos Abiertos, licencia **ODC-BY**:
    `BD_2003-2025_EMERGENCIAS.csv` (SHA256 a1fe63f0…2687, 142 139 filas) y `BD_2026_Semestre_I.csv` (acb09730…0280).
  - **ICEN oficial** del IGP (`met.igp.gob.pe/datos/ICEN.txt`, cabecera «ICEN; ENFEN, 2024 — versión oficial»).
  - La web de ENFEN (`enfen.imarpe.gob.pe`) y gob.pe no respondieron (timeout/403) desde el entorno de desarrollo.
- **Decisión:**
  - `scripts/ingest_case_trujillo.py` descarga, verifica SHA256, normaliza y escribe `data/case-trujillo/`
    (`sinpad_trujillo.json` 318 registros de la provincia 1301xx, `icen_enfen.json`, `MANIFEST.json`), versionados.
  - Fechas: formatos mixtos (DD/MM/AAAA hasta 2024; M/D/AA en 2025) **desambiguados con las columnas oficiales AÑO/MES**.
  - Episodios ENFEN **derivados** de la serie ICEN con regla configurable: El Niño Costero si ICEN > +0,5 durante ≥ 3
    meses; La Niña Costera si ICEN < −0,7 durante ≥ 3 meses (umbrales citados de documentos ENFEN que remiten a la
    NT 01-2024). Estado `umbral_citado_pendiente_de_verificacion` visible en API y UI. Sin clasificar magnitud.
  - Cada evento: contexto ENFEN (`coincidencia_el_nino_costero` / `coincidencia_la_nina_costera` / `fuera_de_episodio`)
    y `causal_attribution.status = no_verificada` (nunca inferida por fecha). Clase visual: darkorange solo con
    atribución verificada (0 casos); goldenrod = coincidencia El Niño; gris = fuera.
  - API: `GET /cases`, `/cases/trujillo-el-nino`, `/events` (filtros geo_id/años/focal), `/enfen`. SDK `client.cases`.
  - Web: capa opcional «Contexto local» en Explorar (solo provincia de Trujillo y sus distritos): bandas de episodios
    sobre la serie, marcadores (triángulo = huaico, círculo = inundación) y tabla de eventos con leyenda y fuentes.
- **Conciliación:** 2017–2025 = **16 registros, idénticos a la v12 código a código** (fecha y contexto ENFEN 16/16).
  Los otros 8 registros focales son de 2003–2013 (fuera de la ventana de la v12). 2026-S1: ninguno.
- **Episodios derivados relevantes:** EN-COSTERO-2017 (ene–abr 2017, pico +1,31), EN-COSTERO-2023-24 (mar 2023–feb 2024,
  pico +2,92), LN-COSTERO-2017-18 (oct 2017–may 2018), **EN-COSTERO-2026 en curso** (mar–sep 2026, ICEN +4,50 en sep).
- **Pendiente:** verificar umbrales con el PDF de la NT 01-2024 (el usuario puede aportarlo); cartografía INEI con
  Alto Trujillo (130112); historia guiada de 6 escenas (§9.2); asociación eventos↔anomalías con meses de control (§7.7).
