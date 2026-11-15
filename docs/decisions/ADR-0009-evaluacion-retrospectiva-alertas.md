# ADR-0009 — Escena 5: evaluación retrospectiva de reglas de alerta por lluvia diaria

- **Fecha:** 2026-11-15 · **Estado:** aceptada
- **Contexto:** plan §9.2 (escena 5 «¿habría dado una alerta?»), §9.3 (límites), §7.7 (asociación ≠ alerta). El estudio
  previo (v12/v13.1) encontró muchas falsas alarmas y casi ningún acierto en 2022–2025; la escena estaba marcada
  «en preparación» hasta poder reproducirlo con datos oficiales y la plataforma.
- **Datos:** `scripts/ingest_case_trujillo_daily.py` extrae de Earth Engine `NASA/GPM_L3/IMERG_V07` (Final,
  semihoraria; Σ tasa × 0,5 h) por **día local de Lima** (05:00–05:00 UTC) y distrito IGN (media ponderada por área,
  11 132 m), 2017–2025. Una sola agregación por mes (imagen de 28–31 bandas): EE rechaza muchas agregaciones
  concurrentes. Se guarda el número de semihoras por día; un día con < 48 no se evalúa. Salida versionada
  `data/case-trujillo/imerg_daily_districts.csv.gz` con procedencia en la cabecera.
- **Validación de datos:** frente al panel diario v12 (8 distritos comunes, 23 009 distrito-días 2017–2025):
  correlación 1,000 con desfase 0 (0,29 con ±1 día) y totales 13 769 vs 13 772 mm → misma definición de día local.
- **Decisión (motor `apps/api/app/services/cases/backtest.py`, endpoint `GET /cases/{id}/backtest`):**
  - Unidad distrito-día. Señal S(t) = lluvia de los `w` días **anteriores** (t−w … t−1): la alerta del día t no usa
    información del propio día ni posterior.
  - Umbral por distrito = percentil p de S en **2017–2021** (calibración), con mínimo 1 mm (en la costa árida el P90
    puede ser 0 mm y alertaría todos los días). Se aplica sin cambios a **2022–2025** (prueba fuera de muestra).
  - Acierto: registro SINPAD focal en el distrito entre t y t+h−1. Se publican VP/FP/FN/VN, FAR = FP/(VP+FP), POD por
    registro con IC de Wilson, anticipación, alertas por distrito-año y el POD esperado con alertas aleatorias de la
    misma frecuencia (1 − (1 − tasa)^h). El periodo de calibración se muestra como «en muestra, optimista».
  - **Regla principal declarada antes de ver resultados:** P95, ventana 3 días, horizonte 3 días. Las 27
    combinaciones (P90/95/99 × 1/3/7 × 1/3/7) se muestran como sensibilidad, con advertencia contra elegir a posteriori.
  - Registros sin polígono IGN (Alto Trujillo, 130112) quedan fuera y se listan; no se reasignan a otro distrito.
- **Advertencias obligatorias:** IMERG Final es reprocesado → «anticipación POTENCIAL retrospectiva», no desempeño
  operativo (exigiría IMERG Early/Late); N de prueba diminuto; registro administrativo ≠ fenómeno (parte de las «falsas
  alarmas» pueden ser eventos no registrados); no es un sistema de alerta ni sustituye a SENAMHI/INDECI.
- **Resultado (2026-11-15):** regla principal en prueba: 0 de 3 registros anticipados (IC 95 % 0–56 %), 755 alertas
  distrito-día sin registro (17 por distrito-año); azar esperado 13 %. En calibración 10/12, pero 10 de 12 son de 2017.
  Coincide con v13.1 (VP = 0 en prueba). Se publica como resultado nulo, con la misma visibilidad.
- **Consecuencias:** cálculo puro sobre datos versionados (sin EE en tiempo de petición, apto para anónimos y CI).
  Pruebas sintéticas en `tests/scientific/test_case_backtest.py`; contrato en `tests/contract/test_case_trujillo.py`.
