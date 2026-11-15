# ADR-0005 — Acceso por token, estimación de coste y límites de uso

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** plan §12.2 (estimar coste antes de procesar), §12.3 (explorar sin registro; lo pesado con credencial y
  cuota) y §12A.2 (tokens revocables con scopes, 401/403/413/429 con `Retry-After`). Earth Engine tiene cuotas de
  concurrencia y EECU-h/mes: nada puede ser ilimitado.
- **Decisión:**
  - **Coste** (`app/services/analyses/cost.py`): `source_images` (meses × imágenes/mes según granularidad nativa) y
    `pixel_images` (× píxeles del ROI a la escala de extracción). Segundos ≈ 3 + 8e-4·imágenes + 2e-7·píxel-imágenes,
    calibrado con mediciones reales (MERRA-2 22 años ≈ 157 s estimados vs 100–210 s medidos). Niveles:
    `cached` (run o extracción en caché) · `light` (≤ 5e4 imágenes y ≤ 5e7 píxel-imágenes) · `heavy` (≤ 6e5 y ≤ 3e9) ·
    `too_large` (resto o ROI > `MAX_ROI_AREA_KM2`). Umbrales configurables por entorno.
  - **Runner** dividido en `prepare()` (valida, normaliza, hash, detecta caché, resuelve geografía) y `execute()`;
    así la política decide antes de tocar Earth Engine y lo ya calculado nunca se cobra.
  - **Identidad** (`app/core/security.py`): anónima (`anon:<ip>`) o token `ets_<key_id>_<secreto>` (solo SHA-256 en
    disco, scopes, revocable). Gestión: `scripts/manage_api_keys.py`. `GET /me`, `GET /me/api-keys`,
    `DELETE /me/api-keys/{key_id}` (autorevocación). La creación de claves por API queda para cuando existan cuentas.
  - **Política:** anónimo → `cached` + `light`; token con `analyses:write` → también `heavy`; `too_large` → 413.
    `AUTH_MODE=required` exige token para todo análisis nuevo (catálogo y geografías siguen públicos).
  - **Límites** (`app/core/limits.py`): ventana deslizante de extracciones nuevas por hora (anónimo 20, token 200; las
    respuestas de caché no consumen cupo) → 429 `quota_exceeded` + `Retry-After`; semáforo de extracciones simultáneas
    (2) → 503 `source_busy` + `Retry-After: 30`.
  - Errores por excepción `Problem` → `application/problem+json` uniforme.
- **Limitaciones:** contadores en memoria de un proceso (para varios workers: Redis/DB con la misma interfaz); el
  coste es orientativo, no facturación de EE.
