# Despliegue gratuito de GaIA: Vercel Hobby (web) + Render Free (API) + Earth Engine (nasa-pizzia)

Objetivo: demostración pública con **US$ 0 de alojamiento** (ADR-0014). Ningún paso requiere tarjeta.

> **Regla de coste cero:** NO registres un medio de pago en Render ni en Vercel. Sin tarjeta, si se supera un
> límite gratuito el servicio se **suspende o pausa** hasta el mes siguiente; nunca se cobra. Earth Engine
> (no comercial, nivel Community) no requiere cuenta de facturación.

## 0. Antes de empezar (una sola vez)

| Comprobación | Dónde |
|---|---|
| Proyecto `nasa-pizzia` registrado como **no comercial** (verificado por API: `REGISTERED_NOT_COMMERCIALLY`) y cuestionario de verificación completado | Consola de Google Cloud → Earth Engine → Configuración |
| Nivel de cuota (Community = 150 EECU-h/mes, sin facturación) | Mismo lugar |

## 1. Clave dedicada de Earth Engine para Render (la creas tú; nadie más la ve)

1. Consola de Google Cloud → IAM → **Cuentas de servicio** → crear `gaia-render@nasa-pizzia.iam.gserviceaccount.com`
   (recomendado: una cuenta separada de la de tu PC, para poder revocarla sin afectar al desarrollo).
2. Roles mínimos en el proyecto `nasa-pizzia`:
   - **Earth Engine Resource Viewer** (`roles/earthengine.viewer`)
   - **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`)
3. En la cuenta → **Claves** → Agregar clave → JSON. Se descarga un archivo: **no lo pongas en el repositorio**
   (el `.gitignore` y la API lo impiden, pero mejor no tentar).
4. Guárdalo fuera del repositorio hasta subirlo a Render (paso 2.4) y después **bórralo de tu PC**.

## 2. API en Render Free

1. Crea una cuenta en <https://render.com> (con GitHub). **No agregues tarjeta.**
2. Instala la **app de Render en la organización** de GitHub (https://github.com/apps/render/installations/new →
   `pizzIA-dev`). Sin la app, Render puede clonar el repo con tu conexión personal pero **no recibe los avisos de
   `push`** y el despliegue automático no se dispara (pasó el 2026-11-15).
3. **New → Blueprint** → elige el repositorio. Render lee `render.yaml` y crea el servicio `gaia-api` (plan free).
   Te pedirá los valores marcados como secretos:
   - `EE_SERVICE_ACCOUNT_EMAIL` = correo de la cuenta del paso 1.
   - `ALLOWED_ORIGINS` = la URL de Vercel (paso 3). La primera vez puedes poner `https://localhost` y
     actualizarla después.
4. Servicio `gaia-api` → **Environment → Secret Files** → agrega un archivo llamado exactamente
   `ee-service-account.json` con el contenido del JSON del paso 1. Render lo monta en
   `/etc/secrets/ee-service-account.json` (ya configurado en `EE_SERVICE_ACCOUNT_FILE`).
5. Despliega. La compilación (~3–5 min) instala dependencias, descarga y verifica las fronteras oficiales del IGN
   (HDX, SHA-256) y precarga la caché de demostración.
6. Comprueba: `https://gaia-api.onrender.com/api/v1/health` (la URL exacta la muestra Render) → `"status": "ok"`.

## 3. Web en Vercel Hobby (con la CLI)

Vercel Hobby **no** despliega desde Git un repositorio privado de una organización de GitHub; por eso se usa la CLI
desde tu PC (sube solo lo indicado en `.vercelignore`: la web y los tokens de diseño).

```bash
npx vercel login
```

Desde la **raíz** del repositorio, la primera vez (crea el proyecto; cuando pregunte, «Root Directory» = `apps/web`):

```bash
npx vercel link
```

Variable de entorno con la URL de la API de Render:

```bash
npx vercel env add NEXT_PUBLIC_API_URL production
```

(escribe `https://gaia-api.onrender.com/api/v1`, o la URL real). Despliegue de producción:

```bash
npx vercel deploy --prod
```

Después, vuelve a Render y pon la URL de Vercel en `ALLOWED_ORIGINS` (paso 2.3).

## 3b. Actualizaciones

- **API:** automática. Cada merge a `main` dispara un despliegue en Render (Auto-Deploy «On Commit»).
- **Web:** manual, desde `apps/web`: `npx vercel deploy --prod` (Hobby no despliega desde Git un repo privado de
  organización, por eso la integración de Git de Vercel está desconectada).

## 4. Verificación tras desplegar

- [ ] Abrir la web: si la API dormía, aparece «Despertando el servidor gratuito…» y los datos llegan solos (1–2 min).
- [ ] El Panel muestra las 4 variables del territorio de ejemplo; elegir otro país (p. ej. Ecuador) funciona.
- [ ] SDK: `EarthTrendClient(base_url="https://gaia-api.onrender.com/api/v1").analyses.run(spec)` devuelve el
      mismo `run_id` que la web para la misma configuración.
- [ ] Render → Metrics: memoria < 512 MB (medido en local: pico 231 MB).

## 5. Límites conocidos (planes gratuitos)

| Límite | Efecto en GaIA | Mitigación aplicada |
|---|---|---|
| Render se duerme tras 15 min sin visitas | Primera visita espera 1–2 min | Aviso en la web + reintentos automáticos |
| Render: 0,1 CPU | Cálculos de CPU más lentos (≈ 10×) | Caché de geometrías simplificadas; resultados en caché |
| Render: disco efímero | La caché nueva se pierde al dormir/reiniciar | Caché de demostración precargada en cada compilación |
| Render: 5 GB/mes de salida | Si se supera, suspensión hasta el mes siguiente | Respuestas comprimidas (gzip) |
| Render: 750 h/mes de instancia | Un servicio despierto todo el mes ≈ 744 h | No usar «pings» para mantenerlo despierto |
| Render: 500 min/mes de compilación | ≈ 100 despliegues | Desplegar solo cambios listos |
| Vercel Hobby: solo uso no comercial | GaIA es gratuita y sin fines de lucro | — |
| Earth Engine Community: 150 EECU-h/mes | Si se agota, «modo restringido» (más lento), sin coste | Caché; vigilar en Cloud Monitoring |
| Tokens de API en disco efímero | Se pierden al reiniciar | La web no los usa; el SDK funciona sin token (análisis ligeros) |

## 6. Rotación y retirada

- Si la clave se expone o termina la demo: Consola → cuenta `gaia-render` → Claves → **eliminar**; en Render,
  borrar el Secret File. La API pasa a responder 503 «fuente no disponible» (honesto), sin romper la web.
