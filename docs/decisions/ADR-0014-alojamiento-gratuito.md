# ADR-0014 — Alojamiento gratuito: Vercel Hobby (web) + Render Free (API) + Earth Engine no comercial

- **Fecha:** 2026-11-15 · **Estado:** aceptada (preparada; despliegue pendiente de las cuentas del usuario)
- **Contexto:** el usuario quiere publicar una demo de GaIA con **US$ 0 de alojamiento** y descartó Cloud Run.
  Restricciones: no habilitar servicios de pago ni crear credenciales privadas sin su autorización.
- **Verificado (2026-11-15):**
  - Earth Engine: `nasa-pizzia` → `REGISTERED_NOT_COMMERCIALLY` (API). Nivel Community 150 EECU-h/mes sin cuenta
    de facturación; al agotarse, modo restringido (más lento), sin coste.
  - Render Free: 512 MB / 0,1 CPU, se duerme a los 15 min (≈ 1 min para despertar), 750 h/mes, 5 GB/mes de salida,
    500 min/mes de compilación, disco efímero; sin medio de pago → suspensión, no cobro. «No para producción».
  - Vercel Hobby: uso personal/no comercial; **no despliega desde Git repos privados de organizaciones** → se usa la
    CLI desde la PC del usuario.
  - Medido en local: pico de memoria de la API 231 MB; arranque 5 s; simulación de la compilación de Render desde una
    copia limpia (fronteras IGN + caché sembrada) 22 s; cálculo nuevo en EE con clave fuera del repo ✓.
- **Decisión:**
  - `render.yaml` (Blueprint, plan free, región virginia): compila instalando dependencias, ingiriendo fronteras
    oficiales (HDX, SHA-256) y sembrando la caché de demostración; arranca uvicorn con `--proxy-headers` para que el
    cupo anónimo sea por IP real (sin eso, todos compartirían 20 cálculos/hora).
  - Clave de Earth Engine como **Secret File** de Render (`/etc/secrets/ee-service-account.json`), de una cuenta de
    servicio dedicada con roles mínimos que crea el usuario. Nunca en el repo, en Vercel ni en el navegador.
  - API: compresión gzip (geometría del Perú 1,1 MB → ~0,39 MB) y caché en memoria de geometrías simplificadas
    (7,9 s → 0,4 s en la segunda petición).
  - Web: todas las páginas estáticas (CDN de Vercel); aviso «Despertando el servidor gratuito…» si `/health` tarda,
    reintentos automáticos (cada 10 s, ~2 min) ante servidor dormido o EE ocupado; una respuesta no JSON (página de
    espera del proxy) se trata como transitoria. `.vercelignore` en lista blanca (solo web y tokens de diseño).
- **Consecuencias:** primera visita tras inactividad lenta; caché nueva se pierde al dormir; la demo no es un servicio
  de producción. Guía: `docs/runbooks/despliegue-gratuito.md`.
