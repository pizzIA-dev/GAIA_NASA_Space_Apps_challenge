# ADR-0011 — Diferencia de pendientes con IC propio (solo Theil–Sen)

- **Fecha:** 2026-11-15 · **Estado:** aceptada
- **Contexto:** plan §7 («comparación territorial … con inferencia compatible»), §12A.1 («diferencia de pendientes e
  IC propio»). Hasta ahora `/analyses/compare` solo daba IC por territorio y advertía que el solapamiento de IC no es
  una prueba. Los territorios vecinos comparten el clima: sus series están muy correlacionadas (Huanchaco–Moche,
  lluvia anual IMERG: r = 0,96), así que combinar los IC por separado es incorrecto.
- **Decisión:** `POST /api/v1/analyses/difference` {a, b, resamples, block_length, seed} y SDK
  `analyses.difference()`. Las especificaciones deben diferir **solo** en el territorio (409 `not_comparable` si no).
  Coste y cupo como una comparación de dos análisis (reutiliza `/compare`).
  - Estimación Δ = TS(A) − TS(B). IC: **bootstrap de bloques móviles sobre pares de periodos** (cada réplica remuestrea
    los mismos bloques (t, A, B)), b = 3 años (12 meses en series mensuales), R = 2000, semilla fija. p aproximado
    por inversión del IC percentil, etiquetado como tal. Solo periodos con dato en ambas series.
  - Se informa la correlación de residuos entre A y B.
- **Mediciones que decidieron el método (simulación, n = 22 años, IC nominal 95 %):**

  | Método | Cobertura |
  |---|---|
  | Bootstrap de bloques sobre residuos (Theil–Sen), b = 2–4, con o sin inflado | 82–89 % ✗ |
  | **Bootstrap de bloques sobre pares (Theil–Sen), b = 3** | **96–98,5 %** ✓ (algo conservador) |
  | OLS: HAC Newey–West sobre A − B | 73–85 % ✗ |
  | OLS: bootstrap de bloques sobre pares | 83–92 % ✗ |

  Escenarios: AR(1) φ ∈ {0; 0,3; 0,5}, correlación cruzada ρ ∈ {0; 0,7; 0,9}.
  **Con OLS no se ofrece la diferencia** (409 con la explicación): un IC más estrecho de lo declarado es peor que
  ninguno. La prueba de cobertura queda en `tests/scientific/test_slope_difference.py`.
- **UI:** cada panel del Estudio muestra «Diferencia de pendientes» con selectores A/B entre los territorios
  calculados, la Δ con IC y una lectura en lenguaje claro (o la razón por la que no se ofrece con OLS).
- **Hallazgo colateral (pendiente):** el IC HAC de OLS para una sola serie anual corta probablemente subcubre igual que
  aquí; conviene medir la cobertura de los IC por serie del motor (`trend_core`) con el mismo protocolo.
