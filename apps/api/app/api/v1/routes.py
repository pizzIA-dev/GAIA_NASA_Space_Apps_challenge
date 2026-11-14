from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.schemas.analysis import AnalysisSpec
from app.services.analyses import runner
from app.services.earth_engine.adapters import catalog
from app.services.earth_engine.client import EarthEngineUnavailable
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


@router.post("/analyses", tags=["analyses"])
def create_analysis(spec: AnalysisSpec, request: Request,
                    store=Depends(get_store), adapters=Depends(get_adapters)):
    try:
        return runner.run_analysis(spec, store=store, adapters=adapters)
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
