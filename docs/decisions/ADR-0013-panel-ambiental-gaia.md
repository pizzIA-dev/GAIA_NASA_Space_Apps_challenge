# ADR-0013 — Realineación a GaIA: el Panel ambiental como experiencia principal

- **Fecha:** 2026-11-15 · **Estado:** aceptada · **Recuperación:** tag `pre-dashboard-2026-11-15` (estado previo de `main`)
- **Contexto:** el usuario corrigió prioridades (no reinicio): la experiencia principal debe ser un **panel ambiental
  unificado** — elegir territorio, periodo, variables, método y nivel de confianza y ver todo en una página — con
  alcance mundial. Trujillo/El Niño es solo un ejemplo; el caso lo trabajan los usuarios y ENFEN no se continúa.
- **Auditoría (resumen):** motor, API (`/analyses` con caché), catálogo/capabilities, geografías mundiales, Explorar,
  Estudio, Atlas e Historias estaban completos y se **conservan**. Faltaba la página unificada, elegir el método
  completo y el nivel de confianza en la web (tareas F3/F4 pendientes) y la búsqueda mundial en la web.
- **Decisión (cambios mínimos, sin tocar contratos de API ni SDK):**
  - `/` = **Panel**: territorio (países geoBoundaries + subdivisiones; Perú con fronteras IGN), periodo anual
    (≥ 10 años), variables (una tarjeta por variable, cada una un `/analyses` independiente: carga progresiva y caché
    compartida con Explorar/Estudio/API/SDK), estimador + IC + prueba ofrecidos desde `/catalog/capabilities` (solo
    combinaciones válidas; recomendados por defecto, aviso si no corrigen autocorrelación), nivel 90/95/99 %.
    Cada tarjeta: veredicto, cambio por década, IC, prueba y p, años con dato, serie con tendencia, advertencias,
    fuente/cobertura temporal/versión/licencia y «Ver detalle» (Explorar con la misma configuración).
  - **Veredicto con α = 1 − nivel** (antes 0,05 fijo): IC y prueba se leen con el mismo umbral.
  - Especificaciones: los presets de siempre producen el mismo `run_id`; las variantes (`ic`, `prueba`, `conf`) se
    añaden sin romper URLs ni cachés existentes.
  - Navegación: Panel · Análisis avanzado (Estudio) · Atlas · Casos de estudio (Historias) · Fuentes · Métodos.
    Explorar sigue disponible como detalle de una variable. Atlas acepta cualquier territorio. Marca: **GaIA**.
- **Niveles de confianza (simulación, `scientific/reports/cobertura_ic.md`):** métodos recomendados al 90 % y 99 %:
  cercanos al nominal con poca autocorrelación (90 %: 92–94 % / 10 %; 99 %: ≥ 99 % / ≈ 1 %); con φ = 0,6 la
  confianza real baja (90 % → 83–85 %, 99 % → ≈ 95 %). El panel lo dice al elegir 90 % o 99 %.
- **Pendiente / decisión abierta:** MERRA-2 y GLDAS con periodos largos son «pesados» y requieren token; la web no
  tiene dónde introducir un token. Opciones: campo de token en la web, umbral «ligero» mayor en el servidor desplegado
  o caché precalculada. Mientras tanto la tarjeta muestra el motivo y el coste (nunca un valor inventado).
- **Pruebas:** E2E `panel.spec.ts` (portada, paridad web = API con método y nivel elegidos, «Ver detalle», quitar
  variable) + axe en `/`. Regresión completa: backend 122, E2E 39, contraste AA.
