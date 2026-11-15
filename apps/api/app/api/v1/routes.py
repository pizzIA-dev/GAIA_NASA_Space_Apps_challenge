from __future__ import annotations

import math
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import ExtractionGate, RateLimited, SlidingWindowLimiter
from app.core.security import ApiKeyStore, Identity, InvalidToken
from app.schemas.analysis import AnalysisSpec
from app.services.analyses import cost, runner
from app.services.analyses.seasonal import seasonal_summary
from app.services.cases import trujillo
from app.services.cases.association import association
from app.services.earth_engine.adapters import catalog
from app.services.earth_engine.client import EarthEngineUnavailable
from app.services.geographies import geoboundaries as gb
from app.services.geographies import registry as reg
from app.services.geographies.peru_ign import BoundariesNotIngested
from app.services.statistics.slope_difference import slope_difference
from app.services.statistics.trend_core import IncompatibleMethodError, benjamini_hochberg

router = APIRouter(prefix="/api/v1")
COMPARE_MAX_SPECS = 12
ATLAS_MAX_UNITS = 250
ATLAS_UNITS_PER_QUOTA = 12


def problem(status: int, code: str, detail: str, request: Request | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": f"https://earth-trend.local/problems/{code}", "title": code, "status": status,
                 "detail": detail, "instance": str(request.url.path) if request else None},
    )


def get_store() -> runner.RunStore:
    return runner.RunStore(runner.settings.cache_dir)


def get_adapters():
    return runner.ADAPTERS


def get_geographies() -> reg.GeographyRegistry:
    return reg.registry


@router.get("/catalog/datasets", tags=["catalog"])
def list_datasets() -> list[dict]:
    return [asdict(d) for d in catalog()]


@router.get("/catalog/variables", tags=["catalog"])
def list_variables(dataset_id: str | None = None) -> list[dict]:
    out = []
    for d in catalog():
        if dataset_id and d.dataset_id != dataset_id:
            continue
        for v in d.variables:
            out.append({**asdict(v), "dataset_id": d.dataset_id, "status": d.status})
    return out


@router.get("/geographies/boundary-sets", tags=["geographies"])
def list_boundary_sets(geos=Depends(get_geographies)):
    return {"items": geos.boundary_sets(), "default_by_country": reg.OFFICIAL_DEFAULT}


@router.get("/geographies/countries", tags=["geographies"])
def list_countries(request: Request, geos=Depends(get_geographies)):
    try:
        return {"boundary_set_id": gb.BOUNDARY_SET_ID, "attribution": gb.ATTRIBUTION,
                "items": [c.to_dict() for c in geos.countries()]}
    except EarthEngineUnavailable as e:
        return problem(503, "source_unavailable", str(e), request)


@router.get("/geographies/search", tags=["geographies"])
def search_geographies(request: Request, q: str = Query(..., min_length=2, max_length=80),
                       country: str | None = Query(None, min_length=3, max_length=3),
                       level: Literal["ADM0", "ADM1", "ADM2", "ADM3"] | None = None,
                       boundary_set_id: str | None = None,
                       limit: int = Query(20, ge=1, le=100), geos=Depends(get_geographies)):
    """Busca por nombre (sin acentos) o UBIGEO. Perú usa por defecto la fuente oficial IGN (ADM1–ADM3);
    geoBoundaries se pide con `boundary_set_id=geoboundaries-gbopen-6.0.0`. Sin `country`, solo países."""
    try:
        used, items = geos.search(q, country=country, level=level, boundary_set_id=boundary_set_id, limit=limit)
        return {"boundary_set_id": used, "attribution": geos.attribution(used), "items": items}
    except gb.GeographyNotFound as e:
        return problem(404, "unknown_country_or_boundary_set", f"No soportado: {e}", request)
    except EarthEngineUnavailable as e:
        return problem(503, "source_unavailable", str(e), request)


@router.get("/geographies/{geo_id}", tags=["geographies"])
def get_geography(geo_id: str, request: Request,
                  geometry: Literal["none", "simplified"] = "none", geos=Depends(get_geographies)):
    try:
        g = geos.get(geo_id)
        out = {**g.to_dict(), "path": geos.path(g), "attribution": geos.attribution(g.boundary_set_id),
               "children": [c.to_dict() for c in geos.children(g)]}
        if geometry == "simplified":
            out["geometry"] = geos.geometry_geojson(geo_id)
            out["geometry_note"] = "Simplificada solo para visualización; el análisis usa la geometría original"
        return out
    except gb.GeographyNotFound:
        return problem(404, "unknown_geography", f"geo_id no encontrado: {geo_id}", request)
    except (EarthEngineUnavailable, BoundariesNotIngested) as e:
        return problem(503, "source_unavailable", str(e), request)


_FEATURES_CACHE: OrderedDict[str, dict] = OrderedDict()
FEATURES_CACHE_SIZE = 32  # colecciones simplificadas en memoria (la del Perú ≈ 1 MB); evita recalcular en CPU limitada


@router.get("/geographies/{geo_id}/features", tags=["geographies"])
def geography_features(geo_id: str, request: Request, geos=Depends(get_geographies)):
    """GeoJSON FeatureCollection del territorio y sus unidades hijas (geometría simplificada, solo visualización)."""
    # Solo con el registro global (en pruebas se inyectan registros temporales que no deben compartir caché).
    cacheable = geos is reg.registry
    key = geo_id
    if cacheable and key in _FEATURES_CACHE:
        _FEATURES_CACHE.move_to_end(key)
        return _FEATURES_CACHE[key]
    try:
        g = geos.get(geo_id)
        units = [("self", g), *[("child", c) for c in geos.children(g)]]
        features = [{
            "type": "Feature", "id": u.geo_id,
            "properties": {"geo_id": u.geo_id, "name": u.name, "admin_level": u.admin_level, "area_km2": u.area_km2,
                           "role": role, "boundary_set_id": u.boundary_set_id},
            "geometry": geos.geometry_geojson(u.geo_id),
        } for role, u in units]
        out = {"type": "FeatureCollection", "features": features, "attribution": geos.attribution(g.boundary_set_id),
               "geometry_note": "Simplificada solo para visualización; el análisis usa la geometría original"}
        if cacheable:
            _FEATURES_CACHE[key] = out
        while len(_FEATURES_CACHE) > FEATURES_CACHE_SIZE:
            _FEATURES_CACHE.popitem(last=False)
        return out
    except gb.GeographyNotFound:
        return problem(404, "unknown_geography", f"geo_id no encontrado: {geo_id}", request)
    except (EarthEngineUnavailable, BoundariesNotIngested) as e:
        return problem(503, "source_unavailable", str(e), request)


class Problem(Exception):
    """Error HTTP tipado → application/problem+json (manejador registrado en app.main)."""

    def __init__(self, status: int, code: str, detail: str, retry_after: int | None = None, extra: dict | None = None):
        super().__init__(detail)
        self.status, self.code, self.detail, self.retry_after, self.extra = status, code, detail, retry_after, extra


def problem_response(request: Request, p: Problem) -> JSONResponse:
    resp = problem(p.status, p.code, p.detail, request)
    if p.extra:
        import json as _json

        body = _json.loads(resp.body) | p.extra
        resp = JSONResponse(status_code=p.status, media_type="application/problem+json", content=body)
    if p.retry_after is not None:
        resp.headers["Retry-After"] = str(p.retry_after)
    return resp


_key_store = ApiKeyStore(runner.settings.api_keys_file)
_limiter = SlidingWindowLimiter(3600.0)
_gate = ExtractionGate(runner.settings.max_concurrent_extractions, wait_s=runner.settings.extraction_wait_s)


def get_key_store() -> ApiKeyStore:
    return _key_store


def get_limiter() -> SlidingWindowLimiter:
    return _limiter


def get_gate() -> ExtractionGate:
    return _gate


def get_identity(request: Request, keys: ApiKeyStore = Depends(get_key_store)) -> Identity:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return keys.verify(auth[7:].strip())
        except InvalidToken as e:
            raise Problem(401, "token_invalid", str(e)) from e
    host = request.client.host if request.client else "unknown"
    return Identity("anonymous", f"anon:{host}", None, ("catalog:read", "runs:read"))


def _extraction_limit(identity: Identity) -> int:
    s = runner.settings
    return s.anon_extractions_per_hour if identity.is_anonymous else s.key_extractions_per_hour


@router.get("/me", tags=["access"])
def me(identity: Identity = Depends(get_identity), limiter=Depends(get_limiter)):
    s = runner.settings
    lim = _extraction_limit(identity)
    return {
        "kind": identity.kind, "key_id": None if identity.is_anonymous else identity.subject, "name": identity.name,
        "scopes": list(identity.scopes), "auth_mode": s.auth_mode,
        "limits": {"new_extractions_per_hour": lim, "remaining_this_hour": limiter.remaining(identity.subject, lim),
                   "allowed_tiers": ["cached", "light"] if identity.is_anonymous else ["cached", "light", "heavy"],
                   "max_roi_area_km2": s.max_roi_area_km2},
    }


@router.get("/me/api-keys", tags=["access"])
def my_api_keys(identity: Identity = Depends(get_identity), keys=Depends(get_key_store)):
    if identity.is_anonymous:
        raise Problem(401, "token_required", "Envía Authorization: Bearer <token>")
    return {"items": [r.public() for r in keys.list() if r.key_id == identity.subject]}


@router.delete("/me/api-keys/{key_id}", tags=["access"])
def revoke_my_api_key(key_id: str, identity: Identity = Depends(get_identity), keys=Depends(get_key_store)):
    if identity.is_anonymous:
        raise Problem(401, "token_required", "Envía Authorization: Bearer <token>")
    if key_id != identity.subject:
        raise Problem(403, "scope_forbidden", "Solo puedes revocar tu propia clave")
    keys.revoke(key_id)
    return {"key_id": key_id, "revoked": True}


def _prepare(spec: AnalysisSpec, store, adapters, geos) -> runner.PreparedRun:
    try:
        return runner.prepare(spec, store=store, adapters=adapters, geographies=geos)
    except runner.AnalysisError as e:
        raise Problem(e.status, e.code, e.detail) from e
    except IncompatibleMethodError as e:
        raise Problem(409, "incompatible_method", str(e)) from e
    except EarthEngineUnavailable as e:
        raise Problem(503, "source_unavailable", str(e)) from e


def _authorize(identity: Identity, est: cost.CostEstimate) -> None:
    """Política de acceso (plan §12.3): explorar sin registro; lo pesado requiere token; nada ilimitado."""
    if est.tier == "too_large":
        raise Problem(413, "area_too_large", est.reason, extra={"cost": est.to_dict()})
    if identity.is_anonymous:
        if runner.settings.auth_mode == "required" and est.tier != "cached":
            raise Problem(401, "token_required", "Este servidor exige token para nuevos análisis",
                          extra={"cost": est.to_dict()})
        if est.tier == "heavy":
            raise Problem(401, "token_required",
                          f"Análisis pesado (~{est.estimated_seconds:.0f} s estimados, {est.source_images:,} imágenes "
                          "fuente): requiere token de API. Alternativas sin token: periodo más corto o producto mensual.",
                          extra={"cost": est.to_dict()})
    elif not identity.has("analyses:write") and est.tier != "cached":
        raise Problem(403, "scope_forbidden", "El token no tiene el scope analyses:write")


@router.post("/analyses/estimate-cost", tags=["analyses"])
def estimate_cost(spec: AnalysisSpec, identity: Identity = Depends(get_identity), store=Depends(get_store),
                  adapters=Depends(get_adapters), geos=Depends(get_geographies)):
    """Complejidad estimada del análisis y si tu identidad puede ejecutarlo (no consume cupo ni toca Earth Engine)."""
    p = _prepare(spec, store, adapters, geos)
    est = cost.estimate(p)
    try:
        _authorize(identity, est)
        allowed, why = True, None
    except Problem as e:
        allowed, why = False, {"status": e.status, "code": e.code, "detail": e.detail}
    return {"run_id": p.run_id, "analysis_spec_hash": p.s_hash, "cost": est.to_dict(), "allowed": allowed,
            "denied": why}


@router.post("/analyses", tags=["analyses"])
def create_analysis(spec: AnalysisSpec, identity: Identity = Depends(get_identity), store=Depends(get_store),
                    adapters=Depends(get_adapters), geos=Depends(get_geographies), limiter=Depends(get_limiter),
                    gate=Depends(get_gate)):
    p = _prepare(spec, store, adapters, geos)
    est = cost.estimate(p)
    _authorize(identity, est)
    if p.needs_extraction:
        try:
            limiter.check_and_add(identity.subject, _extraction_limit(identity))
        except RateLimited as e:
            raise Problem(429, "quota_exceeded", e.detail, retry_after=e.retry_after) from e
    try:
        run = runner.execute(p, extraction_gate=gate.slot())
    except RateLimited as e:
        raise Problem(503, "source_busy", e.detail, retry_after=e.retry_after) from e
    except runner.AnalysisError as e:
        raise Problem(e.status, e.code, e.detail) from e
    except IncompatibleMethodError as e:
        raise Problem(409, "incompatible_method", str(e)) from e
    except EarthEngineUnavailable as e:
        raise Problem(503, "source_unavailable", str(e)) from e
    return run | {"cost": est.to_dict()}


class CompareRequest(BaseModel):
    """Familia de análisis comparados (territorios y/o variables). Plan §12A.1 «Comparar territorios»."""

    model_config = ConfigDict(extra="forbid")
    specs: list[AnalysisSpec] = Field(min_length=1, max_length=COMPARE_MAX_SPECS)
    multiple_testing: Literal["none", "BH_FDR"] = "BH_FDR"
    family_id: str | None = Field(None, max_length=120)


@router.post("/analyses/compare", tags=["analyses"])
def compare_analyses(req: CompareRequest, identity: Identity = Depends(get_identity), store=Depends(get_store),
                     adapters=Depends(get_adapters), geos=Depends(get_geographies), limiter=Depends(get_limiter),
                     gate=Depends(get_gate)):
    """Ejecuta varios análisis con la misma política de coste/cuota y corrige por pruebas múltiples (BH-FDR).

    Cada ítem falla o tiene éxito por separado (p. ej. un distrito sin píxeles no invalida a los demás).
    No estima la diferencia entre pendientes: para eso, POST /analyses/difference (IC propio, plan §12A.1).
    """
    slots: list[dict] = []
    for i, spec in enumerate(req.specs):
        geo_id = spec.geography.geo_ids[0] if spec.geography.geo_ids else "custom_roi"
        try:
            p = _prepare(spec, store, adapters, geos)
            est = cost.estimate(p)
            _authorize(identity, est)
            slots.append({"index": i, "geo_id": geo_id, "prepared": p, "cost": est})
        except Problem as e:
            slots.append({"index": i, "geo_id": geo_id, "error": {"status": e.status, "code": e.code, "detail": e.detail}})
    # Cuota: se verifica para toda la familia ANTES de consumir, para no dejar comparaciones a medias.
    new = [s for s in slots if "prepared" in s and s["prepared"].needs_extraction]
    limit = _extraction_limit(identity)
    if len(new) > limiter.remaining(identity.subject, limit):
        raise Problem(429, "quota_exceeded",
                      f"La comparación requiere {len(new)} extracciones nuevas y tu cupo restante esta hora es "
                      f"{limiter.remaining(identity.subject, limit)}. Usa un token o menos territorios.", retry_after=60)
    for s in new:
        try:
            limiter.check_and_add(identity.subject, limit)
        except RateLimited as e:
            raise Problem(429, "quota_exceeded", e.detail, retry_after=e.retry_after) from e

    items: list[dict] = []
    for s in slots:
        if "error" in s:
            items.append({"index": s["index"], "geo_id": s["geo_id"], "status": "failed", "error": s["error"]})
            continue
        try:
            run = runner.execute(s["prepared"], extraction_gate=gate.slot())
            items.append({"index": s["index"], "geo_id": s["geo_id"], "status": "succeeded", "run_id": run["run_id"],
                          "analysis_spec_hash": run["analysis_spec_hash"], "statistics": dict(run["statistics"]),
                          "series": run["series"], "geography": run.get("geography"),
                          "source_versions": run["source_versions"], "cache_hit": run.get("cache_hit", False),
                          "cost": s["cost"].to_dict()})
        except RateLimited as e:
            raise Problem(503, "source_busy", e.detail, retry_after=e.retry_after) from e
        except (runner.AnalysisError, IncompatibleMethodError, EarthEngineUnavailable) as e:
            err = ({"status": e.status, "code": e.code, "detail": e.detail} if isinstance(e, runner.AnalysisError)
                   else {"status": 409 if isinstance(e, IncompatibleMethodError) else 503,
                         "code": "incompatible_method" if isinstance(e, IncompatibleMethodError) else "source_unavailable",
                         "detail": str(e)})
            items.append({"index": s["index"], "geo_id": s["geo_id"], "status": "failed", "error": err})

    ok = [it for it in items if it["status"] == "succeeded"]
    if req.multiple_testing == "BH_FDR":
        qs = benjamini_hochberg([it["statistics"]["p_value"] for it in ok])
        for it, q in zip(ok, qs, strict=True):
            it["statistics"]["q_value"] = q
            it["statistics"]["multiple_tests_family"] = req.family_id or "comparacion"
    return {
        "family_id": req.family_id, "multiple_testing": req.multiple_testing, "family_size": len(ok),
        "items": sorted(items, key=lambda it: it["index"]),
        "note": "q-valores BH-FDR sobre los ítems con p-valor de esta familia. Un solapamiento de IC no equivale a una "
                "prueba de diferencia: para comparar dos pendientes usa POST /analyses/difference (IC propio).",
    }


class AtlasRequest(BaseModel):
    """Atlas (plan §4.1, §8 «mapa de tendencias», MAP-01): pendiente de una variable en TODAS las subunidades de un
    territorio, con la misma especificación que Explorar (comparten caché) y BH-FDR sobre la familia de unidades."""

    model_config = ConfigDict(extra="forbid")
    parent_geo_id: str
    dataset_id: str
    variable_id: str
    start_year: int = Field(2003, ge=1980, le=2100)
    end_year: int = Field(2024, ge=1980, le=2100)
    method: Literal["sen", "ols"] = "sen"


ATLAS_METHODS = {  # = presets «sen» y «ols» de la web (misma especificación → caché compartida). ADR-0012.
    "sen": {"estimator": "theil_sen", "interval_method": "theil_sen_ar1", "significance_test": "mann_kendall_ar1"},
    "ols": {"estimator": "ols", "interval_method": "ar1_effective_n", "significance_test": "ols_ar1_t"},
}


EE_TRANSIENT = ("Too many concurrent aggregations", "Computation timed out", "Too Many Requests")
ATLAS_RETRY_WAITS_S = (5.0, 15.0)


def _execute_with_retry(p: runner.PreparedRun, waits: tuple[float, ...] = ATLAS_RETRY_WAITS_S) -> dict:
    """Reintenta solo errores TRANSITORIOS de Earth Engine (límite de agregaciones concurrentes, etc.). Los errores
    de datos o de método se propagan al primer intento. Medido: NDVI 25 departamentos con 6 en paralelo → 2 fallos."""
    for wait in (*waits, None):
        try:
            return runner.execute(p)
        except (runner.AnalysisError, IncompatibleMethodError):
            raise
        except Exception as e:
            if wait is None or not any(t in str(e) for t in EE_TRANSIENT):
                raise
            time.sleep(wait)
    raise AssertionError("inalcanzable")


def _atlas_unit(slot: dict) -> dict:
    u = slot["unit"]
    base = {"geo_id": u.geo_id, "name": u.name, "admin_level": u.admin_level, "area_km2": u.area_km2}
    if "error" in slot:
        return base | {"status": "failed", "error": slot["error"]}
    try:
        run = _execute_with_retry(slot["prepared"])
    except runner.AnalysisError as e:
        return base | {"status": "failed", "error": {"status": e.status, "code": e.code, "detail": e.detail}}
    except IncompatibleMethodError as e:
        return base | {"status": "failed", "error": {"status": 409, "code": "incompatible_method", "detail": str(e)}}
    except Exception as e:  # noqa: BLE001 — fallo de Earth Engine en esta unidad: se informa, no tumba el atlas
        return base | {"status": "failed", "error": {"status": 503, "code": "source_error",
                                                     "detail": f"Earth Engine: {type(e).__name__}: {str(e)[:160]}"}}
    return base | {"status": "succeeded", "run_id": run["run_id"], "statistics": dict(run["statistics"])}


@router.post("/atlas", tags=["analyses"])
def atlas(req: AtlasRequest, identity: Identity = Depends(get_identity), store=Depends(get_store),
          adapters=Depends(get_adapters), geos=Depends(get_geographies), limiter=Depends(get_limiter),
          gate=Depends(get_gate)):
    """Pendiente anual por subunidad, con la MISMA especificación que Explorar (comparten caché). Las series nuevas se
    extraen en paralelo bajo un turno del semáforo de EE; cada 12 unidades nuevas cuentan como una extracción del cupo.

    Cada unidad falla o tiene éxito por separado (p. ej. sin píxeles válidos). q-valores BH-FDR sobre las unidades.
    """
    if req.end_year - req.start_year < 9:
        raise Problem(422, "invalid_request", "El atlas requiere al menos 10 años (end_year − start_year ≥ 9)")
    try:
        parent = geos.get(req.parent_geo_id)
        units = geos.children(parent)
    except reg.GeographyNotFound as e:
        raise Problem(404, "unknown_geography", f"geo_id no encontrado: {req.parent_geo_id}") from e
    except BoundariesNotIngested as e:
        raise Problem(503, "source_unavailable", str(e)) from e
    if not units:
        raise Problem(422, "no_subunits", f"{parent.name} no tiene subunidades en el sistema de fronteras")
    if len(units) > ATLAS_MAX_UNITS:
        raise Problem(413, "too_many_units", f"{len(units)} subunidades superan el máximo de {ATLAS_MAX_UNITS} por atlas")
    slots: list[dict] = []
    for u in units:
        spec = AnalysisSpec.model_validate({
            "data": {"dataset_id": req.dataset_id, "variable_id": req.variable_id},
            "geography": {"geo_ids": [u.geo_id]},
            "time": {"start": f"{req.start_year}-01-01", "end_exclusive": f"{req.end_year + 1}-01-01",
                     "granularity": "year"},
            "statistics": ATLAS_METHODS[req.method],
        })
        try:
            slots.append({"unit": u, "prepared": _prepare(spec, store, adapters, geos)})
        except Problem as e:
            if e.code in ("unknown_dataset", "unknown_variable", "incompatible_method", "insufficient_coverage"):
                raise  # el error es de la petición (igual para todas las unidades), no de un territorio
            slots.append({"unit": u, "error": {"status": e.status, "code": e.code, "detail": e.detail}})
    preps = [s["prepared"] for s in slots if "prepared" in s]
    est = cost.estimate_batch(preps)
    _authorize(identity, est)
    new = [p for p in preps if p.needs_extraction]
    if new:
        # Cupo: cada ATLAS_UNITS_PER_QUOTA unidades nuevas cuentan como una extracción (como una familia de /compare).
        need = math.ceil(len(new) / ATLAS_UNITS_PER_QUOTA)
        limit = _extraction_limit(identity)
        if need > limiter.remaining(identity.subject, limit):
            raise Problem(429, "quota_exceeded", f"El atlas requiere {need} extracciones de tu cupo y te quedan "
                          f"{limiter.remaining(identity.subject, limit)} esta hora. Usa un token o un territorio menor.",
                          retry_after=60)
        for _ in range(need):
            limiter.check_and_add(identity.subject, limit)
        try:
            # Un turno del semáforo global; dentro, extracciones individuales en paralelo (mismo código que Explorar:
            # resultados idénticos y caché compartida). La reducción multibanda por lotes resultó más lenta en EE.
            with gate.slot(), ThreadPoolExecutor(max_workers=runner.settings.atlas_parallel_extractions) as pool:
                items = list(pool.map(_atlas_unit, slots))
        except RateLimited as e:
            raise Problem(503, "source_busy", e.detail, retry_after=e.retry_after) from e
    else:
        items = [_atlas_unit(s) for s in slots]
    ok = [it for it in items if it["status"] == "succeeded"]
    for it, q in zip(ok, benjamini_hochberg([it["statistics"]["p_value"] for it in ok]), strict=True):
        it["statistics"]["q_value"] = q
        it["statistics"]["multiple_tests_family"] = f"atlas:{parent.geo_id}"
    adapter = adapters[req.dataset_id]
    var = adapter.info.variable(req.variable_id)
    abs_est = [abs(it["statistics"]["estimate"]) for it in ok if it["statistics"].get("estimate") is not None]
    return {
        "parent": {"geo_id": parent.geo_id, "name": parent.name, "admin_level": parent.admin_level},
        "variable": {"dataset_id": req.dataset_id, "variable_id": req.variable_id, "unit": var.unit_display,
                     "physical_quantity": var.physical_quantity},
        "period": [req.start_year, req.end_year], "method": ATLAS_METHODS[req.method],
        "n_units": len(items), "n_succeeded": len(ok),
        "scale": {"center": 0, "max_abs_estimate": max(abs_est) if abs_est else None},
        "pixel_km2": (adapter.info.native_scale_m / 1000.0) ** 2,
        "source_versions": [{"dataset_id": adapter.info.dataset_id, "ee_collection_id": adapter.info.ee_collection_id,
                             "version": adapter.info.version, "native_scale_m": adapter.info.native_scale_m}],
        "cost": est.to_dict(), "new_extractions": len(new), "items": items,
        "note": "Pendiente por unidad con su propio IC; q-valores BH-FDR sobre las unidades del atlas. Escala divergente "
                "centrada en 0, común a todas las unidades; las unidades sin evidencia se marcan, no se ocultan.",
    }


class DifferenceRequest(BaseModel):
    """Diferencia de pendientes A − B con IC propio (plan §12A.1 «Comparar territorios»)."""

    model_config = ConfigDict(extra="forbid")
    a: AnalysisSpec
    b: AnalysisSpec
    resamples: int = Field(2000, ge=500, le=10000)
    block_length: int | None = Field(None, ge=1, le=36)
    seed: int = 2026


@router.post("/analyses/difference", tags=["analyses"])
def slope_difference_endpoint(req: DifferenceRequest, identity: Identity = Depends(get_identity),
                              store=Depends(get_store), adapters=Depends(get_adapters), geos=Depends(get_geographies),
                              limiter=Depends(get_limiter), gate=Depends(get_gate)):
    """Diferencia de pendientes (Theil–Sen) entre dos análisis que solo difieren en el territorio.

    No se combinan los IC individuales: bootstrap de bloques sobre pares de periodos, que conserva la correlación
    entre territorios vecinos. Coste y cupo como una comparación de dos análisis.
    """
    da, db = req.a.model_dump(mode="json"), req.b.model_dump(mode="json")
    same = {k: da[k] == db[k] for k in ("data", "time", "transforms")}
    same["estimator"] = da["statistics"]["estimator"] == db["statistics"]["estimator"]
    if not all(same.values()):
        diff = ", ".join(k for k, v in same.items() if not v)
        raise Problem(409, "not_comparable",
                      f"Las dos especificaciones deben diferir solo en el territorio (difieren en: {diff})")
    if da["geography"] == db["geography"]:
        raise Problem(422, "invalid_request", "A y B son el mismo territorio")
    fam = compare_analyses(CompareRequest(specs=[req.a, req.b], multiple_testing="none", family_id="diferencia"),
                           identity, store, adapters, geos, limiter, gate)
    items = fam["items"]
    failed = [it for it in items if it["status"] != "succeeded"]
    if failed:
        e = failed[0]["error"]
        raise Problem(e["status"], e["code"], f"{'A' if failed[0]['index'] == 0 else 'B'}: {e['detail']}")
    ia, ib = items
    st = req.a.statistics
    block = req.block_length or (12 if req.a.time.granularity == "month" else 3)
    unit = ia["statistics"]["estimate_unit"].rsplit("/", 1)[0]
    try:
        diff = slope_difference(
            [r["time_start_utc"] for r in ia["series"]], [r["value"] for r in ia["series"]],
            [r["time_start_utc"] for r in ib["series"]], [r["value"] for r in ib["series"]],
            estimator=st.estimator, confidence_level=st.confidence_level, time_unit=st.time_unit, value_unit=unit,
            resamples=req.resamples, block_length=block, seed=req.seed)
    except IncompatibleMethodError as e:
        raise Problem(409, "incompatible_method", str(e)) from e

    def brief(it: dict) -> dict:
        s = it["statistics"]
        return {"geo_id": it["geo_id"], "geography": it.get("geography"), "run_id": it["run_id"],
                "estimate": s["estimate"], "ci_lower": s["ci_lower"], "ci_upper": s["ci_upper"],
                "p_value": s["p_value"], "estimate_unit": s["estimate_unit"]}

    return {"a": brief(ia), "b": brief(ib), "difference": diff,
            "interpretation": "Diferencia = pendiente de A menos pendiente de B, con su propio IC. Que los IC de A y B "
                              "se solapen no implica que la diferencia sea cero, ni lo contrario."}


def _run(run_id: str, store) -> dict:
    run = store.get("runs", run_id)
    if run is None:
        raise Problem(404, "unknown_run", f"run no encontrado: {run_id}")
    return run


@router.get("/analyses/{run_id}", tags=["analyses"])
def get_analysis(run_id: str, store=Depends(get_store)):
    run = _run(run_id, store)
    return {k: run[k] for k in ("run_id", "status", "analysis_spec_hash", "quality", "source_versions")} | {
        "results": {
            "series_url": f"/api/v1/analyses/{run_id}/series",
            "statistics_url": f"/api/v1/analyses/{run_id}/statistics",
            "manifest_url": f"/api/v1/analyses/{run_id}/manifest",
        }
    }


@router.get("/analyses/{run_id}/statistics", tags=["analyses"])
def get_statistics(run_id: str, store=Depends(get_store)):
    return _run(run_id, store)["statistics"]


@router.get("/analyses/{run_id}/series", tags=["analyses"])
def get_series(run_id: str, store=Depends(get_store)):
    run = _run(run_id, store)
    return {"run_id": run_id, "unit": run["statistics"]["estimate_unit"].split("/")[0], "series": run["series"]}


@router.get("/analyses/{run_id}/manifest", tags=["analyses"])
def get_manifest(run_id: str, store=Depends(get_store)):
    run = _run(run_id, store)
    return {k: run[k] for k in ("run_id", "analysis_spec_hash", "request", "source_versions", "provenance",
                                "compute")}


@router.get("/analyses/{run_id}/seasonal", tags=["analyses"])
def get_seasonal(run_id: str, store=Depends(get_store)):
    """Matriz año × mes, climatología mensual (media, mediana, P25–P75) y meses extremos de la serie MENSUAL extraída.

    Se calcula desde la extracción del run (sin volver a Earth Engine), aunque el run sea anual o de anomalías.
    """
    run = _run(run_id, store)
    key = run.get("provenance", {}).get("extraction_key")
    extraction = store.get("extractions", key) if key else None
    if extraction is None:
        raise Problem(404, "extraction_not_cached", "La extracción mensual de este run ya no está en caché; vuelve a ejecutarlo.")
    rows = extraction["rows"]
    unit = rows[0].get("unit", "") if rows else ""
    return {"run_id": run_id, "source_versions": run["source_versions"], **seasonal_summary(rows, unit)}


# ---------------------------------------------------------------- casos (plan §9): capas nacionales opcionales
# Casos de estudio locales (p. ej. Trujillo): NO forman parte de la plataforma general. Solo se montan si
# ENABLE_CASE_STUDIES=true (app.main); por defecto no aparecen en la API pública ni en su documentación.
cases_router = APIRouter(prefix="/api/v1")



@cases_router.get("/cases", tags=["cases"])
def list_cases():
    try:
        s = trujillo.summary()
    except FileNotFoundError as e:
        raise Problem(503, "case_not_ingested", str(e)) from e
    return {"items": [{"id": s["id"], "title": s["title"], "description": s["description"],
                       "province_geo_id": s["province_geo_id"]}]}


def _case(case_id: str) -> None:
    if case_id != trujillo.CASE_ID:
        raise Problem(404, "unknown_case", f"Caso no encontrado: {case_id}")


@cases_router.get("/cases/{case_id}", tags=["cases"])
def get_case(case_id: str):
    _case(case_id)
    try:
        return trujillo.summary()
    except FileNotFoundError as e:
        raise Problem(503, "case_not_ingested", str(e)) from e


@cases_router.get("/cases/{case_id}/events", tags=["cases"])
def get_case_events(case_id: str, geo_id: str | None = None, year_from: int | None = Query(None, ge=1990),
                    year_to: int | None = Query(None, le=2100), focal: bool = True, geos=Depends(get_geographies)):
    """Registros SINPAD del caso. `geo_id` (pe-ign2020:UBIGEO de la provincia o un distrito) filtra por territorio."""
    _case(case_id)
    ubigeo = None
    if geo_id:
        if not geo_id.startswith("pe-ign2020:1301"):
            raise Problem(422, "outside_case", "El caso cubre la provincia de Trujillo (pe-ign2020:1301 y sus distritos)")
        ubigeo = geo_id.split(":", 1)[1]
    known = {g.geo_id for g in geos.pe.all()} if geos.pe.available else None
    items = trujillo.events(ubigeo, year_from, year_to, focal, known)
    return {"case_id": case_id, "count": len(items), "items": items,
            "legend": {"atribucion_verificada": "darkorange (0 casos documentados)",
                       "coincidencia_el_nino": "goldenrod: ocurrió durante un episodio El Niño Costero; NO prueba causa",
                       "fuera_de_el_nino": "gris: fuera de episodios El Niño Costero"},
            "note": "Reporte administrativo ≠ fenómeno físico único; ausencia de registro ≠ ausencia de evento."}


@cases_router.get("/cases/{case_id}/enfen", tags=["cases"])
def get_case_enfen(case_id: str, year_from: int | None = Query(None, ge=1950), year_to: int | None = Query(None, le=2100)):
    """Serie oficial ICEN y episodios El Niño/La Niña Costera derivados con la regla operacional declarada."""
    _case(case_id)
    return trujillo.enfen(year_from, year_to)


@cases_router.get("/cases/{case_id}/backtest", tags=["cases"])
def get_case_backtest(case_id: str):
    """Escena 5 (plan §9.2): ¿habría dado una alerta? Reglas de lluvia diaria IMERG por distrito, umbrales fijados en
    2017–2021 y evaluados fuera de muestra en 2022–2025 (VP/FP/FN/VN, POD con IC de Wilson, falsas alarmas).

    Precalculado a partir de datos versionados: no consulta Earth Engine. Anticipación POTENCIAL retrospectiva.
    """
    _case(case_id)
    try:
        return trujillo.backtest_result()
    except FileNotFoundError as e:
        raise Problem(503, "case_not_ingested", str(e)) from e


class AssociationRequest(BaseModel):
    """Escena 4 del caso (plan §9.2): ¿relación o coincidencia? Panel distrito × mes con y sin registros."""

    model_config = ConfigDict(extra="forbid")
    dataset_id: str = "nasa-gpm-imerg-monthly-v07"
    variable_id: str = "precipitation_mm_month"
    year_from: int = Field(2003, ge=2001, le=2025)
    year_to: int = Field(2024, ge=2002, le=2026)
    lags: list[int] = Field(default_factory=lambda: [0, 1, 2, 3], min_length=1, max_length=7)
    resamples: int = Field(2000, ge=199, le=10000)
    seed: int = 2026


@cases_router.post("/cases/{case_id}/association", tags=["cases"])
def case_association(case_id: str, req: AssociationRequest, identity: Identity = Depends(get_identity),
                     store=Depends(get_store), adapters=Depends(get_adapters), geos=Depends(get_geographies),
                     limiter=Depends(get_limiter), gate=Depends(get_gate)):
    """Anomalías mensuales de la variable en meses CON vs SIN registros SINPAD (mismo mes calendario), con desfases.

    Unidades: distritos IGN de la provincia de Trujillo. Reutiliza /analyses/compare (misma política de coste/cuota).
    """
    _case(case_id)
    if any(h < 0 or h > 12 for h in req.lags) or req.year_to <= req.year_from:
        raise Problem(422, "invalid_request", "Desfases entre 0 y 12 meses y year_to > year_from")
    units = [g for g in geos.children(geos.get("pe-ign2020:1301"))] if geos.pe.available else []
    if not units:
        raise Problem(503, "source_unavailable", "Fronteras oficiales del Perú no ingeridas")
    specs = [AnalysisSpec.model_validate({
        "data": {"dataset_id": req.dataset_id, "variable_id": req.variable_id},
        "geography": {"geo_ids": [u.geo_id]},
        "time": {"start": f"{req.year_from - 1}-01-01", "end_exclusive": f"{req.year_to + 1}-01-01", "granularity": "month"},
        "transforms": {"seasonality": "monthly_anomaly"},
    }) for u in units]
    fam = compare_analyses(CompareRequest(specs=specs, multiple_testing="none", family_id=f"{case_id}:asociacion"),
                           identity, store, adapters, geos, limiter, gate)
    series, unit_status = {}, []
    for u, it in zip(units, fam["items"], strict=True):
        unit_status.append({"geo_id": u.geo_id, "name": u.name, "status": it["status"],
                            "error": it.get("error", {}).get("code") if it["status"] != "succeeded" else None})
        if it["status"] == "succeeded":
            series[u.geo_id] = it["series"]
    if len(series) < 2:
        raise Problem(422, "insufficient_coverage", "Menos de 2 distritos con serie mensual: no hay panel comparable",
                      extra={"units": unit_status})
    known = set(series)
    evs = trujillo.events(None, req.year_from, req.year_to, True, known_geo_ids=known)
    unit_label = (adapters[req.dataset_id].info.variable(req.variable_id).unit_display
                  if req.dataset_id in adapters else "")
    out = association(series, evs, req.year_from, req.year_to, req.lags, req.resamples, req.seed, unit=unit_label)
    excluded = [e for e in trujillo.events(None, req.year_from, req.year_to, True) if f"pe-ign2020:{e['ubigeo']}" not in known]
    return out | {
        "case_id": case_id, "variable": {"dataset_id": req.dataset_id, "variable_id": req.variable_id, "unit": unit_label},
        "period": [req.year_from, req.year_to], "units": unit_status,
        "events_used": sum(1 for e in evs if e["geo_id"]), "events_excluded_no_geometry": len(excluded),
        "interpretation": "Efecto = anomalía media (respecto al mismo mes calendario) en los distrito-mes con registro "
                          "SINPAD menos la de los distrito-mes sin registro del mismo mes calendario, h meses antes.",
    }
