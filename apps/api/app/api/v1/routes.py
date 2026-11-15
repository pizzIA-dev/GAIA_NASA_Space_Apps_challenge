from __future__ import annotations

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
from app.services.earth_engine.adapters import catalog
from app.services.earth_engine.client import EarthEngineUnavailable
from app.services.geographies import geoboundaries as gb
from app.services.geographies import registry as reg
from app.services.geographies.peru_ign import BoundariesNotIngested
from app.services.statistics.trend_core import IncompatibleMethodError, benjamini_hochberg

router = APIRouter(prefix="/api/v1")
COMPARE_MAX_SPECS = 12


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


@router.get("/geographies/{geo_id}/features", tags=["geographies"])
def geography_features(geo_id: str, request: Request, geos=Depends(get_geographies)):
    """GeoJSON FeatureCollection del territorio y sus unidades hijas (geometría simplificada, solo visualización)."""
    try:
        g = geos.get(geo_id)
        units = [("self", g), *[("child", c) for c in geos.children(g)]]
        features = [{
            "type": "Feature", "id": u.geo_id,
            "properties": {"geo_id": u.geo_id, "name": u.name, "admin_level": u.admin_level, "area_km2": u.area_km2,
                           "role": role, "boundary_set_id": u.boundary_set_id},
            "geometry": geos.geometry_geojson(u.geo_id),
        } for role, u in units]
        return {"type": "FeatureCollection", "features": features, "attribution": geos.attribution(g.boundary_set_id),
                "geometry_note": "Simplificada solo para visualización; el análisis usa la geometría original"}
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
_gate = ExtractionGate(runner.settings.max_concurrent_extractions)


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
    No estima la diferencia entre pendientes: compárense los IC de cada ítem (pendiente futura del plan §12A.1).
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
        "note": "q-valores BH-FDR sobre los ítems con p-valor de esta familia. La diferencia entre pendientes no se "
                "estima aquí: un solapamiento de IC no equivale a una prueba de diferencia.",
    }


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
