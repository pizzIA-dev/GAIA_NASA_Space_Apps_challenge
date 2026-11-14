# Runbook — Cuenta de servicio de Earth Engine

**Cuenta:** `earth-trend-backend@nasa-pizzia.iam.gserviceaccount.com` (proyecto `nasa-pizzia`). El email y el ID no son
secretos; **la clave JSON sí lo es**: nunca en el repo, en chats, issues ni capturas.

## 1. Permisos (Consola GCP → IAM, proyecto `nasa-pizzia`) — lo hace el dueño
- `Earth Engine Resource Viewer` (`roles/earthengine.viewer`) — leer datasets. (Writer solo si se exportan assets.)
- `Service Usage Consumer` (`roles/serviceusage.serviceUsageConsumer`).
- Earth Engine API habilitada y proyecto registrado para uso no comercial (code.earthengine.google.com/register).

## 2. Clave JSON (desarrollo local / servidor de demo)
1. IAM y administración → Cuentas de servicio → `earth-trend-backend` → Claves → Agregar clave → JSON.
   (Si falla por la política `iam.disableServiceAccountKeyCreation`, usar Workload Identity en Cloud Run — ver §4.)
2. Guardar FUERA del repo, p. ej. `C:/Users/<usuario>/.secrets/earth-trend-backend.json`.
3. En `.env` del repo: `EE_SERVICE_ACCOUNT_FILE=C:/Users/<usuario>/.secrets/earth-trend-backend.json`.
4. Verificar: `apps/api/.venv/Scripts/python scripts/check_ee_auth.py` → debe decir `modo=service_account`.

El backend rechaza la clave si: está dentro del repo, no es de tipo `service_account`, su `client_email` no coincide
con `EE_SERVICE_ACCOUNT_EMAIL`, o su `project_id` no es `EE_PROJECT`.

## 3. Volver a modo usuario (solo desarrollo)
Vaciar `EE_SERVICE_ACCOUNT_FILE` → usa las credenciales de `earthengine authenticate`.

## 4. Producción (F6) — preferido sin claves
En Cloud Run, asignar `earth-trend-backend` como identidad del servicio y no montar ninguna clave JSON
(credenciales por metadata). Requiere adaptar `client.py` a `google.auth.default()` cuando no haya archivo.

## 5. Rotación / incidente
Si una clave se expone: borrarla en la consola (Claves → eliminar), crear otra, actualizar la ruta local. Las claves no
caducan solas: rotar al cerrar el challenge.
