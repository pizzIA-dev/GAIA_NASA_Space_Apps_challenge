from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.schemas.analysis import AnalysisSpec
from app.services.analyses import runner
from app.services.earth_engine.client import EarthEngineUnavailable
from app.services.geographies import geoboundaries as gb
from app.services.geographies import registry as reg
from app.services.geographies.peru_ign import BoundariesNotIngested
from app.services.statistics.trend_core import IncompatibleMethodError

router = APIRouter(prefix="/api/v1")


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
        out = {**g.to_dict(), "attribution": geos.attribution(g.boundary_set_id),
               "children": [c.to_dict() for c in geos.children(g)]}
        if geometry == "simplified":
            out["geometry"] = geos.geometry_geojson(geo_id)
            out["geometry_note"] = "Simplificada solo para visualización; el análisis usa la geometría original"
        return out
    except gb.GeographyNotFound:
        return problem(404, "unknown_geography", f"geo_id no encontrado: {geo_id}", request)
    except (EarthEngineUnavailable, BoundariesNotIngested) as e:
        return problem(503, "source_unavailable", str(e), request)


@router.post("/analyses", tags=["analyses"])
def create_analysis(spec: AnalysisSpec, request: Request, store=Depends(get_store),
                    adapters=Depends(get_adapters), geos=Depends(get_geographies)):
    try:
        return runner.run_analysis(spec, store=store, adapters=adapters, geographies=geos)
    except runner.AnalysisError as e:
        return problem(e.status, e.code, e.detail, request)
    except IncompatibleMethodError as e:
        return problem(409, "incompatible_method", str(e), request)
    except EarthEngineUnavailable as e:
        return problem(503, "source_unavailable", str(e), request)


def _run(run_id: str, store) -> dict:
    run = store.get("runs", run_id)
    if run is None:
        raise HTTPException(404, f"run no encontrado: {run_id}")
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
