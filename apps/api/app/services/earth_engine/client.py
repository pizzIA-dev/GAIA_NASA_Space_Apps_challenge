"""Inicialización de Earth Engine SOLO en backend. Credenciales por entorno, nunca en el repo ni en el navegador.

Modos:
- `service_account`: EE_SERVICE_ACCOUNT_FILE apunta a una clave JSON guardada FUERA del repositorio. Se verifica que
  `client_email` coincida con EE_SERVICE_ACCOUNT_EMAIL (si está definido) y que `project_id` sea EE_PROJECT.
- `user`: credenciales locales de `earthengine authenticate` (solo desarrollo).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.core.config import REPO_ROOT, settings


class EarthEngineUnavailable(RuntimeError):
    """EE no configurado o sin credenciales (API → 503 source_unavailable)."""


logger = logging.getLogger(__name__)
_lock = threading.Lock()
_initialized = False
_auth_mode: str | None = None


def auth_mode() -> str | None:
    """Modo de autenticación activo ('service_account' | 'user') o None si EE aún no se inicializó."""
    return _auth_mode


def load_service_account_key(path: str, expected_email: str | None, expected_project: str | None) -> str:
    """Valida la clave sin exponer su contenido. Devuelve el client_email."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise EarthEngineUnavailable("EE_SERVICE_ACCOUNT_FILE no existe o no es un archivo")
    if p.is_relative_to(REPO_ROOT.resolve()):
        raise EarthEngineUnavailable("La clave de la cuenta de servicio no debe estar dentro del repositorio")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EarthEngineUnavailable("No se pudo leer la clave JSON de la cuenta de servicio") from exc
    if data.get("type") != "service_account" or "client_email" not in data or "private_key" not in data:
        raise EarthEngineUnavailable("El archivo no es una clave JSON de cuenta de servicio")
    email = data["client_email"]
    if expected_email and email != expected_email:
        raise EarthEngineUnavailable(f"La clave pertenece a {email}, se esperaba {expected_email}")
    if expected_project and data.get("project_id") not in (None, expected_project):
        raise EarthEngineUnavailable(f"La clave es del proyecto {data.get('project_id')}, se esperaba {expected_project}")
    return email


def get_ee():
    """Devuelve el módulo `ee` inicializado (perezoso, una sola vez)."""
    global _initialized, _auth_mode
    try:
        import ee
    except ImportError as exc:  # pragma: no cover
        raise EarthEngineUnavailable("earthengine-api no instalado (pip install -e .[gee])") from exc
    if _initialized:
        return ee
    with _lock:
        if _initialized:
            return ee
        if not settings.ee_project:
            raise EarthEngineUnavailable("EE_PROJECT no configurado")
        if settings.ee_service_account_file:
            email = load_service_account_key(
                settings.ee_service_account_file, settings.ee_service_account_email, settings.ee_project
            )
            mode = "service_account"
        else:
            email, mode = None, "user"
        try:
            if mode == "service_account":
                creds = ee.ServiceAccountCredentials(email, settings.ee_service_account_file)
                ee.Initialize(creds, project=settings.ee_project)
            else:
                ee.Initialize(project=settings.ee_project)  # credenciales de `earthengine authenticate`
        except Exception as exc:
            # Detalle completo solo al log del servidor; al cliente HTTP, únicamente el tipo de error.
            logger.error("Fallo al inicializar Earth Engine (project=%s, mode=%s): %s", settings.ee_project, mode, exc)
            raise EarthEngineUnavailable(f"No se pudo inicializar Earth Engine: {type(exc).__name__}") from exc
        _initialized, _auth_mode = True, mode
        logger.info("Earth Engine inicializado (project=%s, mode=%s)", settings.ee_project, mode)
    return ee
